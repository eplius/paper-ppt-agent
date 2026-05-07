"""PPTX template importer: converts a user-provided PPTX into a reusable template.

Pipeline:
  1. build_manifest() — extract metadata, theme colors, fonts
  2. export_slides_to_svg() — export via PowerPoint COM (preferred) or PyMuPDF
  3. externalize_svg_batch() — clean inline Base64 images
  4. optimize_reference_batch() — optimize SVG structure
  5. classify & select representative slides per page type
  6. generate template SVGs with content-area markers
  7. write to assets/templates/layouts/<template_id>/
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.config import settings

from .template_import.externalize_images import externalize_svg_batch
from .template_import.manifest import build_manifest
from .template_import.optimize_reference import optimize_reference_batch

logger = logging.getLogger(__name__)

_USER_TEMPLATES_DIR = settings.templates_dir / "layouts"
_USER_INDEX_PATH = _USER_TEMPLATES_DIR / "user_templates.json"

# ── Import task tracking ──────────────────────────────────────────────────────

_import_tasks: dict[str, dict[str, Any]] = {}
_import_lock = threading.Lock()


@dataclass
class ImportResult:
    template_id: str = ""
    label: str = ""
    status: str = "processing"
    export_mode: str = ""
    slide_count: int = 0
    cover_svg: str = ""
    content_svg: str = ""
    theme_colors: list[str] = field(default_factory=list)
    error: str = ""


def _generate_template_id(pptx_name: str) -> str:
    stem = Path(pptx_name).stem
    # Sanitize: lowercase, replace spaces/special chars with underscores
    safe = "".join(c if c.isalnum() else "_" for c in stem.lower()).strip("_")
    short_hash = hashlib.sha1(stem.encode()).hexdigest()[:4]
    return f"user_{safe}_{short_hash}"


# ── SVG export backends ───────────────────────────────────────────────────────

_POWERSHELL_SVG_EXPORT = r"""
param(
    [Parameter(Mandatory = $true)][string]$PptxPath,
    [Parameter(Mandatory = $true)][string]$OutputDir
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$powerpoint = $null
$presentation = $null
try {
    $powerpoint = New-Object -ComObject PowerPoint.Application
    $powerpoint.Visible = -1
    $presentation = $powerpoint.Presentations.Open($PptxPath, $false, $false, $false)
    foreach ($slide in $presentation.Slides) {
        $fileName = ('slide_{0:D2}.svg' -f $slide.SlideIndex)
        $target = Join-Path $OutputDir $fileName
        $slide.Export($target, 'SVG')
    }
} finally {
    if ($presentation -ne $null) { $presentation.Close() }
    if ($powerpoint -ne $null) { $powerpoint.Quit() }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
"""

_POWERSHELL_PDF_EXPORT = r"""
param(
    [Parameter(Mandatory = $true)][string]$PptxPath,
    [Parameter(Mandatory = $true)][string]$PdfPath
)
$ErrorActionPreference = 'Stop'
$pdfDir = Split-Path -Parent $PdfPath
New-Item -ItemType Directory -Force -Path $pdfDir | Out-Null
$powerpoint = $null
$presentation = $null
try {
    $powerpoint = New-Object -ComObject PowerPoint.Application
    $powerpoint.Visible = -1
    $presentation = $powerpoint.Presentations.Open($PptxPath, $false, $false, $false)
    $presentation.SaveAs($PdfPath, 32)
} finally {
    if ($presentation -ne $null) { $presentation.Close() }
    if ($powerpoint -ne $null) { $powerpoint.Quit() }
    [System.GC]::Collect()
    [System.GC]::WaitForPendingFinalizers()
}
"""


def _run_powershell(script: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as f:
        f.write(script)
        script_path = Path(f.name)
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), *args],
            capture_output=True,
            check=False,
        )
    finally:
        script_path.unlink(missing_ok=True)


def _export_via_powerpoint(pptx_path: Path, output_dir: Path) -> list[Path]:
    """Export PPTX slides to SVG using PowerPoint COM automation."""
    completed = _run_powershell(
        _POWERSHELL_SVG_EXPORT,
        "-PptxPath", str(pptx_path),
        "-OutputDir", str(output_dir),
    )
    if completed.returncode != 0:
        stderr = (completed.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"PowerPoint SVG export failed: {stderr}")
    svgs = sorted(output_dir.glob("slide_*.svg"))
    if not svgs:
        raise RuntimeError("PowerPoint export completed but no SVG files found")
    return svgs


def _export_via_pymupdf(pptx_path: Path, output_dir: Path) -> list[Path]:
    """Export PPTX slides to SVG via PDF→SVG using PyMuPDF."""
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) not installed. Install with: pip install pymupdf")

    # First export PPTX to PDF via PowerPoint if available, else try direct
    pdf_dir = output_dir.parent / "pdf_temp"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{pptx_path.stem}.pdf"

    if platform.system() == "Windows":
        completed = _run_powershell(
            _POWERSHELL_PDF_EXPORT,
            "-PptxPath", str(pptx_path),
            "-PdfPath", str(pdf_path),
        )
        if completed.returncode != 0:
            raise RuntimeError("PowerPoint PDF export failed (needed for PyMuPDF fallback)")
    else:
        raise RuntimeError("PDF export requires PowerPoint on Windows for PPTX→PDF step")

    if not pdf_path.exists():
        raise RuntimeError("PDF export completed but no PDF file found")

    # Convert PDF pages to SVG
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = 96.0 / 72.0
    matrix = fitz.Matrix(scale, scale)
    svg_files: list[Path] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, 1):
            target = output_dir / f"slide_{index:02d}.svg"
            target.write_text(page.get_svg_image(matrix=matrix, text_as_path=False), encoding="utf-8")
            svg_files.append(target)

    # Cleanup temp PDF
    shutil.rmtree(pdf_dir, ignore_errors=True)
    return svg_files


def _export_slides_to_svg(pptx_path: Path, output_dir: Path) -> tuple[list[Path], str]:
    """Try PowerPoint COM first, fall back to PyMuPDF. Returns (svg_files, export_mode)."""
    # Try PowerPoint COM first
    try:
        svgs = _export_via_powerpoint(pptx_path, output_dir)
        return svgs, "powerpoint-svg"
    except Exception as exc:
        logger.info("PowerPoint SVG export failed (%s), trying PyMuPDF fallback", exc)

    # Fallback: PyMuPDF (needs PowerPoint for PPTX→PDF step)
    try:
        svgs = _export_via_pymupdf(pptx_path, output_dir)
        return svgs, "pymupdf-svg"
    except Exception as exc:
        logger.info("PyMuPDF export also failed (%s), metadata-only mode", exc)

    return [], "metadata-only"


# ── Slide classification & template generation ────────────────────────────────

_PAGE_TYPE_MAP = {
    "cover_candidate": "cover",
    "chapter_candidate": "chapter",
    "toc_candidate": "toc",
    "ending_candidate": "ending",
    "content_candidate": "content",
}


def _select_representatives(manifest: dict) -> dict[str, dict]:
    """Select one representative slide per page type."""
    slides = manifest.get("slides", [])
    page_types = manifest.get("pageTypeCandidates", {})

    selected: dict[str, dict] = {}
    # Priority order for selection
    for ptype, label in _PAGE_TYPE_MAP.items():
        if label in selected:
            continue
        candidates = page_types.get(ptype, [])
        if candidates:
            idx = candidates[0]  # first candidate
            for s in slides:
                if s["index"] == idx:
                    selected[label] = s
                    break

    # Ensure we have at least content
    if "content" not in selected and slides:
        # Pick a middle slide as content representative
        mid = slides[len(slides) // 2]
        selected["content"] = mid

    return selected


def _extract_theme_colors(theme: dict) -> list[str]:
    """Extract a list of hex colors from the manifest theme."""
    colors = theme.get("colors", {})
    result = []
    for key in ("dk1", "lt1", "accent1", "accent2", "accent3", "accent4"):
        val = colors.get(key)
        if val and val.startswith("#"):
            result.append(val)
    return result[:6]


def _generate_design_spec(manifest: dict, template_id: str, label: str) -> str:
    """Generate a design_spec.md from the manifest metadata."""
    theme = manifest.get("theme", {})
    colors = theme.get("colors", {})
    fonts = theme.get("fonts", {})
    size = manifest.get("slideSize", {})
    slides = manifest.get("slides", [])

    color_lines = []
    for name, hex_val in sorted(colors.items()):
        color_lines.append(f"  - {name}: {hex_val}")

    font_lines = []
    for name, face in fonts.items():
        font_lines.append(f"  - {name}: {face}")

    page_types = manifest.get("pageTypeCandidates", {})
    pt_lines = []
    for ptype, indexes in sorted(page_types.items()):
        pt_lines.append(f"  - {ptype}: slides {indexes}")

    w = size.get("width_px", 1280)
    h = size.get("height_px", 720)

    return f"""# Template Design Spec: {label}

## Source
- Template ID: {template_id}
- Original file: {manifest.get('source', {}).get('name', 'unknown')}
- Slide size: {w} x {h} px
- Total slides: {len(slides)}

## Color Scheme
{chr(10).join(color_lines) if color_lines else '  - (none detected)'}

## Typography
{chr(10).join(font_lines) if font_lines else '  - (none detected)'}

## Page Types
{chr(10).join(pt_lines) if pt_lines else '  - (not classified)'}

## Notes
- This template was auto-imported from a PPTX file.
- SVG slides are exported reference images; content areas are marked with `<g id="content-area">`.
- The executor should use the template's color scheme and typography for generated content.
"""


def _wrap_svg_with_content_area(svg_path: Path, canvas_w: int, canvas_h: int) -> str:
    """Read an SVG and wrap the main content with a content-area marker if not present."""
    content = svg_path.read_text(encoding="utf-8")

    # If already has content-area marker, return as-is
    if 'id="content-area"' in content:
        return content

    # Insert content-area group before closing </svg>
    # Default content area: 5% margins
    margin_x = int(canvas_w * 0.03)
    margin_y = int(canvas_h * 0.14)  # top margin larger for header
    ca_w = canvas_w - 2 * margin_x
    ca_h = canvas_h - margin_y - int(canvas_h * 0.08)  # bottom margin for footer

    marker = (
        f'\n  <!-- Content area boundary (auto-generated) -->\n'
        f'  <g id="content-area">\n'
        f'    <rect x="{margin_x}" y="{margin_y}" width="{ca_w}" height="{ca_h}" '
        f'fill="none" stroke="#999" stroke-width="0.5" stroke-dasharray="4" opacity="0.3"/>\n'
        f'  </g>\n'
    )

    if "</svg>" in content:
        content = content.replace("</svg>", marker + "</svg>")
    else:
        content += marker

    return content


# ── Main import function ──────────────────────────────────────────────────────

def import_pptx_template(
    pptx_path: Path,
    *,
    task_id: str | None = None,
) -> ImportResult:
    """Import a PPTX file as a reusable template.

    If task_id is provided, progress is tracked in _import_tasks for polling.
    """
    result = ImportResult()

    def _update(**kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(result, k, v)
        if task_id:
            with _import_lock:
                _import_tasks[task_id] = {
                    "status": result.status,
                    "template_id": result.template_id,
                    "label": result.label,
                    "export_mode": result.export_mode,
                    "slide_count": result.slide_count,
                    "error": result.error,
                }

    try:
        _update(status="processing")

        # Generate template ID
        template_id = _generate_template_id(pptx_path.name)
        label = pptx_path.stem.replace("_", " ").replace("-", " ").title()
        _update(template_id=template_id, label=label)

        # Create working directory
        work_dir = Path(tempfile.mkdtemp(prefix="pptx_import_"))
        svg_raw_dir = work_dir / "svg_raw"
        svg_clean_dir = work_dir / "svg"

        # Step 1: Build manifest
        logger.info("Building manifest for %s", pptx_path.name)
        manifest = build_manifest(pptx_path, work_dir)
        slide_count = len(manifest.get("slides", []))
        _update(slide_count=slide_count)

        # Step 2: Export slides to SVG
        logger.info("Exporting slides to SVG")
        svg_files, export_mode = _export_slides_to_svg(pptx_path, svg_raw_dir)
        _update(export_mode=export_mode)

        if svg_files:
            # Step 3: Externalize inline images
            logger.info("Externalizing inline images")
            externalize_svg_batch(
                svg_files=svg_files,
                output_dir=svg_clean_dir,
                assets_dir=work_dir / "assets",
            )

            # Step 4: Optimize SVGs
            logger.info("Optimizing SVGs")
            cleaned_svgs = sorted(svg_clean_dir.glob("slide_*.svg"))
            if cleaned_svgs:
                optimize_reference_batch([str(svg_clean_dir)], precision=2)

        # Step 5: Select representative slides
        representatives = _select_representatives(manifest)

        # Step 6: Write to template directory
        template_dir = _USER_TEMPLATES_DIR / template_id
        template_dir.mkdir(parents=True, exist_ok=True)

        # Get canvas size from manifest
        size = manifest.get("slideSize", {})
        canvas_w = size.get("width_px", 1280)
        canvas_h = size.get("height_px", 720)

        # Copy representative SVGs as template files
        cover_svg = ""
        content_svg = ""

        for page_type, slide_info in representatives.items():
            slide_idx = slide_info["index"]
            src_svg = svg_clean_dir / f"slide_{slide_idx:02d}.svg"
            if not src_svg.exists():
                # Try raw dir
                src_svg = svg_raw_dir / f"slide_{slide_idx:02d}.svg"
            if not src_svg.exists():
                continue

            wrapped = _wrap_svg_with_content_area(src_svg, canvas_w, canvas_h)

            filename_map = {
                "cover": "01_cover.svg",
                "toc": "02_toc.svg",
                "chapter": "02_chapter.svg",
                "content": "03_content.svg",
                "ending": "04_ending.svg",
            }
            filename = filename_map.get(page_type)
            if filename:
                dest = template_dir / filename
                dest.write_text(wrapped, encoding="utf-8")
                if page_type == "cover":
                    cover_svg = wrapped
                elif page_type == "content":
                    content_svg = wrapped

        # If no content slide found, use the first available cleaned SVG
        if not content_svg:
            cleaned = sorted(svg_clean_dir.glob("slide_*.svg"))
            if not cleaned:
                cleaned = sorted(svg_raw_dir.glob("slide_*.svg"))
            if cleaned:
                wrapped = _wrap_svg_with_content_area(cleaned[0], canvas_w, canvas_h)
                (template_dir / "03_content.svg").write_text(wrapped, encoding="utf-8")
                content_svg = wrapped

        # Write design_spec.md
        design_spec = _generate_design_spec(manifest, template_id, label)
        (template_dir / "design_spec.md").write_text(design_spec, encoding="utf-8")

        # Copy assets
        src_assets = work_dir / "assets"
        if src_assets.is_dir():
            dest_assets = template_dir / "assets"
            if dest_assets.exists():
                shutil.rmtree(dest_assets)
            shutil.copytree(src_assets, dest_assets)

        # Save manifest
        (template_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # Update user templates index
        _register_user_template(template_id, label, manifest)

        # Extract theme colors for response
        theme_colors = _extract_theme_colors(manifest.get("theme", {}))

        _update(
            status="complete",
            cover_svg=cover_svg,
            content_svg=content_svg,
            theme_colors=theme_colors,
        )

        # Cleanup working directory
        shutil.rmtree(work_dir, ignore_errors=True)

        logger.info("Template import complete: %s", template_id)
        return result

    except Exception as exc:
        logger.exception("Template import failed")
        _update(status="error", error=str(exc))
        return result


def _register_user_template(template_id: str, label: str, manifest: dict) -> None:
    """Add a template to the user_templates.json index."""
    index: dict[str, Any] = {}
    if _USER_INDEX_PATH.exists():
        try:
            index = json.loads(_USER_INDEX_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            index = {}

    templates = index.get("templates", {})
    templates[template_id] = {
        "label": label,
        "summary": f"Imported from {manifest.get('source', {}).get('name', 'PPTX')}",
        "tone": "user-imported",
        "themeMode": "custom",
        "keywords": ["user-imported"],
        "slideCount": len(manifest.get("slides", [])),
        "theme": manifest.get("theme", {}),
    }
    index["templates"] = templates
    _USER_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    _USER_INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def remove_user_template(template_id: str) -> bool:
    """Delete a user-imported template. Returns True if deleted."""
    template_dir = _USER_TEMPLATES_DIR / template_id
    if not template_dir.is_dir():
        return False

    shutil.rmtree(template_dir, ignore_errors=True)

    # Remove from index
    if _USER_INDEX_PATH.exists():
        try:
            index = json.loads(_USER_INDEX_PATH.read_text(encoding="utf-8"))
            templates = index.get("templates", {})
            templates.pop(template_id, None)
            index["templates"] = templates
            _USER_INDEX_PATH.write_text(
                json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except (json.JSONDecodeError, OSError):
            pass

    return True


def get_import_task(task_id: str) -> dict[str, Any] | None:
    """Get the status of an import task."""
    with _import_lock:
        return _import_tasks.get(task_id)


def list_user_templates() -> list[dict[str, Any]]:
    """List all user-imported templates."""
    if not _USER_INDEX_PATH.exists():
        return []
    try:
        index = json.loads(_USER_INDEX_PATH.read_text(encoding="utf-8"))
        templates = index.get("templates", {})
        return [
            {"template_id": tid, **meta}
            for tid, meta in templates.items()
        ]
    except (json.JSONDecodeError, OSError):
        return []
