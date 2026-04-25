"""Unit tests for the novice-mode note simplifier."""

from __future__ import annotations

from jmb.worker.stages.simplify import simplify_notes


def _note(onset, offset, pitch, conf=0.8):
    return {"onset": onset, "offset": offset, "pitch": pitch, "confidence": conf, "amplitude": conf}


def test_drops_low_confidence_notes():
    notes = [_note(0.0, 1.0, 60, conf=0.8), _note(1.0, 2.0, 62, conf=0.2)]
    out = simplify_notes(notes, min_confidence=0.4)
    assert [n["pitch"] for n in out] == [60]


def test_drops_too_short_notes():
    notes = [_note(0.0, 0.05, 60), _note(0.5, 1.0, 62)]
    out = simplify_notes(notes, min_duration_s=0.1)
    assert [n["pitch"] for n in out] == [62]


def test_snaps_onsets_to_grid():
    # 0.05 is closer to 0 than to 0.25, so it snaps to 0.0
    out = simplify_notes([_note(0.05, 0.5, 60)], beat_grid_s=0.25)
    assert out[0]["onset"] == 0.0
    # 0.13 is closer to 0.25 than to 0
    out = simplify_notes([_note(0.13, 0.5, 60)], beat_grid_s=0.25)
    assert out[0]["onset"] == 0.25


def test_dedupes_collisions_keeping_higher_confidence():
    # Both 0.05 and 0.10 snap to onset 0.0, same pitch → collision; higher conf wins.
    notes = [_note(0.05, 0.6, 60, conf=0.5), _note(0.10, 0.7, 60, conf=0.9)]
    out = simplify_notes(notes, beat_grid_s=0.25)
    assert len(out) == 1
    assert out[0]["confidence"] == 0.9


def test_returns_sorted():
    notes = [_note(2.0, 3.0, 64), _note(0.0, 1.0, 60), _note(1.0, 2.0, 62)]
    out = simplify_notes(notes)
    assert [n["pitch"] for n in out] == [60, 62, 64]


def test_preserves_pitch_polyphony_at_same_onset():
    notes = [_note(0.0, 1.0, 60), _note(0.0, 1.0, 64), _note(0.0, 1.0, 67)]
    out = simplify_notes(notes)
    assert sorted(n["pitch"] for n in out) == [60, 64, 67]


def test_empty_input():
    assert simplify_notes([]) == []


def test_all_filtered_yields_empty():
    notes = [_note(0.0, 0.05, 60, conf=0.1)]   # both too short and too low conf
    assert simplify_notes(notes) == []
