"""MIDI → music21 → MusicXML → MuseScore PDF.

For the violin path. Quantizes to 16th-notes, sets the violin instrument,
attempts key + time-signature inference.
"""

from __future__ import annotations

import asyncio
import shutil
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
    proc = await asyncio.create_subprocess_exec(
        MUSESCORE_BIN, "-o", str(pdf_path), str(musicxml_path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"MuseScore PDF render failed: {err.decode()[:300]}")


async def build_sheet(midi_path: Path, musicxml_path: Path, pdf_path: Path,
                       instrument: str = "violin") -> None:
    await asyncio.to_thread(midi_to_musicxml, midi_path, musicxml_path, instrument)
    await musicxml_to_pdf(musicxml_path, pdf_path)


# Backwards-compatible alias for any internal callers still using the old name.
build_violin_sheet = build_sheet
