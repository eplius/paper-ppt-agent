"""Main paper-to-PPT pipeline orchestrator.

Ties together: parsing → research → strategist → SVG executor → finalize → export.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from backend.config import settings

from . import research_agent, strategist_agent, svg_executor


@dataclass
class ProgressEvent:
    """Progress event emitted during pipeline execution."""

    stage: str
    status: Literal["started", "progress", "complete", "error"]
    message: str = ""
    progress: float = 0.0  # 0.0 to 1.0
    data: dict | None = None


@dataclass
class GenerationRequest:
    """Request parameters for paper-to-PPT generation."""

    file_path: Path
    source_type: Literal["pdf", "latex"]
    provider: str  # "openai", "anthropic", "gemini"
    model: str
    api_key: str
    base_url: str | None = None
    canvas_format: str = "ppt169"
    style: str = "academic"
    num_pages: int | None = None
    instruction: str = ""
    language: str = "en"
    detail_level: str = "normal"


async def run_pipeline(
    request: GenerationRequest,
) -> AsyncIterator[ProgressEvent]:
    """Execute the full paper-to-PPT pipeline.

    Yields ProgressEvent at each stage transition.
    """
    # Initialize LLM provider
    from backend.generator.project_manager import get_notes, get_svg_files, init_project
    from backend.generator.svg_finalize import finalize_project
    from backend.generator.svg_to_pptx import create_pptx
    from backend.llm import create_provider
    from backend.parser.latex_parser import LaTeXParser
    from backend.parser.pdf_parser import PDFParser

    llm = create_provider(request.provider, request.api_key, base_url=request.base_url)

    # Create project workspace
    project_dir = init_project(
        name="paper_ppt",
        canvas_format=request.canvas_format,
        base_dir=settings.workspaces_dir,
    )

    try:
        # Stage 1: Parse paper
        yield ProgressEvent(
            "parsing",
            "started",
            "Parsing paper...",
            data={"project_dir": str(project_dir)},
        )

        output_dir = project_dir / "sources"
        if request.source_type == "pdf":
            parser = PDFParser()
        else:
            parser = LaTeXParser()

        paper = await parser.parse(request.file_path, output_dir)
        yield ProgressEvent("parsing", "complete", f"Parsed: {paper.title}", 0.15)

        # Stage 2: Research agent
        yield ProgressEvent("research", "started", "Analyzing paper content...")
        manuscript = await research_agent.analyze_paper(
            paper,
            llm,
            request.model,
            instruction=request.instruction,
            num_pages=request.num_pages,
            language=request.language,
            detail_level=request.detail_level,
        )

        # Save manuscript
        (project_dir / "manuscript.md").write_text(manuscript, encoding="utf-8")
        yield ProgressEvent("research", "complete", "Manuscript generated", 0.30)

        # Stage 3: Strategist agent
        yield ProgressEvent("strategy", "started", "Creating design specification...")
        design_spec = await strategist_agent.create_design_spec(
            manuscript,
            llm,
            request.model,
            canvas_format=request.canvas_format,
            style=request.style,
            language=request.language,
            detail_level=request.detail_level,
        )

        # Save design spec
        (project_dir / "design_spec.md").write_text(design_spec, encoding="utf-8")
        yield ProgressEvent("strategy", "complete", "Design spec created", 0.40)

        # Stage 4: SVG executor
        total_pages = manuscript.count("---") + 1
        yield ProgressEvent(
            "generation",
            "started",
            "Generating slide SVGs...",
            0.40,
            data={"total_slides": total_pages},
        )
        generated = 0

        async for page_num, svg_content in svg_executor.generate_svg_pages(
            design_spec,
            manuscript,
            project_dir,
            llm,
            request.model,
            style=request.style,
            language=request.language,
            detail_level=request.detail_level,
        ):
            generated += 1
            progress = 0.40 + (generated / total_pages) * 0.35

            # Embed images inline for live preview (browser can't load file:// paths)
            preview_svg = _embed_svg_preview(svg_content, project_dir)

            yield ProgressEvent(
                "generation",
                "progress",
                f"Generated slide {page_num}/{total_pages}",
                progress,
                data={"page": page_num, "svg": preview_svg},
            )

        yield ProgressEvent("generation", "complete", f"{generated} slides generated", 0.75)

        # Stage 5: Post-processing
        yield ProgressEvent("postprocess", "started", "Finalizing SVGs...")
        stats = finalize_project(project_dir)
        yield ProgressEvent(
            "postprocess",
            "complete",
            f"Processed {stats['total_files']} files",
            0.85,
        )

        # Stage 6: Export PPTX
        yield ProgressEvent("export", "started", "Exporting to PowerPoint...")
        svg_files = get_svg_files(project_dir, source="final")
        notes = get_notes(project_dir, svg_files)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pptx_path = project_dir / "exports" / f"presentation_{timestamp}.pptx"

        create_pptx(
            svg_files,
            pptx_path,
            canvas_format=request.canvas_format,
            notes=notes,
        )

        yield ProgressEvent(
            "export",
            "complete",
            "PowerPoint generated!",
            1.0,
            data={"output_path": str(pptx_path)},
        )

    except Exception as e:
        yield ProgressEvent("error", "error", str(e))
        raise


def _embed_svg_preview(svg_content: str, project_dir: Path) -> str:
    """Embed image hrefs as base64 data URIs so browsers can render them.

    Runs the same lightweight render-prep path used by preview/export,
    including icon embedding, image embedding, and safe text flattening.
    """
    from backend.generator.svg_finalize.render_ready import prepare_svg_content_for_render

    try:
        return prepare_svg_content_for_render(svg_content, project_dir / "svg_output")
    except Exception:
        return svg_content


# ── Refine pipeline ───────────────────────────────────────────────────────────


@dataclass
class RefineRequest:
    """Parameters for a refine (feedback-based iteration) run."""

    project_dir: str        # absolute path to the existing project workspace
    feedback: str           # latest user feedback text
    feedback_history: list[str]  # all feedback rounds including the latest
    job_id: str             # new job ID (for logging / context)
    parent_job_id: str      # job ID of the previous generation
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    base_url: str | None = None
    canvas_format: str = "ppt169"
    style: str = "academic"
    language: str = "en"
    detail_level: str = "normal"
    target_pages: list[int] | None = None
    allow_structure_changes: bool = False


async def run_refine_pipeline(
    request: RefineRequest,
) -> AsyncIterator[ProgressEvent]:
    """Re-run stages 4–6 (SVG generation → finalize → export) with feedback.

    Reads the existing ``manuscript.md`` and ``design_spec.md`` from the
    project directory, appends the accumulated feedback as an extra
    instruction block, then re-generates all SVG pages.

    Previously generated SVGs are archived to ``svg_archive/round_N/``
    before being overwritten so the user can compare iterations.

    Yields ProgressEvent at each stage transition — identical shape to
    ``run_pipeline`` so the frontend WebSocket handler needs no changes.
    """
    from backend.generator.project_manager import get_notes, get_svg_files
    from backend.generator.svg_finalize import finalize_project
    from backend.generator.svg_to_pptx import create_pptx
    from backend.llm import create_provider

    project_dir = Path(request.project_dir)
    if not project_dir.exists():
        yield ProgressEvent("error", "error", f"Project directory not found: {project_dir}")
        return

    # Read existing manuscript and design_spec
    manuscript_path = project_dir / "manuscript.md"
    design_spec_path = project_dir / "design_spec.md"

    if not manuscript_path.exists() or not design_spec_path.exists():
        yield ProgressEvent(
            "error", "error",
            "Cannot refine: manuscript.md or design_spec.md missing from project."
        )
        return

    manuscript = manuscript_path.read_text(encoding="utf-8")
    design_spec = design_spec_path.read_text(encoding="utf-8")

    llm = create_provider(request.provider, request.api_key, base_url=request.base_url)
    target_pages = sorted({page for page in (request.target_pages or []) if page > 0})

    # Build feedback block injected into the SVG executor prompt
    feedback_block = _build_feedback_block(
        request.feedback_history,
        target_pages=target_pages,
        allow_structure_changes=request.allow_structure_changes,
    )

    if request.allow_structure_changes:
        yield ProgressEvent("research", "started", "Revising manuscript structure from feedback...", 0.0)
        manuscript = await research_agent.revise_manuscript(
            manuscript,
            llm,
            request.model,
            feedback_history=request.feedback_history,
            language=request.language,
            detail_level=request.detail_level,
            target_pages=target_pages,
            allow_structure_changes=True,
        )
        manuscript_path.write_text(manuscript, encoding="utf-8")
        yield ProgressEvent("research", "complete", "Manuscript revised", 0.15)

        yield ProgressEvent("strategy", "started", "Rebuilding design specification...", 0.15)
        design_spec = await strategist_agent.create_design_spec(
            manuscript,
            llm,
            request.model,
            canvas_format=request.canvas_format,
            style=request.style,
            language=request.language,
            detail_level=request.detail_level,
        )
        design_spec_path.write_text(design_spec, encoding="utf-8")
        yield ProgressEvent("strategy", "complete", "Design spec rebuilt", 0.30)

    # Archive current svg_output before overwriting
    _archive_svgs(project_dir)
    if target_pages and not request.allow_structure_changes:
        _seed_svg_output_for_targeted_refine(project_dir, target_pages)

    # ── Stage 4: SVG generation (with feedback) ───────────────────────────
    total_pages = manuscript.count("---") + 1
    pages_to_generate = len(target_pages) if target_pages and not request.allow_structure_changes else total_pages
    generation_start = 0.30 if request.allow_structure_changes else 0.0
    generation_span = 0.30 if request.allow_structure_changes else 0.60
    yield ProgressEvent(
        "generation", "started",
        "Re-generating selected slides with feedback..." if target_pages and not request.allow_structure_changes else "Re-generating slides with feedback...",
        generation_start,
        data={"total_slides": pages_to_generate},
    )
    generated = 0

    async for page_num, svg_content in svg_executor.generate_svg_pages(
        design_spec,
        manuscript,
        project_dir,
        llm,
        request.model,
        style=request.style,
        language=request.language,
        detail_level=request.detail_level,
        extra_instruction=feedback_block,
        target_pages=set(target_pages) if target_pages and not request.allow_structure_changes else None,
    ):
        generated += 1
        progress = generation_start + (generated / max(pages_to_generate, 1)) * generation_span

        preview_svg = _embed_svg_preview(svg_content, project_dir)
        yield ProgressEvent(
            "generation", "progress",
            f"Generated slide {page_num}/{total_pages}",
            progress,
            data={"page": page_num, "svg": preview_svg},
        )

    yield ProgressEvent(
        "generation",
        "complete",
        f"{generated} slides regenerated",
        generation_start + generation_span,
    )

    # ── Stage 5: Post-processing ──────────────────────────────────────────
    postprocess_start = generation_start + generation_span
    export_start = 0.80 if request.allow_structure_changes else 0.80
    yield ProgressEvent("postprocess", "started", "Finalizing SVGs...", postprocess_start)
    stats = finalize_project(project_dir)
    yield ProgressEvent(
        "postprocess", "complete",
        f"Processed {stats['total_files']} files",
        export_start,
    )

    # ── Stage 6: Export PPTX ─────────────────────────────────────────────
    yield ProgressEvent("export", "started", "Exporting to PowerPoint...", export_start)
    svg_files = get_svg_files(project_dir, source="final")
    notes = get_notes(project_dir, svg_files)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pptx_path = project_dir / "exports" / f"presentation_{timestamp}.pptx"

    create_pptx(svg_files, pptx_path, canvas_format=request.canvas_format, notes=notes)

    # Persist feedback history to disk for auditability
    _save_feedback_history(project_dir, request.feedback_history)

    yield ProgressEvent(
        "export", "complete",
        "Refined PowerPoint generated!",
        1.0,
        data={"output_path": str(pptx_path)},
    )


def _archive_svgs(project_dir: Path) -> None:
    """Copy current svg_output/ into svg_archive/round_N/ before overwriting."""
    import shutil

    svg_output = project_dir / "svg_output"
    if not svg_output.exists():
        return

    archive_base = project_dir / "svg_archive"
    archive_base.mkdir(exist_ok=True)

    # find next round number
    existing = [d for d in archive_base.iterdir() if d.is_dir() and d.name.startswith("round_")]
    next_round = len(existing) + 1
    dest = archive_base / f"round_{next_round:02d}"
    try:
        shutil.copytree(svg_output, dest)
    except Exception:
        pass


def _build_feedback_block(
    feedback_history: list[str],
    *,
    target_pages: list[int] | None = None,
    allow_structure_changes: bool = False,
) -> str:
    """Format accumulated feedback history as a prompt instruction block."""
    if not feedback_history:
        return ""
    lines = ["## User Feedback (apply to ALL slides)"]
    if target_pages:
        lines.append(
            "\n## Targeted Scope\n"
            f"\nOnly modify these slide pages: {', '.join(map(str, target_pages))}."
            "\nKeep all other pages visually and semantically unchanged."
        )
    if allow_structure_changes:
        lines.append(
            "\n## Structural Changes Allowed\n"
            "\nYou may insert new slides, remove slides, split dense slides, or reorder slides if needed."
        )
    for i, fb in enumerate(feedback_history, 1):
        lines.append(f"\n### Round {i}\n{fb.strip()}")
    lines.append(
        "\n**Important:** Address ALL feedback points above when generating each slide."
    )
    return "\n".join(lines)


def _save_feedback_history(project_dir: Path, history: list[str]) -> None:
    """Append-write feedback_history.json for auditability."""
    import json

    path = project_dir / "feedback_history.json"
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_svg_output_for_targeted_refine(project_dir: Path, target_pages: list[int]) -> None:
    """Seed svg_output/ with the latest stable deck before partial regeneration."""
    import shutil

    source_dir = project_dir / "svg_final"
    if not source_dir.exists() or not any(source_dir.glob("*.svg")):
        source_dir = project_dir / "svg_output"
    if not source_dir.exists():
        return

    output_dir = project_dir / "svg_output"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for svg_path in sorted(source_dir.glob("*.svg")):
        shutil.copy2(svg_path, output_dir / svg_path.name)

    for page in target_pages:
        for existing in output_dir.glob(f"{page:02d}_*.svg"):
            existing.unlink(missing_ok=True)
