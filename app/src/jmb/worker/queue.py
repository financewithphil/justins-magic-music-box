"""Single-consumer asyncio job queue.

Spawned in FastAPI lifespan; one job processes at a time so we never
double-load the GPU.
"""

from __future__ import annotations

import asyncio
import logging

from .pipeline import process_job

log = logging.getLogger("jmb.queue")

_queue: asyncio.Queue[str] = asyncio.Queue()
_worker_task: asyncio.Task | None = None


async def enqueue(job_id: str) -> None:
    await _queue.put(job_id)


async def _consume() -> None:
    while True:
        job_id = await _queue.get()
        try:
            await process_job(job_id)
        except Exception as e:
            log.exception("Job %s failed: %s", job_id, e)
        finally:
            _queue.task_done()


def start() -> asyncio.Task:
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_consume(), name="jmb-worker")
    return _worker_task


async def stop() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except (asyncio.CancelledError, Exception):
            pass
    _worker_task = None
