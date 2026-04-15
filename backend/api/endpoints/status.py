"""Job status endpoint."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import JobStatus
from backend.session.manager import session_manager

router = APIRouter()


@router.get("/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> JobStatus:
    job = session_manager.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    normalized_status = "complete" if job.output_path and Path(job.output_path).exists() else job.status

    return JobStatus(
        status=normalized_status,
        progress=job.progress,
        message=job.message,
        slides_completed=job.slides_completed,
        total_slides=job.total_slides,
        output_path=job.output_path,
        error=None if normalized_status == "complete" else job.error,
    )
