from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import settings
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    musescore = Path("/Applications/MuseScore 4.app/Contents/MacOS/mscore").exists()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": __version__,
        "device": settings.device,
        "data_dir": str(settings.data_dir),
        "exports_dir": str(settings.exports_dir),
        "musescore_installed": musescore,
        "db": str(settings.db_path),
    }


@app.get("/")
def root() -> dict:
    return {"message": settings.app_name, "docs": "/docs", "health": "/api/health"}
