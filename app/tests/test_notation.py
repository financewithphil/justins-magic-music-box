"""Regression tests for the MuseScore PDF render path.

Background: MuseScore 4 on macOS spews QML warnings (e.g. about IconCode,
MusicalSymbolCodes, Contain) and sometimes returns a non-zero exit code
even when it has rendered the PDF correctly. The render should succeed
as long as the PDF file is on disk.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jmb.worker.stages.notation import MUSESCORE_BIN, musicxml_to_pdf

MINIMAL_MUSICXML = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Test</part-name></score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line></clef>
      </attributes>
      <note>
        <pitch><step>C</step><octave>4</octave></pitch>
        <duration>4</duration>
        <type>whole</type>
      </note>
    </measure>
  </part>
</score-partwise>
"""


needs_musescore = pytest.mark.skipif(
    not Path(MUSESCORE_BIN).exists(),
    reason="MuseScore 4 not installed at the expected path",
)


@needs_musescore
def test_musescore_renders_minimal_musicxml(tmp_path):
    mxl = tmp_path / "minimal.musicxml"
    mxl.write_text(MINIMAL_MUSICXML)
    pdf = tmp_path / "minimal.pdf"

    asyncio.run(musicxml_to_pdf(mxl, pdf))

    assert pdf.exists(), "MuseScore did not produce a PDF"
    assert pdf.stat().st_size > 256, f"PDF suspiciously small: {pdf.stat().st_size} bytes"
    header = pdf.read_bytes()[:5]
    assert header == b"%PDF-", f"Output is not a PDF (header={header!r})"


@needs_musescore
def test_musescore_render_overwrites_stale_output(tmp_path):
    """If a stale PDF exists at the target, the render should replace it."""
    mxl = tmp_path / "minimal.musicxml"
    mxl.write_text(MINIMAL_MUSICXML)
    pdf = tmp_path / "out.pdf"
    pdf.write_bytes(b"not a real pdf")
    stale_size = pdf.stat().st_size

    asyncio.run(musicxml_to_pdf(mxl, pdf))

    assert pdf.exists()
    assert pdf.stat().st_size > stale_size
    assert pdf.read_bytes()[:5] == b"%PDF-"


@needs_musescore
def test_musescore_raises_when_input_missing(tmp_path):
    pdf = tmp_path / "out.pdf"
    missing = tmp_path / "does-not-exist.musicxml"

    with pytest.raises(RuntimeError, match="MuseScore"):
        asyncio.run(musicxml_to_pdf(missing, pdf))

    assert not pdf.exists()
