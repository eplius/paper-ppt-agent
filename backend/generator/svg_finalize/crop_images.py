"""Smart image cropping for SVG images with preserveAspectRatio="...slice"."""

from __future__ import annotations

import io
import re
from pathlib import Path

from PIL import Image

X_MAP = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}
Y_MAP = {"YMin": 0.0, "YMid": 0.5, "YMax": 1.0}


def crop_images_in_svg(svg_path: Path) -> int:
    """Process images with slice aspect ratio, cropping to fit target dimensions.

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
    cropped_dir = svg_dir.parent / "images" / "cropped"
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
            cropped = _crop_to_aspect(img, target_w, target_h, align)
            if cropped is None:
                continue

            cropped_dir.mkdir(parents=True, exist_ok=True)
            out_path = cropped_dir / img_path.name
            fmt = "PNG" if img_path.suffix.lower() == ".png" else "JPEG"
            if fmt == "JPEG" and cropped.mode == "RGBA":
                cropped = cropped.convert("RGB")
            cropped.save(out_path, format=fmt, quality=90, optimize=True)

            # Update SVG element
            rel_path = f"../images/cropped/{img_path.name}"
            if f"{{{XLINK_NS}}}href" in elem.attrib:
                elem.set(f"{{{XLINK_NS}}}href", rel_path)
            else:
                elem.set("href", rel_path)
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


def _crop_to_aspect(
    img: Image.Image,
    target_w: float,
    target_h: float,
    align: dict,
) -> Image.Image | None:
    """Crop image to match target aspect ratio using alignment anchor."""
    img_w, img_h = img.size
    target_ratio = target_w / target_h
    img_ratio = img_w / img_h

    if abs(img_ratio - target_ratio) < 0.01:
        return None  # Already correct ratio

    if img_ratio > target_ratio:
        # Wider than target, crop sides
        crop_h = img_h
        crop_w = int(img_h * target_ratio)
    else:
        # Taller than target, crop top/bottom
        crop_w = img_w
        crop_h = int(img_w / target_ratio)

    extra_w = img_w - crop_w
    extra_h = img_h - crop_h
    left = int(extra_w * align["x"])
    top = int(extra_h * align["y"])

    return img.crop((left, top, left + crop_w, top + crop_h))
