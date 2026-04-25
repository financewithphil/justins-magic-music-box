from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import events as events_api
from .api import jobs as jobs_api
from .api import upload as upload_api
from .config import settings
from .db import init_db
from .worker import queue as job_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    job_queue.start()
    try:
        yield
    finally:
        await job_queue.stop()


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_api.router, prefix="/api", tags=["upload"])
app.include_router(jobs_api.router, prefix="/api", tags=["jobs"])
app.include_router(events_api.router, prefix="/api", tags=["events"])


@app.get("/api/health")
def health() -> dict:
    musescore = Path("/Applications/MuseScore 4.app/Contents/MacOS/mscore").exists()
    demucs_venv = (Path(__file__).resolve().parents[3] / "workers" / "demucs" / ".venv" / "bin" / "python").exists()
    bp_venv = (Path(__file__).resolve().parents[3] / "workers" / "basicpitch" / ".venv" / "bin" / "python").exists()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "device": settings.device,
        "data_dir": str(settings.data_dir),
        "exports_dir": str(settings.exports_dir),
        "musescore": musescore,
        "demucs_venv": demucs_venv,
        "basicpitch_venv": bp_venv,
        "db": str(settings.db_path),
    }


static_dir = Path(__file__).resolve().parents[2] / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="ui")
else:
    @app.get("/")
    def root() -> dict:
        return {"message": settings.app_name, "ui": False, "docs": "/docs"}
