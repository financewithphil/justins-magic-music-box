"""Note-list simplification for novice-readable output.

Operates on the Basic Pitch sidecar JSON list (one dict per note with
onset/offset/pitch/amplitude/confidence). Pure logic, no IO.
"""

from __future__ import annotations


def simplify_notes(
    notes: list[dict],
    *,
    min_confidence: float = 0.4,
    min_duration_s: float = 0.12,
    beat_grid_s: float = 0.25,
) -> list[dict]:
    """Drop noisy/short notes and snap remaining ones to a coarse grid.

    Defaults are tuned for "novice readability":
    - 0.4 confidence cutoff drops bleed and ghost notes from Basic Pitch.
    - 120 ms minimum duration drops grace-note-length artifacts.
    - 0.25 s grid = an eighth note at 120 BPM. Adjacent notes that snap
      to the same (onset, pitch) collapse into one.
    """
    snapped: list[dict] = []
    for n in notes:
        if n.get("confidence", 0.0) < min_confidence:
            continue
        duration = n["offset"] - n["onset"]
        if duration < min_duration_s:
            continue
        new_onset = round(n["onset"] / beat_grid_s) * beat_grid_s
        # Round duration to grid; ensure at least one slot
        slots = max(1, round(duration / beat_grid_s))
        new_offset = new_onset + slots * beat_grid_s
        snapped.append({**n, "onset": new_onset, "offset": new_offset})

    # Dedupe: same (onset, pitch) → keep highest confidence
    by_key: dict[tuple, dict] = {}
    for n in snapped:
        k = (round(n["onset"], 4), n["pitch"])
        cur = by_key.get(k)
        if cur is None or n["confidence"] > cur["confidence"]:
            by_key[k] = n

    return sorted(by_key.values(), key=lambda n: (n["onset"], n["pitch"]))
