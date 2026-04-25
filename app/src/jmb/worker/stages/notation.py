"""MIDI → music21 → MusicXML → MuseScore PDF.

For the violin path. Quantizes to 16th-notes, sets the violin instrument,
attempts key + time-signature inference.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

MUSESCORE_BIN = "/Applications/MuseScore 4.app/Contents/MacOS/mscore"


def midi_to_musicxml(midi_path: Path, musicxml_path: Path, instrument: str = "violin") -> None:
    import music21 as m21

    score = m21.converter.parse(str(midi_path))
    score = score.quantize([4, 3])

    inst = m21.instrument.Violin() if instrument == "violin" else m21.instrument.fromString(instrument)
    for part in score.parts:
        part.insert(0, inst)
        part.partName = instrument.title()

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


async def build_violin_sheet(midi_path: Path, musicxml_path: Path, pdf_path: Path) -> None:
    await asyncio.to_thread(midi_to_musicxml, midi_path, musicxml_path, "violin")
    await musicxml_to_pdf(musicxml_path, pdf_path)
