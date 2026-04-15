from __future__ import annotations

from pathlib import Path

from backend.session.manager import session_manager


def test_session_manager_broadcasts_events_and_cleans_uploads(workspace_tmp: Path):
    upload_dir = workspace_tmp / "uploads" / "abc123"
    upload_dir.mkdir(parents=True)
    file_path = upload_dir / "paper.pdf"
    file_path.write_bytes(b"data")

    session = session_manager.create_session(file_path, "pdf", "paper.pdf", 4, session_id="abc123")
    job = session_manager.create_job(session.id)

    queue = session_manager.subscribe_ws(job.id)
    session_manager.record_event(job.id, {"job_id": job.id, "type": "progress"}, status="parsing")

    event = queue.get_nowait()
    assert event["type"] == "progress"

    session_manager.unsubscribe_ws(job.id, queue)
    session_manager.delete_session(session.id)
    assert not upload_dir.exists()
