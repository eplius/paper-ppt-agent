"""Embed external image references as Base64 data URIs in SVG files."""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image

MIME_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".svg"}

# Directories to skip when building the image index (avoid scanning venv etc.)
_SKIP_DIRS = {".venv", "venv", "node_modules", "__pycache__", ".git", "svg_output", "svg_final"}


def build_image_index(project_dir: Path) -> dict[str, Path]:
    """Recursively scan *project_dir* and return a stem→path index.

    When multiple files share the same stem the preferred extension order
    (png > jpg > jpeg > gif > webp > pdf > svg) determines which one wins.
    """
    suffix_order = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".svg"]
    # stem.lower() → {suffix.lower(): path}
    by_stem: dict[str, dict[str, Path]] = {}

    try:
        for p in project_dir.rglob("*"):
            if not p.is_file():
                continue
            # Skip undesirable directories anywhere in the path
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            stem_key = p.stem.lower()
            by_stem.setdefault(stem_key, {}).setdefault(p.suffix.lower(), p)
    except OSError:
        pass

    index: dict[str, Path] = {}
    for stem_key, candidates in by_stem.items():
        for suffix in suffix_order:
            if suffix in candidates:
                index[stem_key] = candidates[suffix]
                break
        else:
            index[stem_key] = next(iter(candidates.values()))

    return index


def _pdf_to_png_bytes(pdf_path: Path) -> bytes:
    """Render first page of a PDF to PNG bytes using PyMuPDF."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(2.0, 2.0)  # 2x resolution for clarity
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    doc.close()
    return png_bytes


def _resolve_image_path(
    href: str,
    svg_dir: Path,
    image_index: dict[str, Path] | None = None,
) -> Path | None:
    """Resolve an image href to an existing file path.

    Resolution order:
    1. Absolute path (as-is).
    2. Relative to svg_dir.
    3. Fixed candidate directories (parent, images/, sources/images/).
    4. Project-wide index built by :func:`build_image_index` — matches by
       file stem so paths invented by the LLM still resolve as long as the
       filename stem matches a real file anywhere in the project.
    """
    candidate = Path(href)
    candidate_dirs = [
        svg_dir,
        svg_dir.parent,
        svg_dir.parent / "images",
        svg_dir.parent / "sources" / "images",
    ]

    # Absolute path
    if candidate.is_absolute() and _path_exists(candidate):
        return candidate

    # Relative to SVG directory
    rel = (svg_dir / href).resolve()
    if _path_exists(rel):
        return rel

    # Try fixed parent directories by full filename
    for parent in candidate_dirs[1:]:
        c = (parent / Path(href).name).resolve()
        if _path_exists(c):
            return c

    # Fallback: same basename with a different extension in fixed dirs
    stem = candidate.stem
    if stem:
        for parent in candidate_dirs:
            alt = _match_same_stem(parent, stem)
            if alt is not None:
                return alt

    # Last resort: project-wide index lookup by stem
    if stem and image_index:
        indexed = image_index.get(stem.lower())
        if indexed is not None and _path_exists(indexed):
            return indexed

    return None


def _path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _match_same_stem(directory: Path, stem: str) -> Path | None:
    if not _path_exists(directory) or not directory.is_dir():
        return None

    suffix_order = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".svg"]
    by_suffix: dict[str, Path] = {}
    try:
        for child in directory.iterdir():
            if not child.is_file():
                continue
            if child.stem.lower() != stem.lower():
                continue
            by_suffix.setdefault(child.suffix.lower(), child)
    except OSError:
        return None

    for suffix in suffix_order:
        if suffix in by_suffix:
            return by_suffix[suffix]
    return next(iter(by_suffix.values()), None)


def embed_images_in_svg(
    svg_path: Path,
    compress: bool = False,
    max_dimension: int | None = None,
    image_index: dict[str, Path] | None = None,
) -> int:
    """Replace external image hrefs with Base64 data URIs.

    Handles PNG/JPEG/GIF/WebP directly and converts PDF images via PyMuPDF.

    Args:
        svg_path: Path to the SVG file to process.
        compress: Whether to compress embedded images.
        max_dimension: Max pixel dimension for images.
        image_index: Optional project-wide stem→path index from
            :func:`build_image_index`.  When provided, unresolved hrefs are
            looked up by filename stem so images in arbitrary subdirectories
            (e.g. ``sources/latex_src/Figure/``) are still found.

    Returns:
        Number of images embedded.
    """
    content = svg_path.read_text(encoding="utf-8")
    svg_dir = svg_path.parent
    count = 0

    def replace_href(match: re.Match) -> str:
        nonlocal count
        href = match.group(1)

        img_path = _resolve_image_path(href, svg_dir, image_index)
        if img_path is None:
            return match.group(0)

        try:
            source_ext = img_path.suffix.lstrip(".").lower()
            if source_ext == "pdf":
                img_bytes = _pdf_to_png_bytes(img_path)
                mime = "image/png"
            else:
                img_bytes = img_path.read_bytes()
                mime = _detect_mime(img_bytes, source_ext)

            if compress or max_dimension:
                img_bytes = _optimize(img_bytes, mime, compress, max_dimension)

            b64 = base64.b64encode(img_bytes).decode("ascii")
            count += 1
            return f'href="data:{mime};base64,{b64}"'
        except Exception:
            return match.group(0)

    pattern = re.compile(r'href="(?!data:)([^"]+\.(png|jpg|jpeg|gif|webp|pdf))"', re.IGNORECASE)
    content = pattern.sub(replace_href, content)
    svg_path.write_text(content, encoding="utf-8")
    return count


def _detect_mime(data: bytes, ext: str) -> str:
    """Detect MIME type from file magic bytes, falling back to extension."""
    for magic, mime in MIME_MAGIC.items():
        if data[:len(magic)] == magic:
            return mime
    ext_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
    return ext_map.get(ext, "image/png")


def _optimize(
    img_bytes: bytes,
    mime: str,
    compress: bool,
    max_dimension: int | None,
) -> bytes:
    """Optionally compress and resize image."""
    try:
        img = Image.open(io.BytesIO(img_bytes))
    except Exception:
        return img_bytes

    w, h = img.size

    if max_dimension and (w > max_dimension or h > max_dimension):
        ratio = min(max_dimension / w, max_dimension / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    if not compress:
        buf = io.BytesIO()
        fmt = "PNG" if "png" in mime else "JPEG"
        if fmt == "JPEG" and img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(buf, format=fmt, optimize=True)
        result = buf.getvalue()
        return result if len(result) < len(img_bytes) else img_bytes

    buf = io.BytesIO()
    if "jpeg" in mime or "jpg" in mime:
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85, optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)

    result = buf.getvalue()
    return result if len(result) < len(img_bytes) else img_bytes
