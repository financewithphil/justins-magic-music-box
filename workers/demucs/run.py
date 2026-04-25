"""Demucs subprocess CLI wrapper, run inside .venv-demucs.

Invoked by app/src/jmb/worker/stages/separate.py.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True, help="Source audio file")
    p.add_argument("--out-dir", required=True, help="Where to put per-stem WAVs")
    p.add_argument("--model", default="htdemucs", help="htdemucs | htdemucs_ft | htdemucs_6s")
    p.add_argument("--device", default="mps", choices=["mps", "cpu"])
    p.add_argument("--segment", type=int, default=7)
    args = p.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Demucs writes to <out>/<model>/<track-stem>/<stem>.wav — we'll flatten after.
    raw_root = out_dir / "_raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "demucs",
        "--name", args.model,
        "--device", args.device,
        "--segment", str(args.segment),
        "--out", str(raw_root),
        str(input_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # Fall back to CPU on MPS-specific failures
        if args.device == "mps":
            cmd_cpu = [c if c != "mps" else "cpu" for c in cmd]
            proc = subprocess.run(cmd_cpu, capture_output=True, text=True)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr)
            return proc.returncode

    # Flatten <raw_root>/<model>/<track>/<stem>.wav → <out_dir>/<stem>.wav
    track_stem = input_path.stem
    nested = raw_root / args.model / track_stem
    if not nested.exists():
        sys.stderr.write(f"Demucs output not found at {nested}\n")
        return 2

    stems: dict[str, str] = {}
    for wav in nested.glob("*.wav"):
        target = out_dir / wav.name
        shutil.move(str(wav), str(target))
        stems[wav.stem] = str(target)

    shutil.rmtree(raw_root, ignore_errors=True)

    print(json.dumps({"ok": True, "model": args.model, "stems": stems}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
