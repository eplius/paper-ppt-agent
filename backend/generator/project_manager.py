"""Project directory management for SVG-based presentation generation.

Creates and manages the project workspace structure required by the
SVG generation → post-processing → PPTX export pipeline.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from backend.config import CANVAS_FORMATS


def init_project(
    name: str,
    canvas_format: str = "ppt169",
    base_dir: Path = Path("workspaces"),
) -> Path:
    """Create a new project directory with required structure.

    Args:
        name: Project name.
        canvas_format: Canvas format key (e.g., "ppt169").
        base_dir: Parent directory for projects.

    Returns:
        Path to the created project directory.
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    timestamp = now.strftime("%H%M%S")
    project_name = f"{name}_{canvas_format}_{date_str}_{timestamp}"
    project_dir = base_dir / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create required subdirectories
    for subdir in [
        "svg_output",
        "svg_final",
        "images",
        "notes",
        "templates",
        "sources",
        "exports",
    ]:
        (project_dir / subdir).mkdir(exist_ok=True)

    # Write project metadata
    fmt = CANVAS_FORMATS.get(canvas_format, CANVAS_FORMATS["ppt169"])
    readme = project_dir / "README.md"
    readme.write_text(
        f"# {name}\n\n"
        f"- **Format**: {fmt['name']} ({fmt['ratio']})\n"
        f"- **ViewBox**: `{fmt['viewbox']}`\n"
        f"- **Created**: {date_str}\n",
        encoding="utf-8",
    )

    return project_dir


def prepare_for_finalize(project_dir: Path) -> None:
    """Copy svg_output/ to svg_final/ in preparation for post-processing."""
    svg_output = project_dir / "svg_output"
    svg_final = project_dir / "svg_final"

    if svg_final.exists():
        shutil.rmtree(svg_final)
    svg_final.mkdir()

    for svg_file in sorted(svg_output.glob("*.svg")):
        shutil.copy2(svg_file, svg_final / svg_file.name)


def get_svg_files(project_dir: Path, source: str = "final") -> list[Path]:
    """Get sorted list of SVG files from a project directory.

    Args:
        project_dir: Project directory path.
        source: "output" or "final".

    Returns:
        Sorted list of SVG file paths.
    """
    svg_dir = project_dir / f"svg_{source}"
    if not svg_dir.exists():
        return []
    return sorted(svg_dir.glob("*.svg"))


def get_notes(project_dir: Path, svg_files: list[Path]) -> dict[str, str]:
    """Match speaker notes files to SVG files.

    Returns:
        Dict mapping SVG stem to notes markdown content.
    """
    notes_dir = project_dir / "notes"
    if not notes_dir.exists():
        return {}

    notes = {}
    for svg_path in svg_files:
        stem = svg_path.stem
        # Try exact match first
        md_path = notes_dir / f"{stem}.md"
        if md_path.exists():
            notes[stem] = md_path.read_text(encoding="utf-8")
    return notes
