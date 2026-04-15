"""LaTeX equation rendering to images.

Converts LaTeX math expressions to PNG images for embedding in SVG slides.
Uses matplotlib as the rendering backend (available via numpy/matplotlib).
"""

from __future__ import annotations

import hashlib
import subprocess
import shutil
from pathlib import Path


async def render_equation(
    latex: str,
    output_dir: Path,
    dpi: int = 200,
) -> Path | None:
    """Render a LaTeX equation to a PNG image.

    Args:
        latex: LaTeX math expression (without $ delimiters).
        output_dir: Directory to write the output image.
        dpi: Resolution for rendering.

    Returns:
        Path to the rendered PNG, or None on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate deterministic filename from equation content
    eq_hash = hashlib.md5(latex.encode()).hexdigest()[:12]
    output_path = output_dir / f"eq_{eq_hash}.png"

    if output_path.exists():
        return output_path

    # Try matplotlib rendering (most reliable cross-platform)
    try:
        return _render_with_matplotlib(latex, output_path, dpi)
    except Exception:
        pass

    return None


def _render_with_matplotlib(latex: str, output_path: Path, dpi: int) -> Path:
    """Render equation using matplotlib's TeX rendering."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(0.01, 0.01))
    ax.axis("off")

    # Render the equation
    text = ax.text(
        0.5,
        0.5,
        f"${latex}$",
        transform=ax.transAxes,
        fontsize=14,
        verticalalignment="center",
        horizontalalignment="center",
    )

    # Auto-fit figure to text
    fig.savefig(
        str(output_path),
        dpi=dpi,
        bbox_inches="tight",
        pad_inches=0.1,
        transparent=True,
    )
    plt.close(fig)
    return output_path
