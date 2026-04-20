"""Upload API endpoint."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.api.schemas import FileInfo, UploadResponse
from backend.config import settings
from backend.session.manager import session_manager

router = APIRouter()

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".tex": "latex",
    ".zip": "latex",
    ".tgz": "latex",
}

SUPPORTED_SUFFIX_PATTERNS = {
    ".tar.gz": "latex",
}


def detect_source_type(filename: str | None) -> tuple[str | None, str]:
    lower_name = (filename or "").lower()
    for suffix, source_type in SUPPORTED_SUFFIX_PATTERNS.items():
        if lower_name.endswith(suffix):
            return source_type, suffix

    suffix = Path(lower_name).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(suffix), suffix


@router.post("/upload", response_model=UploadResponse)
async def upload_paper(file: UploadFile = File(...)) -> UploadResponse:
    source_type, suffix = detect_source_type(file.filename)
    if source_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Use a paper PDF or TeX source (.pdf, .tex, .zip, .tgz, or .tar.gz).",
        )

    session_id = uuid.uuid4().hex[:12]
    upload_dir = settings.workspaces_dir / "uploads" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / (file.filename or f"upload{suffix}")
    content = await file.read()
    file_path.write_bytes(content)

    session = session_manager.create_session(
        file_path=file_path,
        source_type=source_type,
        file_name=file.filename or file_path.name,
        file_size=len(content),
        session_id=session_id,
    )

    return UploadResponse(
        session_id=session.id,
        file_info=FileInfo(
            name=session.file_name,
            size=session.file_size,
            source_type=session.source_type,
        ),
    )
