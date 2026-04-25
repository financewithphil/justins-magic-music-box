"""ffprobe + sparse-source detection.

Sparse heuristic: spectral flatness over the first 30s of audio.
- Flatness < 0.06 → likely solo / sparse → bypass Demucs (violin path)
- Otherwise → full mix → use Demucs

This is a coarse rule. Tunable on Justin's first test corpus.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


async def ffprobe(path: Path) -> dict:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {err.decode()[:200]}")
    return json.loads(out)


async def normalize_to_wav(src: Path, dst: Path) -> None:
    """Extract + re-encode audio from any input (audio or video) to 44.1kHz stereo PCM-16 WAV."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-vn",                              # discard video stream cleanly
        "-map", "0:a:0?",                  # take the first audio stream if any
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
        str(dst),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg normalize failed: {err.decode()[:300]}")


def is_sparse(audio_path: str | Path, *, threshold: float = 0.06) -> tuple[bool, float]:
    """Return (is_sparse, flatness_score). Lower flatness ⇒ more harmonic / sparser."""
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=22050, mono=True, duration=30.0)
    flatness = float(np.mean(librosa.feature.spectral_flatness(y=y)))
    return flatness < threshold, flatness
