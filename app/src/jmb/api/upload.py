from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..db import Job, SessionLocal
from ..services.storage import job_dir
from ..utils.ids import new_id
from ..worker.queue import enqueue
from ..worker.stages.probe import ffprobe, normalize_to_wav

router = APIRouter()

AUDIO_SUFFIX = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".opus"}
VIDEO_SUFFIX = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".mpeg", ".mpg"}
ALLOWED_SUFFIX = AUDIO_SUFFIX | VIDEO_SUFFIX


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    instrument: str = Form("auto"),
    complexity: str = Form("full"),
):
    if instrument not in {"auto", "guitar", "violin"}:
        raise HTTPException(400, "instrument must be 'auto', 'guitar', or 'violin'")
    if complexity not in {"full", "simple"}:
        raise HTTPException(400, "complexity must be 'full' or 'simple'")
    if not file.filename:
        raise HTTPException(400, "missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIX:
        raise HTTPException(400, f"unsupported audio format {suffix}")

    job_id = new_id()
    jdir = job_dir(job_id)

    raw_path = jdir / f"raw{suffix}"
    with raw_path.open("wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)

    wav_path = jdir / "source.wav"
    await normalize_to_wav(raw_path, wav_path)

    info = await ffprobe(wav_path)
    duration_s = float(info["format"]["duration"])
    audio_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if not audio_streams:
        raw_path.unlink(missing_ok=True)
        wav_path.unlink(missing_ok=True)
        raise HTTPException(422, "no audio track found in this file")
    sample_rate = int(audio_streams[0]["sample_rate"])

    with SessionLocal() as db:
        job = Job(
            id=job_id,
            source_filename=file.filename,
            source_path=str(wav_path),
            duration_s=duration_s,
            sample_rate=sample_rate,
            state="queued",
            model="htdemucs_6s" if instrument in {"auto", "guitar"} else "htdemucs",
            instrument=instrument,
            complexity=complexity,
        )
        db.add(job)
        db.commit()

    raw_path.unlink(missing_ok=True)
    await enqueue(job_id)

    return {
        "job_id": job_id,
        "duration_s": duration_s,
        "sample_rate": sample_rate,
        "instrument": instrument,
        "state": "queued",
    }
