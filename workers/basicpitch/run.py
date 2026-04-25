"""Basic Pitch subprocess CLI wrapper, run inside .venv-basicpitch.

Outputs MIDI + sidecar JSON of (onset, offset, pitch, confidence, amplitude) per note.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--name", default="transcription", help="Base filename for outputs")
    p.add_argument("--onset-threshold", type=float, default=0.5)
    p.add_argument("--frame-threshold", type=float, default=0.3)
    p.add_argument("--minimum-note-length", type=float, default=58.0, help="ms")
    args = p.parse_args()

    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    import pretty_midi

    in_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    model_output, midi_data, note_events = predict(
        str(in_path),
        ICASSP_2022_MODEL_PATH,
        onset_threshold=args.onset_threshold,
        frame_threshold=args.frame_threshold,
        minimum_note_length=args.minimum_note_length,
    )

    midi_path = out_dir / f"{args.name}.mid"
    midi_data.write(str(midi_path))

    # basic-pitch note_events tuple: (start_time, end_time, pitch_midi, amplitude, pitch_bends?)
    notes_json = [
        {
            "onset": float(n[0]),
            "offset": float(n[1]),
            "pitch": int(n[2]),
            "amplitude": float(n[3]),
            "confidence": float(n[3]),  # amplitude is the model's per-note confidence proxy
        }
        for n in note_events
    ]
    sidecar = out_dir / f"{args.name}.notes.json"
    sidecar.write_text(json.dumps(notes_json))

    avg_conf = sum(n["confidence"] for n in notes_json) / len(notes_json) if notes_json else 0.0
    print(json.dumps({
        "ok": True,
        "midi": str(midi_path),
        "notes": str(sidecar),
        "note_count": len(notes_json),
        "avg_confidence": round(avg_conf, 3),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
