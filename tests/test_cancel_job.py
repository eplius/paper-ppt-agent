from __future__ import annotations

import asyncio
from pathlib import Path

from backend.session.manager import session_manager


def test_cancel_job_marks_job_cancelled(workspace_tmp: Path):
    upload_dir = workspace_tmp / "uploads" / "abc123"
    upload_dir.mkdir(parents=True)
    file_path = upload_dir / "paper.pdf"
    file_path.write_bytes(b"data")

    session = session_manager.create_session(file_path, "pdf", "paper.pdf", 4, session_id="abc123")
    job = session_manager.create_job(session.id)

    async def sleeper():
        await asyncio.sleep(60)

    loop = asyncio.new_event_loop()
    try:
        task = loop.create_task(sleeper())
        session_manager.register_task(job.id, task)
        assert session_manager.cancel_job(job.id) is True
        session_manager.mark_job_cancelled(job.id)

        cancelled_job = session_manager.get_job(job.id)
        assert cancelled_job is not None
        assert cancelled_job.status == "cancelled"
        assert cancelled_job.message == "Job cancelled"
    finally:
        task.cancel()
        try:
          loop.run_until_complete(task)
        except BaseException:
          pass
        loop.close()
