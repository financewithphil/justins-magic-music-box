from __future__ import annotations

import asyncio
from collections import defaultdict

from ..db import Event, SessionLocal


class EventsBus:
    """Persists events to SQLite and notifies async listeners per job."""

    def __init__(self) -> None:
        self._listeners: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def emit(self, job_id: str, stage: str, message: str | None = None,
             progress: float | None = None) -> int:
        with SessionLocal() as db:
            ev = Event(job_id=job_id, stage=stage, progress=progress, message=message)
            db.add(ev)
            db.commit()
            db.refresh(ev)
            event_id = ev.id

        payload = {
            "id": event_id,
            "stage": stage,
            "progress": progress,
            "message": message,
        }
        for q in list(self._listeners.get(job_id, ())):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
        return event_id

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._listeners[job_id].add(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        self._listeners[job_id].discard(q)


bus = EventsBus()
