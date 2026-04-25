"""MIDI → guitar tabs (GP5 + ASCII).

Uses a Viterbi-style DP allocator to assign each MIDI note to a
(string, fret) pair on a 6-string guitar in standard E tuning,
minimizing total fret-distance plus a string-change penalty.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Standard E tuning, low to high — MIDI pitches for open strings
STRINGS = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
MAX_FRET = 24
INF = float("inf")


@dataclass
class TabPos:
    string_idx: int  # 0 = lowest (E2), 5 = highest (E4)
    fret: int


def positions_for_pitch(pitch: int) -> list[TabPos]:
    out: list[TabPos] = []
    for s_idx, open_pitch in enumerate(STRINGS):
        fret = pitch - open_pitch
        if 0 <= fret <= MAX_FRET:
            out.append(TabPos(s_idx, fret))
    return out


def _transition_cost(a: TabPos, b: TabPos) -> float:
    return abs(a.fret - b.fret) + 0.5 * abs(a.string_idx - b.string_idx)


def allocate(pitches: list[int]) -> list[TabPos | None]:
    """Viterbi DP over per-note position options. Out-of-range notes become None."""
    n = len(pitches)
    if n == 0:
        return []

    options: list[list[TabPos]] = [positions_for_pitch(p) for p in pitches]

    # cost[i][j] = min total cost to be at options[i][j] after note i
    # back[i][j] = chosen options[i-1] index that produced it
    cost: list[list[float]] = [[INF] * len(o) for o in options]
    back: list[list[int]] = [[-1] * len(o) for o in options]

    if not options[0]:
        cost[0] = []
    else:
        # bias toward middle of fretboard at start
        for j, pos in enumerate(options[0]):
            cost[0][j] = abs(pos.fret - 5) * 0.1

    last_idx_with_options = 0 if options[0] else -1

    for i in range(1, n):
        if not options[i]:
            continue
        if last_idx_with_options < 0:
            for j, pos in enumerate(options[i]):
                cost[i][j] = abs(pos.fret - 5) * 0.1
            last_idx_with_options = i
            continue
        prev_options = options[last_idx_with_options]
        prev_costs = cost[last_idx_with_options]
        for j, pos_j in enumerate(options[i]):
            best = INF
            best_k = -1
            for k, pos_k in enumerate(prev_options):
                t = prev_costs[k] + _transition_cost(pos_k, pos_j)
                if t < best:
                    best = t
                    best_k = k
            cost[i][j] = best
            back[i][j] = best_k
        last_idx_with_options = i

    # backtrace
    result: list[TabPos | None] = [None] * n
    if last_idx_with_options < 0:
        return result

    cur_i = last_idx_with_options
    cur_j = min(range(len(options[cur_i])), key=lambda j: cost[cur_i][j])
    result[cur_i] = options[cur_i][cur_j]

    while cur_i > 0:
        prev_i = cur_i - 1
        while prev_i >= 0 and not options[prev_i]:
            prev_i -= 1
        if prev_i < 0:
            break
        prev_j = back[cur_i][cur_j]
        if prev_j < 0:
            break
        result[prev_i] = options[prev_i][prev_j]
        cur_i, cur_j = prev_i, prev_j

    return result


def render_ascii_tab(notes: list[dict], positions: list[TabPos | None],
                      title: str = "Tab", measures_per_line: int = 4) -> str:
    """Group notes into measures by onset and render a 6-line ASCII tab.

    `notes` is the Basic Pitch sidecar list; we use onset/offset for layout.
    Simple time-grid: 16 columns per measure (16th-note grid). Tempo is approximated.
    """
    if not notes:
        return f"{title}\n(empty)\n"

    end_t = max(n["offset"] for n in notes)
    # crude tempo: aim for ~120 BPM @ 4/4 → 0.125s per 16th
    seconds_per_col = 0.125
    total_cols = max(16, int(end_t / seconds_per_col) + 1)
    cols_per_measure = 16

    lines = ["e|", "B|", "G|", "D|", "A|", "E|"]
    grid: list[list[str]] = [["-"] * total_cols for _ in range(6)]

    for note, pos in zip(notes, positions, strict=False):
        if pos is None:
            continue
        col = int(note["onset"] / seconds_per_col)
        if col >= total_cols:
            continue
        # strings layout: index 0 = low E (bottom), 5 = high E (top); display is reverse
        display_row = 5 - pos.string_idx
        grid[display_row][col] = str(pos.fret)

    out: list[str] = [f"{title}", ""]
    for measure_start in range(0, total_cols, cols_per_measure * measures_per_line):
        block_end = min(measure_start + cols_per_measure * measures_per_line, total_cols)
        for row in range(6):
            cells = grid[row][measure_start:block_end]
            line = lines[row]
            # split by measure
            measures = [
                "".join(cells[i:i + cols_per_measure])
                for i in range(0, len(cells), cols_per_measure)
            ]
            line += "|".join(measures) + "|"
            out.append(line)
        out.append("")

    return "\n".join(out)


def write_gp5(notes: list[dict], positions: list[TabPos | None], gp_path: Path,
              title: str = "Justin's Magic Music Box") -> None:
    """Build a minimal Guitar Pro 5 file with one track."""
    import guitarpro as gp

    song = gp.Song()
    song.title = title
    song.artist = "Justin's Magic Music Box"
    song.tempo = 120

    track = song.tracks[0]
    track.name = "Guitar"
    # Standard E tuning: high to low in pyguitarpro convention
    track.strings = [
        gp.GuitarString(number=1, value=64),  # high E
        gp.GuitarString(number=2, value=59),
        gp.GuitarString(number=3, value=55),
        gp.GuitarString(number=4, value=50),
        gp.GuitarString(number=5, value=45),
        gp.GuitarString(number=6, value=40),  # low E
    ]

    # Group notes into measures of 4 beats @ 120 BPM = 2 seconds
    seconds_per_measure = 2.0
    if not notes:
        gp.write(song, str(gp_path))
        return

    end_t = max(n["offset"] for n in notes)
    n_measures = max(1, int(end_t / seconds_per_measure) + 1)

    # Reset measures: pyguitarpro starts with 1 by default; ensure correct count
    while len(song.measureHeaders) < n_measures:
        song.addMeasureHeader(gp.MeasureHeader())
    track.measures = []
    for header in song.measureHeaders:
        track.measures.append(gp.Measure(track, header))

    for note, pos in zip(notes, positions, strict=False):
        if pos is None:
            continue
        measure_idx = min(int(note["onset"] / seconds_per_measure), n_measures - 1)
        measure = track.measures[measure_idx]
        if not measure.voices[0].beats:
            measure.voices[0].beats = []
        beat = gp.Beat(measure.voices[0])
        beat.duration = gp.Duration(value=16)  # 16th note default
        gp_string_number = 6 - pos.string_idx  # invert: 0→6 (low E), 5→1 (high E)
        beat.notes = [gp.Note(beat, value=pos.fret, string=gp_string_number)]
        measure.voices[0].beats.append(beat)

    gp.write(song, str(gp_path))


def build_guitar_tabs(midi_path: Path, notes_json_path: Path,
                       gp_path: Path, ascii_path: Path,
                       title: str = "Tab") -> dict:
    import json as _json

    notes = _json.loads(Path(notes_json_path).read_text())
    notes = sorted(notes, key=lambda n: n["onset"])
    pitches = [n["pitch"] for n in notes]
    positions = allocate(pitches)

    placed = sum(1 for p in positions if p is not None)
    confidence = placed / max(1, len(positions))

    ascii_path.write_text(render_ascii_tab(notes, positions, title=title))
    try:
        write_gp5(notes, positions, gp_path, title=title)
        gp_ok = True
    except Exception as e:
        gp_path.write_text(f"GP5 generation failed: {e}\n")
        gp_ok = False

    return {
        "ascii": str(ascii_path),
        "gp5": str(gp_path) if gp_ok else None,
        "confidence": round(confidence, 3),
        "note_count": len(notes),
    }
