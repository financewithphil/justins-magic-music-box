from pathlib import Path

from ..config import settings


def job_dir(job_id: str) -> Path:
    d = settings.jobs_dir / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def stems_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "stems"
    d.mkdir(parents=True, exist_ok=True)
    return d


def midi_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "midi"
    d.mkdir(parents=True, exist_ok=True)
    return d


def musicxml_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "musicxml"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pdf_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "pdf"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tabs_dir(job_id: str) -> Path:
    d = job_dir(job_id) / "tabs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_dir(slug: str) -> Path:
    """User-facing directory under ~/Music/Justin's Magic Music Box/<slug>/"""
    d = settings.exports_dir / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_slug(filename: str) -> str:
    base = Path(filename).stem
    keep = "-_."
    return "".join(c if c.isalnum() or c in keep else "-" for c in base).strip("-")
