"""Fix SVG images that use preserveAspectRatio="slice".

For images with preserveAspectRatio="slice", the image fills the element box
and content is cropped. We convert to "meet" (the SVG default) so the full
image is visible with letterboxing, without changing element dimensions.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

X_MAP = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}
Y_MAP = {"YMin": 0.0, "YMid": 0.5, "YMax": 1.0}


def crop_images_in_svg(svg_path: Path) -> int:
    """Adjust SVG image dimensions to preserve full image content.

    For images with preserveAspectRatio="slice", converts to default "meet"
    behavior so the full image is visible without cropping.

    Returns:
        Number of images processed.
    """
    import xml.etree.ElementTree as ET

    SVG_NS = "http://www.w3.org/2000/svg"
    XLINK_NS = "http://www.w3.org/1999/xlink"
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    svg_dir = svg_path.parent
    count = 0

    for elem in root.iter():
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag != "image":
            continue

        par = elem.get("preserveAspectRatio", "")
        if "slice" not in par:
            continue

        # Parse alignment
        align, _ = _parse_par(par)
        if not align:
            continue

        # Get target dimensions from SVG attributes
        try:
            target_w = float(elem.get("width", 0))
            target_h = float(elem.get("height", 0))
        except ValueError:
            continue
        if target_w <= 0 or target_h <= 0:
            continue

        # Get image href
        href = elem.get(f"{{{XLINK_NS}}}href") or elem.get("href", "")
        if not href or href.startswith("data:"):
            continue

        img_path = (svg_dir / href).resolve()
        if not img_path.exists():
            img_path = (svg_dir.parent / href).resolve()
        if not img_path.exists():
            continue

        try:
            img = Image.open(img_path)
            img_w, img_h = img.size
            if img_w <= 0 or img_h <= 0:
                continue

            # Just remove "slice" — browser default "meet" will show the
            # full image with letterboxing. Keep original element dimensions
            # to preserve layout.
            if "preserveAspectRatio" in elem.attrib:
                del elem.attrib["preserveAspectRatio"]
            count += 1
        except Exception:
            continue

    if count > 0:
        tree.write(str(svg_path), xml_declaration=True, encoding="unicode")
    return count


def _parse_par(par: str) -> tuple[dict | None, str]:
    """Parse preserveAspectRatio string."""
    parts = par.strip().split()
    if len(parts) < 2:
        return None, ""
    align_str = parts[0]
    mode = parts[1] if len(parts) > 1 else "meet"

    # Parse alignment: "xMidYMid" -> {x: 0.5, y: 0.5}
    x_match = re.search(r"(xMin|xMid|xMax)", align_str)
    y_match = re.search(r"(YMin|YMid|YMax)", align_str)
    if not x_match or not y_match:
        return None, mode

    return {"x": X_MAP[x_match.group(1)], "y": Y_MAP[y_match.group(1)]}, mode


def _fmt(val: float) -> str:
    """Format float compactly."""
    if val == int(val):
        return str(int(val))
    return f"{val:.2f}".rstrip("0").rstrip(".")
