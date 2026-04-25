"""Job pipeline orchestrator.

Three modes (set per-job by the user at upload time):
- auto:    Demucs → pick loudest non-drum stem → route by stem type
- guitar:  Demucs htdemucs_6s → "guitar" stem → tabs
- violin:  sparse-source pre-flight; if sparse, bypass Demucs;
           else Demucs htdemucs → "other" stem → sheet music

Single-flight per Mac: the asyncio queue serializes jobs so we never
double-load the GPU.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..db import Job, Output, SessionLocal, Stem
from ..services.events_bus import bus
from ..services.storage import (
    export_dir, midi_dir, musicxml_dir, pdf_dir, safe_slug, stems_dir, tabs_dir,
)
from ..utils.ids import new_id
from .stages.detect import pick_dominant_stem, stem_to_output
from .stages.notation import build_sheet
from .stages.probe import is_sparse
from .stages.separate import run_demucs
from .stages.tabs import build_guitar_tabs
from .stages.transcribe import run_basicpitch


async def _set_state(job_id: str, state: str, error: str | None = None) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        job.state = state
        if error is not None:
            job.error = error
        if state == "complete":
            from datetime import datetime, timezone
            job.completed_at = int(datetime.now(timezone.utc).timestamp())
        db.commit()


def _record_stems(job_id: str, stems: dict[str, str]) -> None:
    with SessionLocal() as db:
        for name, p in stems.items():
            db.add(Stem(id=new_id(), job_id=job_id, name=name, path=p))
        db.commit()


async def process_job(job_id: str) -> None:
    bus.emit(job_id, "queued", "Job picked up", progress=0.0)
    await _set_state(job_id, "running")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        instrument_pref = (job.instrument or "auto").lower()
        source_path = Path(job.source_path)
        slug = safe_slug(job.source_filename)
        title = Path(job.source_filename).stem

    try:
        # 1. Probe (sparse-flatness only used by the violin branch)
        bus.emit(job_id, "probe", "Analyzing source", progress=0.1)
        sparse, flatness = is_sparse(source_path)
        bus.emit(job_id, "probe",
                 f"Spectral flatness {flatness:.3f} → {'sparse' if sparse else 'full mix'}",
                 progress=1.0)

        # 2. Decide which stem to transcribe
        output_kind: str          # "tabs" | "sheet"
        instrument_label: str     # for music21 + filename
        stem_for_midi: Path

        if instrument_pref == "auto":
            bus.emit(job_id, "separate", "Demucs htdemucs_6s — separating all instruments", progress=0.0)
            stems = await run_demucs(source_path, stems_dir(job_id), model="htdemucs_6s")
            _record_stems(job_id, stems)
            bus.emit(job_id, "separate",
                     f"Stems: {', '.join(stems)}", progress=1.0)

            winner, rms = pick_dominant_stem(stems)
            rms_str = ", ".join(f"{k}={v:.1f}" for k, v in sorted(rms.items(), key=lambda x: -x[1]))
            bus.emit(job_id, "detect",
                     f"Dominant melodic stem: {winner}  (dB: {rms_str})",
                     progress=1.0)

            output_kind, instrument_label = stem_to_output(winner)
            stem_for_midi = Path(stems[winner])

        elif instrument_pref == "guitar":
            bus.emit(job_id, "separate", "Demucs htdemucs_6s for guitar isolation", progress=0.0)
            stems = await run_demucs(source_path, stems_dir(job_id), model="htdemucs_6s")
            _record_stems(job_id, stems)
            bus.emit(job_id, "separate", f"Stems: {', '.join(stems)}", progress=1.0)
            output_kind = "tabs"
            instrument_label = "guitar"
            stem_for_midi = Path(stems.get("guitar") or next(iter(stems.values())))

        elif instrument_pref == "violin":
            if sparse:
                stem_for_midi = source_path
                bus.emit(job_id, "separate",
                         "Sparse source — bypassing Demucs (solo or near-solo violin)",
                         progress=1.0)
            else:
                bus.emit(job_id, "separate", "Demucs htdemucs (4-stem)", progress=0.0)
                stems = await run_demucs(source_path, stems_dir(job_id), model="htdemucs")
                _record_stems(job_id, stems)
                stem_for_midi = Path(stems.get("other") or next(iter(stems.values())))
                bus.emit(job_id, "separate",
                         f"Using 'other' stem (violin lives here in 4-stem model)",
                         progress=1.0)
            output_kind = "sheet"
            instrument_label = "violin"

        else:
            raise RuntimeError(f"unknown instrument preference: {instrument_pref}")

        # 3. Transcribe the chosen stem
        bus.emit(job_id, "transcribe",
                 f"Basic Pitch → {instrument_label} MIDI", progress=0.0)
        bp = await run_basicpitch(stem_for_midi, midi_dir(job_id), name=instrument_label)
        bus.emit(job_id, "transcribe",
                 f"{bp['note_count']} notes · avg confidence {bp['avg_confidence']}",
                 progress=1.0)

        midi_path = Path(bp["midi"])
        notes_json = Path(bp["notes"])

        outputs_for_export: list[Path] = [midi_path]

        # 4. Hero output
        if output_kind == "tabs":
            bus.emit(job_id, "tabs", "Generating guitar tabs", progress=0.0)
            tabs_d = tabs_dir(job_id)
            ascii_path = tabs_d / f"{instrument_label}.tab.txt"
            gp5_path = tabs_d / f"{instrument_label}.gp5"
            t = build_guitar_tabs(midi_path, notes_json, gp5_path, ascii_path, title=title)
            bus.emit(job_id, "tabs",
                     f"{t['note_count']} notes mapped (confidence {t['confidence']})",
                     progress=1.0)

            with SessionLocal() as db:
                db.add(Output(id=new_id(), job_id=job_id, kind="tabs",
                              format="ascii", path=t["ascii"], confidence=t["confidence"]))
                if t["gp5"]:
                    db.add(Output(id=new_id(), job_id=job_id, kind="tabs",
                                  format="gp5", path=t["gp5"], confidence=t["confidence"]))
                db.add(Output(id=new_id(), job_id=job_id, kind="tabs",
                              format="midi", path=str(midi_path)))
                db.commit()

            outputs_for_export.append(ascii_path)
            if t["gp5"]:
                outputs_for_export.append(gp5_path)

        else:  # sheet
            bus.emit(job_id, "notation",
                     f"Generating sheet music ({instrument_label})", progress=0.0)
            mxl = musicxml_dir(job_id) / f"{instrument_label}.musicxml"
            pdf = pdf_dir(job_id) / f"{instrument_label}.pdf"
            await build_sheet(midi_path, mxl, pdf, instrument=instrument_label)
            bus.emit(job_id, "notation",
                     f"Sheet music PDF rendered for {instrument_label}", progress=1.0)

            with SessionLocal() as db:
                db.add(Output(id=new_id(), job_id=job_id, kind="sheet",
                              format="pdf", path=str(pdf)))
                db.add(Output(id=new_id(), job_id=job_id, kind="sheet",
                              format="musicxml", path=str(mxl)))
                db.add(Output(id=new_id(), job_id=job_id, kind="sheet",
                              format="midi", path=str(midi_path)))
                db.commit()

            outputs_for_export += [mxl, pdf]

        # 5. Export to ~/Music/Justin's Magic Music Box/<slug>/
        bus.emit(job_id, "export", "Copying to ~/Music/", progress=0.0)
        ed = export_dir(slug)
        for p in outputs_for_export:
            if p.exists():
                shutil.copy2(p, ed / p.name)
        bus.emit(job_id, "export", f"Exports at {ed}", progress=1.0)

        await _set_state(job_id, "complete")
        bus.emit(job_id, "complete", f"Done — {instrument_label} {output_kind}", progress=1.0)

    except Exception as e:
        await _set_state(job_id, "failed", error=str(e))
        bus.emit(job_id, "failed", f"{type(e).__name__}: {e}")
        raise
