"""WebSocket endpoint for job progress updates."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.session.manager import session_manager
from backend.session.progress import build_snapshot_event

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    queue = session_manager.subscribe_ws(job_id)
    try:
        job = session_manager.get_job(job_id)
        if job:
            await websocket.send_json(build_snapshot_event(job_id, job))

        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        session_manager.unsubscribe_ws(job_id, queue)
