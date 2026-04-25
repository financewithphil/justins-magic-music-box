"""MIDI → music21 → MusicXML → MuseScore PDF.

Quantizes to 16th-notes, tags the part with a music21 instrument,
attempts key analysis.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

MUSESCORE_BIN = "/Applications/MuseScore 4.app/Contents/MacOS/mscore"


def _get_instrument(name: str):
    import music21 as m21

    n = (name or "").lower()
    if n == "violin": return m21.instrument.Violin()
    if n == "piano": return m21.instrument.Piano()
    if n in {"vocals", "voice"}: return m21.instrument.Vocalist()
    if n == "bass": return m21.instrument.AcousticBass()
    if n == "guitar": return m21.instrument.AcousticGuitar()
    inst = m21.instrument.Instrument()
    inst.instrumentName = name.title() if name else "Lead"
    return inst


def midi_to_musicxml(midi_path: Path, musicxml_path: Path, instrument: str = "violin") -> None:
    import music21 as m21

    score = m21.converter.parse(str(midi_path))
    score = score.quantize([4, 3])

    inst = _get_instrument(instrument)
    for part in score.parts:
        part.insert(0, inst)
        part.partName = (instrument or "Lead").title()

    try:
        key = score.analyze("key")
        score.insert(0, key)
    except Exception:
        pass

    score.write("musicxml", fp=str(musicxml_path))


async def musicxml_to_pdf(musicxml_path: Path, pdf_path: Path) -> None:
    if not Path(MUSESCORE_BIN).exists():
        raise RuntimeError(f"MuseScore not found at {MUSESCORE_BIN}")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()

    # MuseScore 4 on macOS only ships the "cocoa" Qt platform plugin — do NOT set
    # QT_QPA_PLATFORM=offscreen here; that aborts MuseScore (exit -6).
    # We just silence the harmless QML type-registration warnings the GUI bundle prints
    # on stderr; they're noise even when rendering works.
    env = os.environ.copy()
    env.setdefault(
        "QT_LOGGING_RULES",
        "qt.qml.typeregistration.warning=false;qt.qml.typeregistration=false",
    )

    proc = await asyncio.create_subprocess_exec(
        MUSESCORE_BIN, "-o", str(pdf_path), str(musicxml_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _, err = await proc.communicate()

    # MuseScore 4 on macOS routinely prints QML warnings and sometimes returns
    # non-zero even when the PDF rendered fine. Trust the output file, not the
    # return code.
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        return

    err_text = err.decode(errors="replace")[:500] or "(no stderr)"
    raise RuntimeError(
        f"MuseScore produced no PDF (exit {proc.returncode}): {err_text}"
    )


async def build_sheet(midi_path: Path, musicxml_path: Path, pdf_path: Path,
                       instrument: str = "violin") -> None:
    await asyncio.to_thread(midi_to_musicxml, midi_path, musicxml_path, instrument)
    await musicxml_to_pdf(musicxml_path, pdf_path)


# Backwards-compatible alias for any internal callers still using the old name.
build_violin_sheet = build_sheet
