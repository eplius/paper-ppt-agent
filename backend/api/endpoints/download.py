"""Download endpoint for completed presentations."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.config import settings
from backend.session.manager import session_manager

router = APIRouter()


@router.get("/download/{job_id}")
async def download_presentation(job_id: str) -> FileResponse:
    job = session_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status != "complete" or not job.output_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Presentation is not ready yet.",
        )

    path = Path(job.output_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=path.name,
    )


@router.get("/download-file")
async def download_presentation_file(output_path: str) -> FileResponse:
    path = _resolve_workspace_file(output_path)
    if path is None or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Output file not found.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=path.name,
    )


def _resolve_workspace_file(raw_path: str) -> Path | None:
    try:
        resolved = Path(raw_path).resolve()
        resolved.relative_to(settings.workspaces_dir.resolve())
    except (OSError, ValueError):
        return None
    return resolved
