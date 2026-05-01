"""Version history endpoints — list/inspect/delete archived refine rounds."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import settings
from backend.generator.svg_finalize.render_ready import prepare_svg_content_for_render
from backend.session.manager import session_manager

router = APIRouter()


class VersionSlide(BaseModel):
    index: int
    name: str
    content: str


class VersionItem(BaseModel):
    round: int
    name: str
    path: str
    slide_count: int
    created_at: float


class VersionsResponse(BaseModel):
    job_id: str
    project_dir: str | None
    current_slide_count: int
    versions: list[VersionItem]


class VersionDetailResponse(BaseModel):
    job_id: str
    round: int
    name: str
    path: str
    slides: list[VersionSlide]


def _resolve_project_dir(job_id: str) -> Path:
    job = session_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if not job.project_dir:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job has no project directory.",
        )
    project_dir = Path(job.project_dir)
    try:
        project_dir.resolve().relative_to(settings.workspaces_dir.resolve())
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project path outside workspaces.",
        ) from exc
    if not project_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project directory not found.",
        )
    return project_dir


def _list_rounds(project_dir: Path) -> list[Path]:
    archive = project_dir / "svg_archive"
    if not archive.exists():
        return []
    rounds = [d for d in archive.iterdir() if d.is_dir() and d.name.startswith("round_")]
    rounds.sort(key=lambda p: p.name)
    return rounds


def _round_num(path: Path) -> int:
    try:
        return int(path.name.split("_", 1)[1])
    except (IndexError, ValueError):
        return -1


@router.get("/versions/{job_id}", response_model=VersionsResponse)
async def list_versions(job_id: str) -> VersionsResponse:
    job = session_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if not job.project_dir:
        return VersionsResponse(
            job_id=job_id,
            project_dir=None,
            current_slide_count=0,
            versions=[],
        )
    try:
        project_dir = _resolve_project_dir(job_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return VersionsResponse(
                job_id=job_id,
                project_dir=job.project_dir,
                current_slide_count=0,
                versions=[],
            )
        raise
    rounds = _list_rounds(project_dir)
    items: list[VersionItem] = []
    for round_dir in rounds:
        svgs = sorted(round_dir.glob("*.svg"))
        try:
            created = round_dir.stat().st_ctime
        except OSError:
            created = 0.0
        items.append(
            VersionItem(
                round=_round_num(round_dir),
                name=round_dir.name,
                path=str(round_dir),
                slide_count=len(svgs),
                created_at=created,
            )
        )

    current_count = len(list((project_dir / "svg_output").glob("*.svg"))) if (project_dir / "svg_output").exists() else 0
    return VersionsResponse(
        job_id=job_id,
        project_dir=str(project_dir),
        current_slide_count=current_count,
        versions=items,
    )


@router.get("/versions/{job_id}/{round_name}", response_model=VersionDetailResponse)
async def get_version(job_id: str, round_name: str) -> VersionDetailResponse:
    project_dir = _resolve_project_dir(job_id)
    round_dir = project_dir / "svg_archive" / round_name
    if not round_dir.exists() or not round_dir.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")

    slides: list[VersionSlide] = []
    for index, svg_path in enumerate(sorted(round_dir.glob("*.svg")), start=1):
        try:
            raw = svg_path.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            content = prepare_svg_content_for_render(raw, project_dir / "svg_output")
        except Exception:
            content = raw
        slides.append(VersionSlide(index=index, name=svg_path.stem, content=content))

    return VersionDetailResponse(
        job_id=job_id,
        round=_round_num(round_dir),
        name=round_dir.name,
        path=str(round_dir),
        slides=slides,
    )


@router.delete("/versions/{job_id}/{round_name}")
async def delete_version(job_id: str, round_name: str) -> dict[str, Any]:
    project_dir = _resolve_project_dir(job_id)
    round_dir = project_dir / "svg_archive" / round_name
    if not round_dir.exists() or not round_dir.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found.")
    try:
        shutil.rmtree(round_dir)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete version: {exc}",
        ) from exc
    return {"job_id": job_id, "round": round_name, "deleted": True}
