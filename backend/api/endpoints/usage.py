"""Token usage endpoints.

Exposes aggregated views over :mod:`backend.usage.tracker` for the
frontend Logs page, plus a WebSocket that streams every new usage record
as it is recorded.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.usage.tracker import UsageEvent, usage_tracker

router = APIRouter(prefix="/usage")


def _summary_dict(s: Any) -> dict[str, Any]:
    return {
        "total_calls": s.total_calls,
        "total_prompt": s.total_prompt,
        "total_completion": s.total_completion,
        "total_tokens": s.total_tokens,
    }


@router.get("/summary")
async def usage_summary() -> dict[str, Any]:
    """Return global totals across all recorded LLM calls."""
    return _summary_dict(usage_tracker.summary())


@router.get("/daily")
async def usage_daily(days: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    """Return per-day rollups, most recent first."""
    return {"rows": usage_tracker.daily_series(days=days)}


@router.get("/by-model")
async def usage_by_model() -> dict[str, Any]:
    """Return token usage grouped by model, sorted by total tokens."""
    return {"rows": usage_tracker.per_model()}


@router.get("/by-job")
async def usage_by_job(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    """Return token usage grouped by job_id."""
    return {"rows": usage_tracker.per_job(limit=limit)}


@router.get("/by-stage")
async def usage_by_stage() -> dict[str, Any]:
    return {"rows": usage_tracker.per_stage()}


@router.get("/records")
async def usage_records(
    job_id: str | None = None,
    day: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
) -> dict[str, Any]:
    """Return raw per-call records, newest first."""
    recs = usage_tracker.all_records(job_id=job_id, day=day, limit=limit)
    return {"rows": [r.to_dict() for r in recs]}


@router.websocket("/stream")
async def usage_stream(websocket: WebSocket) -> None:
    """Push each new usage record to the client in real time."""
    await websocket.accept()
    queue: asyncio.Queue[UsageEvent] = usage_tracker.subscribe()
    try:
        # Initial snapshot so clients don't start empty.
        await websocket.send_json({
            "type": "snapshot",
            "summary": _summary_dict(usage_tracker.summary()),
            "by_model": usage_tracker.per_model(),
            "by_stage": usage_tracker.per_stage(),
            "daily": usage_tracker.daily_series(days=30),
            "recent": [
                r.to_dict() for r in usage_tracker.all_records(limit=50)
            ],
        })
        while True:
            event = await queue.get()
            await websocket.send_json({
                "type": event.type,
                "record": event.record.to_dict(),
            })
    except WebSocketDisconnect:
        pass
    finally:
        usage_tracker.unsubscribe(queue)
