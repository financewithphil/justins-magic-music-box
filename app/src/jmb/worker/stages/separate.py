"""Demucs subprocess invocation."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ...config import settings


_PROJECT_ROOT = Path(__file__).resolve().parents[5]


def _demucs_python() -> Path:
    return _PROJECT_ROOT / "workers" / "demucs" / ".venv" / "bin" / "python"


def _demucs_runner() -> Path:
    return _PROJECT_ROOT / "workers" / "demucs" / "run.py"


async def run_demucs(input_wav: Path, out_dir: Path, model: str | None = None) -> dict[str, str]:
    """Run Demucs on input_wav, drop stems into out_dir.

    Returns dict mapping stem name → wav path.
    """
    py = _demucs_python()
    if not py.exists():
        raise RuntimeError(f"Demucs venv not installed at {py.parent.parent}")

    cmd = [
        str(py), str(_demucs_runner()),
        "--input", str(input_wav),
        "--out-dir", str(out_dir),
        "--model", model or settings.demucs_default_model,
        "--device", settings.device,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Demucs failed: {stderr.decode()[:500]}")

    last_line = stdout.decode().strip().splitlines()[-1]
    payload = json.loads(last_line)
    return payload["stems"]
