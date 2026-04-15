"""Session and job lifecycle management."""

from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.config import settings


@dataclass
class Session:
    """A user upload session."""

    id: str
    file_path: Path
    source_type: str  # "pdf" or "latex"
    file_name: str
    file_size: int


@dataclass
class Job:
    """A generation job."""

    id: str
    session_id: str
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    slides_completed: int = 0
    total_slides: int = 0
    output_path: str | None = None
    error: str | None = None
    project_dir: str | None = None
    # For refine jobs: reference to the parent job that produced the project
    parent_job_id: str | None = None
    # Accumulated feedback history for refine iterations (list of strings)
    feedback_history: list[str] = field(default_factory=list)
    provider: str | None = None
    model_name: str | None = None
    base_url: str | None = None
    canvas_format: str | None = None
    style: str | None = None
    language: str | None = None
    detail_level: str | None = None
    instruction: str | None = None
    events: list[dict] = field(default_factory=list)


class SessionManager:
    """Manages sessions and jobs in memory."""

    def __init__(self) -> None:
        self._state_file = settings.runtime_dir / "session_state.json"
        self._sessions: dict[str, Session] = {}
        self._jobs: dict[str, Job] = {}
        self._ws_queues: dict[str, list[asyncio.Queue]] = {}
        # Per-project_dir async lock so two refine requests for the same
        # project cannot run concurrently and corrupt svg_final/.
        self._project_locks: dict[str, asyncio.Lock] = {}
        self._load_state()

    def create_session(
        self,
        file_path: Path,
        source_type: str,
        file_name: str,
        file_size: int,
        session_id: str | None = None,
    ) -> Session:
        session_id = session_id or uuid.uuid4().hex[:12]
        session = Session(
            id=session_id,
            file_path=file_path,
            source_type=source_type,
            file_name=file_name,
            file_size=file_size,
        )
        self._sessions[session_id] = session
        self._persist_state()
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def create_job(self, session_id: str) -> Job:
        job_id = uuid.uuid4().hex[:12]
        job = Job(id=job_id, session_id=session_id)
        self._jobs[job_id] = job
        self._persist_state()
        return job

    def create_refine_job(
        self,
        parent_job_id: str,
        feedback: str,
    ) -> Job | None:
        """Create a refine job that reuses the project_dir of *parent_job_id*.

        The new job inherits the parent's project_dir and feedback_history so
        the pipeline can append the new feedback and regenerate SVGs.

        Returns None if the parent job or its project_dir cannot be found.
        """
        parent = self._jobs.get(parent_job_id)
        if parent is None or not parent.project_dir:
            return None

        job_id = uuid.uuid4().hex[:12]
        # Build cumulative history: parent's history + new feedback
        history = list(parent.feedback_history) + [feedback]

        job = Job(
            id=job_id,
            session_id=parent.session_id,
            project_dir=parent.project_dir,
            parent_job_id=parent_job_id,
            feedback_history=history,
            provider=parent.provider,
            model_name=parent.model_name,
            base_url=parent.base_url,
            canvas_format=parent.canvas_format,
            style=parent.style,
            language=parent.language,
            detail_level=parent.detail_level,
            instruction=parent.instruction,
        )
        self._jobs[job_id] = job
        self._persist_state()
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs: Any) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        changed = False
        for key, value in kwargs.items():
            if hasattr(job, key) and getattr(job, key) != value:
                setattr(job, key, value)
                changed = True
        if changed:
            self._persist_state()

    def record_event(self, job_id: str, event: dict, **job_updates: Any) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return

        if job_updates:
            for key, value in job_updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
        job.events.append(event)
        self._persist_state()

        if job_id in self._ws_queues:
            for queue in self._ws_queues[job_id]:
                queue.put_nowait(event)

    def subscribe_ws(self, job_id: str) -> asyncio.Queue:
        """Subscribe to WebSocket events for a job."""
        queue: asyncio.Queue = asyncio.Queue()
        if job_id not in self._ws_queues:
            self._ws_queues[job_id] = []
        self._ws_queues[job_id].append(queue)
        return queue

    def unsubscribe_ws(self, job_id: str, queue: asyncio.Queue) -> None:
        if job_id in self._ws_queues:
            self._ws_queues[job_id] = [
                q for q in self._ws_queues[job_id] if q is not queue
            ]
            if not self._ws_queues[job_id]:
                self._ws_queues.pop(job_id, None)

    def get_project_lock(self, project_dir: str) -> asyncio.Lock:
        """Return (creating if needed) the async lock for *project_dir*."""
        if project_dir not in self._project_locks:
            self._project_locks[project_dir] = asyncio.Lock()
        return self._project_locks[project_dir]

    def delete_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session and session.file_path.exists():
            upload_dir = session.file_path.parent
            if upload_dir.exists():
                shutil.rmtree(upload_dir, ignore_errors=True)
        self._persist_state()

    def clear(self) -> None:
        self._sessions.clear()
        self._jobs.clear()
        self._ws_queues.clear()
        self._project_locks.clear()
        self._persist_state()

    def _persist_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": [self._serialize_session(session) for session in self._sessions.values()],
            "jobs": [self._serialize_job(job) for job in self._jobs.values()],
        }
        temp_path = self._state_file.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self._state_file)

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        for raw_session in payload.get("sessions", []):
            try:
                session = Session(
                    id=str(raw_session["id"]),
                    file_path=Path(raw_session["file_path"]),
                    source_type=str(raw_session["source_type"]),
                    file_name=str(raw_session["file_name"]),
                    file_size=int(raw_session["file_size"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._sessions[session.id] = session

        for raw_job in payload.get("jobs", []):
            try:
                job = Job(
                    id=str(raw_job["id"]),
                    session_id=str(raw_job["session_id"]),
                    status=str(raw_job.get("status", "pending")),
                    progress=float(raw_job.get("progress", 0.0)),
                    message=str(raw_job.get("message", "")),
                    slides_completed=int(raw_job.get("slides_completed", 0)),
                    total_slides=int(raw_job.get("total_slides", 0)),
                    output_path=raw_job.get("output_path"),
                    error=raw_job.get("error"),
                    project_dir=raw_job.get("project_dir"),
                    parent_job_id=raw_job.get("parent_job_id"),
                    feedback_history=list(raw_job.get("feedback_history", [])),
                    provider=raw_job.get("provider"),
                    model_name=raw_job.get("model_name"),
                    base_url=raw_job.get("base_url"),
                    canvas_format=raw_job.get("canvas_format"),
                    style=raw_job.get("style"),
                    language=raw_job.get("language"),
                    detail_level=raw_job.get("detail_level"),
                    instruction=raw_job.get("instruction"),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._jobs[job.id] = job

    @staticmethod
    def _serialize_session(session: Session) -> dict[str, Any]:
        return {
            "id": session.id,
            "file_path": str(session.file_path),
            "source_type": session.source_type,
            "file_name": session.file_name,
            "file_size": session.file_size,
        }

    @staticmethod
    def _serialize_job(job: Job) -> dict[str, Any]:
        payload = asdict(job)
        payload["events"] = []
        return payload


# Global singleton
session_manager = SessionManager()
