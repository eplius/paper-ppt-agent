from __future__ import annotations

from backend.session.manager import Job
from backend.session.progress import build_snapshot_event


def test_pending_snapshot_uses_started_status() -> None:
    job = Job(
        id="job-1",
        session_id="session-1",
        status="pending",
        progress=0.0,
        message="Generation started",
    )

    snapshot = build_snapshot_event(job.id, job)

    assert snapshot["stage"] == "parsing"
    assert snapshot["status"] == "started"
