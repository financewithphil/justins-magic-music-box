"""Auto-detect the dominant melodic instrument from Demucs stems.

Strategy: pick the loudest non-drum stem. Demucs stems are pre-separated,
so the stem with the highest RMS (excluding drums) is the most prominent
melodic source in the mix.
"""

from __future__ import annotations

from pathlib import Path


def stem_loudness_db(wav_path: str | Path) -> float:
    import librosa
    import numpy as np

    y, _ = librosa.load(str(wav_path), sr=22050, mono=True)
    if y.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(y * y)))
    return 20.0 * np.log10(max(rms, 1e-9))


def pick_dominant_stem(stems: dict[str, str]) -> tuple[str, dict[str, float]]:
    """Return (winner_stem_name, {stem_name: rms_db}) ignoring drums."""
    rms = {name: stem_loudness_db(path) for name, path in stems.items() if name != "drums"}
    if not rms:
        return next(iter(stems)), {}
    winner = max(rms, key=lambda k: rms[k])
    return winner, rms


# Map a Demucs stem name to (output_kind, friendly_label).
STEM_TO_OUTPUT: dict[str, tuple[str, str]] = {
    "guitar": ("tabs", "Guitar"),
    "bass":   ("sheet", "Bass"),       # bass-clef sheet music in v0 (no 4-string tab yet)
    "piano":  ("sheet", "Piano"),
    "vocals": ("sheet", "Voice"),
    "other":  ("sheet", "Lead"),       # violin / strings / horns / synth land here
}


def stem_to_output(stem_name: str) -> tuple[str, str]:
    return STEM_TO_OUTPUT.get(stem_name, ("sheet", stem_name.title() or "Lead"))
