"""Job pipeline orchestrator.

Single-flight per Mac: one job processes at a time. The flow:

   probe → (sparse-check) → separate (or skip) → transcribe →
       guitar tabs  OR  violin sheet music   → export to ~/Music/
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..db import Job, Output, SessionLocal, Stem
from ..services.events_bus import bus
from ..services.storage import (
    export_dir, midi_dir, pdf_dir, safe_slug, stems_dir, tabs_dir, musicxml_dir,
)
from ..utils.ids import new_id
from .stages.notation import build_violin_sheet
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


async def process_job(job_id: str) -> None:
    bus.emit(job_id, "queued", "Job picked up", progress=0.0)
    await _set_state(job_id, "running")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        instrument = (job.instrument or "guitar").lower()
        source_path = Path(job.source_path)
        slug = safe_slug(job.source_filename)

    try:
        # 1. Sparse check (mostly informative; affects routing for violin)
        bus.emit(job_id, "probe", "Analyzing source", progress=0.1)
        sparse, flatness = is_sparse(source_path)
        bus.emit(job_id, "probe",
                 f"Spectral flatness {flatness:.3f} → {'sparse' if sparse else 'full mix'}",
                 progress=1.0)

        # 2. Separate (or bypass for sparse violin)
        if instrument == "violin" and sparse:
            stem_for_midi = source_path
            bus.emit(job_id, "separate",
                     "Sparse source — bypassing Demucs", progress=1.0)
        else:
            model = "htdemucs_6s" if instrument == "guitar" else "htdemucs"
            bus.emit(job_id, "separate", f"Running Demucs ({model})", progress=0.0)
            stems = await run_demucs(source_path, stems_dir(job_id), model=model)
            bus.emit(job_id, "separate",
                     f"Demucs done — stems: {', '.join(stems)}", progress=1.0)
            with SessionLocal() as db:
                for name, p in stems.items():
                    db.add(Stem(id=new_id(), job_id=job_id, name=name, path=p))
                db.commit()

            if instrument == "guitar" and "guitar" in stems:
                stem_for_midi = Path(stems["guitar"])
            elif instrument == "violin" and "other" in stems:
                stem_for_midi = Path(stems["other"])
            else:
                stem_for_midi = Path(next(iter(stems.values())))

        # 3. Transcribe
        bus.emit(job_id, "transcribe",
                 f"Transcribing {instrument} via Basic Pitch", progress=0.0)
        bp = await run_basicpitch(stem_for_midi, midi_dir(job_id), name=instrument)
        bus.emit(job_id, "transcribe",
                 f"{bp['note_count']} notes, avg confidence {bp['avg_confidence']}",
                 progress=1.0)

        midi_path = Path(bp["midi"])
        notes_json = Path(bp["notes"])

        outputs_for_export: list[tuple[str, Path]] = [("midi", midi_path)]

        # 4. Hero output
        if instrument == "guitar":
            bus.emit(job_id, "tabs", "Generating tabs", progress=0.0)
            tabs_d = tabs_dir(job_id)
            ascii_path = tabs_d / f"{instrument}.tab.txt"
            gp5_path = tabs_d / f"{instrument}.gp5"
            t = build_guitar_tabs(midi_path, notes_json, gp5_path, ascii_path,
                                   title=Path(job.source_filename).stem)
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

            outputs_for_export += [
                ("tab.txt", ascii_path),
            ]
            if t["gp5"]:
                outputs_for_export.append(("gp5", gp5_path))
        else:
            bus.emit(job_id, "notation", "Generating sheet music", progress=0.0)
            mxl = musicxml_dir(job_id) / f"{instrument}.musicxml"
            pdf = pdf_dir(job_id) / f"{instrument}.pdf"
            await build_violin_sheet(midi_path, mxl, pdf)
            bus.emit(job_id, "notation", "Sheet music PDF rendered", progress=1.0)

            with SessionLocal() as db:
                db.add(Output(id=new_id(), job_id=job_id, kind="sheet",
                              format="pdf", path=str(pdf)))
                db.add(Output(id=new_id(), job_id=job_id, kind="sheet",
                              format="musicxml", path=str(mxl)))
                db.add(Output(id=new_id(), job_id=job_id, kind="sheet",
                              format="midi", path=str(midi_path)))
                db.commit()

            outputs_for_export += [("musicxml", mxl), ("pdf", pdf)]

        # 5. Export to ~/Music/Justin's Magic Music Box/<slug>/
        bus.emit(job_id, "export", "Copying to ~/Music/", progress=0.0)
        ed = export_dir(slug)
        for label, p in outputs_for_export:
            if p.exists():
                shutil.copy2(p, ed / p.name)
        bus.emit(job_id, "export", f"Outputs at {ed}", progress=1.0)

        await _set_state(job_id, "complete")
        bus.emit(job_id, "complete", "Done", progress=1.0)

    except Exception as e:
        await _set_state(job_id, "failed", error=str(e))
        bus.emit(job_id, "failed", f"{type(e).__name__}: {e}")
        raise
