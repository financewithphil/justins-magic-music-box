from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings
from ..db import Job, Output, SessionLocal, Stem

router = APIRouter()


def _job_to_dict(job: Job, stems: list[Stem], outputs: list[Output]) -> dict:
    return {
        "id": job.id,
        "source_filename": job.source_filename,
        "duration_s": job.duration_s,
        "sample_rate": job.sample_rate,
        "instrument": job.instrument,
        "model": job.model,
        "state": job.state,
        "error": job.error,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "stems": [{"name": s.name, "path": s.path} for s in stems],
        "outputs": [
            {
                "id": o.id,
                "kind": o.kind,
                "format": o.format,
                "path": o.path,
                "confidence": o.confidence,
            }
            for o in outputs
        ],
    }


@router.get("/jobs")
def list_jobs() -> list[dict]:
    with SessionLocal() as db:
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
        return [
            {
                "id": j.id,
                "source_filename": j.source_filename,
                "instrument": j.instrument,
                "state": j.state,
                "duration_s": j.duration_s,
                "created_at": j.created_at,
                "completed_at": j.completed_at,
            }
            for j in jobs
        ]


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        stems = list(job.stems)
        outputs = list(job.outputs)
        return _job_to_dict(job, stems, outputs)


@router.get("/jobs/{job_id}/output/{output_id}")
def download_output(job_id: str, output_id: str) -> FileResponse:
    with SessionLocal() as db:
        out = db.get(Output, output_id)
        if not out or out.job_id != job_id:
            raise HTTPException(404, "output not found")
        path = Path(out.path)
        if not path.exists():
            raise HTTPException(410, "output file missing on disk")
        return FileResponse(path, filename=path.name)


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        db.delete(job)
        db.commit()
    job_data_dir = settings.jobs_dir / job_id
    if job_data_dir.exists():
        shutil.rmtree(job_data_dir, ignore_errors=True)
    return {"deleted": job_id}
