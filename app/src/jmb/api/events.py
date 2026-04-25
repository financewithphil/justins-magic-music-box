from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..db import Event, Job, SessionLocal
from ..services.events_bus import bus

router = APIRouter()


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> EventSourceResponse:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        backlog = list(db.query(Event).filter(Event.job_id == job_id).order_by(Event.id).all())

    queue = bus.subscribe(job_id)

    async def stream():
        try:
            for ev in backlog:
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "id": ev.id,
                        "stage": ev.stage,
                        "progress": ev.progress,
                        "message": ev.message,
                        "ts": ev.ts,
                    }),
                }
            while True:
                with SessionLocal() as db:
                    job = db.get(Job, job_id)
                    if not job:
                        break
                    if job.state in ("complete", "failed"):
                        # Drain any final events queued
                        try:
                            while not queue.empty():
                                payload = queue.get_nowait()
                                yield {"event": "progress", "data": json.dumps(payload)}
                        except asyncio.QueueEmpty:
                            pass
                        yield {"event": "done", "data": json.dumps({"state": job.state})}
                        break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=2.0)
                    yield {"event": "progress", "data": json.dumps(payload)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            bus.unsubscribe(job_id, queue)

    return EventSourceResponse(stream())
