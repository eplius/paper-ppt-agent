"""Convert SVG <rect rx="..."> rounded rectangles to <path> elements.

PowerPoint's "Convert to Shape" feature loses rounded corners from
<rect rx="..."/>. Converting to <path> with elliptical arcs preserves them.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"

# Attributes specific to rect that should be removed after conversion
RECT_ATTRS = {"x", "y", "width", "height", "rx", "ry"}


def convert_rounded_rects_in_svg(svg_path: Path) -> int:
    """Convert rounded rects to paths in an SVG file.

    Returns:
        Number of rectangles converted.
    """
    ET.register_namespace("", SVG_NS)

    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    root = tree.getroot()
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    rect_tag = f"{ns}rect"
    path_tag = f"{ns}path"
    count = 0

    for elem in list(root.iter(rect_tag)):
        rx = _get_float(elem, "rx", 0)
        ry = _get_float(elem, "ry", 0)

        # Only convert if rounded
        if rx <= 0 and ry <= 0:
            continue
        if ry <= 0:
            ry = rx
        if rx <= 0:
            rx = ry

        x = _get_float(elem, "x", 0)
        y = _get_float(elem, "y", 0)
        w = _get_float(elem, "width", 0)
        h = _get_float(elem, "height", 0)
        if w <= 0 or h <= 0:
            continue

        # Generate path
        d = _rect_to_rounded_path(x, y, w, h, rx, ry)

        # Replace element
        elem.tag = path_tag
        elem.set("d", d)
        for attr in RECT_ATTRS:
            if attr in elem.attrib:
                del elem.attrib[attr]
        count += 1

    if count > 0:
        tree.write(str(svg_path), xml_declaration=True, encoding="unicode")
    return count


def _rect_to_rounded_path(
    x: float, y: float, w: float, h: float, rx: float, ry: float
) -> str:
    """Convert a rounded rectangle to an SVG path with elliptical arcs."""
    # Clamp radius to half dimensions
    rx = min(rx, w / 2)
    ry = min(ry, h / 2)

    x1 = x + rx
    x2 = x + w - rx
    y1 = y + ry
    y2 = y + h - ry

    return (
        f"M{_f(x1)},{_f(y)} "
        f"H{_f(x2)} "
        f"A{_f(rx)},{_f(ry)} 0 0 1 {_f(x + w)},{_f(y1)} "
        f"V{_f(y2)} "
        f"A{_f(rx)},{_f(ry)} 0 0 1 {_f(x2)},{_f(y + h)} "
        f"H{_f(x1)} "
        f"A{_f(rx)},{_f(ry)} 0 0 1 {_f(x)},{_f(y2)} "
        f"V{_f(y1)} "
        f"A{_f(rx)},{_f(ry)} 0 0 1 {_f(x1)},{_f(y)} "
        f"Z"
    )


def _get_float(elem: ET.Element, attr: str, default: float) -> float:
    val = elem.get(attr)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _f(val: float) -> str:
    """Format float compactly, removing trailing zeros."""
    if val == int(val):
        return str(int(val))
    return f"{val:.2f}".rstrip("0").rstrip(".")
