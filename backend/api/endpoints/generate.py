"""Generation API endpoint."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import GenerateRequest, GenerateResponse
from backend.session.manager import session_manager
from backend.session.progress import payloads_from_progress_event

router = APIRouter()


async def _iterate_pipeline(job_id: str, request: Any) -> None:
    from backend.orchestrator.pipeline import run_pipeline

    async for event in run_pipeline(request):
        current_job = session_manager.get_job(job_id)
        if current_job is None:
            return
        for payload, updates in payloads_from_progress_event(job_id, current_job, event):
            session_manager.record_event(job_id, payload, **updates)


async def _run_generation_job(job_id: str, request: Any) -> None:
    from backend.orchestrator.pipeline import ProgressEvent

    job = session_manager.get_job(job_id)
    if job is None:
        return

    timeout = getattr(request, "timeout_seconds", None)
    try:
        if timeout and timeout > 0:
            await asyncio.wait_for(_iterate_pipeline(job_id, request), timeout=timeout)
        else:
            await _iterate_pipeline(job_id, request)
    except asyncio.TimeoutError:
        current_job = session_manager.get_job(job_id)
        if current_job is None:
            return
        msg = f"Job exceeded timeout of {timeout}s"
        error_event = ProgressEvent("error", "error", msg, current_job.progress)
        for payload, updates in payloads_from_progress_event(job_id, current_job, error_event):
            session_manager.record_event(job_id, payload, **updates)
    except asyncio.CancelledError:
        session_manager.mark_job_cancelled(job_id)
        raise
    except Exception as exc:
        current_job = session_manager.get_job(job_id)
        if current_job is None:
            return
        error_event = ProgressEvent("error", "error", str(exc), current_job.progress)
        for payload, updates in payloads_from_progress_event(job_id, current_job, error_event):
            session_manager.record_event(job_id, payload, **updates)


@router.post("/generate", response_model=GenerateResponse)
async def generate_presentation(request: GenerateRequest) -> GenerateResponse:
    from backend.orchestrator.pipeline import GenerationRequest

    session = session_manager.get_session(request.session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    job = session_manager.create_job(request.session_id)
    session_manager.update_job(
        job.id,
        status="pending",
        message="Queued for generation",
        provider=request.model_settings.provider,
        model_name=request.model_settings.model,
        base_url=request.model_settings.base_url,
        canvas_format=request.options.canvas_format,
        style=request.options.style,
        language=request.options.language,
        detail_level=request.options.detail_level,
        instruction=request.instruction,
    )

    pipeline_request = GenerationRequest(
        file_path=session.file_path,
        source_type=session.source_type,  # type: ignore[arg-type]
        provider=request.model_settings.provider,
        model=request.model_settings.model,
        api_key=request.model_settings.api_key,
        base_url=request.model_settings.base_url,
        canvas_format=request.options.canvas_format,
        style=request.options.style,
        num_pages=request.options.num_pages,
        instruction=request.instruction,
        language=request.options.language,
        detail_level=request.options.detail_level,
        timeout_seconds=request.options.timeout_seconds,
        style_overrides=(
            request.options.style_overrides.model_dump(exclude_none=True)
            if request.options.style_overrides
            else None
        ),
    )

    task = asyncio.create_task(_run_generation_job(job.id, pipeline_request))
    session_manager.register_task(job.id, task)
    return GenerateResponse(job_id=job.id, status="started")
