from __future__ import annotations

from pathlib import Path

from backend.generator.project_manager import clone_project_for_refine
from backend.session.manager import session_manager


def test_clone_project_for_refine_creates_isolated_workspace(workspace_tmp: Path):
    source = workspace_tmp / "workspaces" / "paper_ppt_ppt169_20260415_120000"
    (source / "svg_output").mkdir(parents=True)
    (source / "svg_final").mkdir()
    (source / "sources").mkdir()
    (source / "notes").mkdir()
    (source / "templates").mkdir()
    (source / "images").mkdir()
    (source / "exports").mkdir()
    (source / "svg_archive").mkdir()
    (source / "manuscript.md").write_text("page-1", encoding="utf-8")
    (source / "design_spec.md").write_text("design", encoding="utf-8")
    (source / "svg_output" / "01_intro.svg").write_text("<svg />", encoding="utf-8")
    (source / "exports" / "old.pptx").write_bytes(b"old")

    cloned = clone_project_for_refine(source, "job123", base_dir=workspace_tmp / "workspaces")

    assert cloned != source
    assert cloned.name.endswith("_refine_job123")
    assert (cloned / "manuscript.md").read_text(encoding="utf-8") == "page-1"
    assert (cloned / "design_spec.md").read_text(encoding="utf-8") == "design"
    assert (cloned / "svg_output" / "01_intro.svg").exists()
    assert (cloned / "exports").exists()
    assert not any((cloned / "exports").iterdir())


def test_create_refine_job_accepts_overridden_project_dir(workspace_tmp: Path):
    upload_dir = workspace_tmp / "uploads" / "abc123"
    upload_dir.mkdir(parents=True)
    file_path = upload_dir / "paper.pdf"
    file_path.write_bytes(b"data")

    session = session_manager.create_session(file_path, "pdf", "paper.pdf", 4, session_id="abc123")
    job = session_manager.create_job(session.id)
    session_manager.update_job(job.id, project_dir=str(workspace_tmp / "workspaces" / "source_project"))

    refined = session_manager.create_refine_job(job.id, "make it shorter", project_dir=str(workspace_tmp / "workspaces" / "clone_project"))

    assert refined is not None
    assert refined.project_dir == str(workspace_tmp / "workspaces" / "clone_project")
    assert refined.parent_job_id == job.id
    assert refined.feedback_history == ["make it shorter"]
