"""Normalize SVG text fonts for preview/export parity."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from backend.generator.svg_to_pptx.utils import select_ppt_font_family

SVG_NS = "http://www.w3.org/2000/svg"


def normalize_text_fonts_in_svg(svg_path: Path) -> int:
    """Rewrite SVG text font-family stacks to concrete PowerPoint fonts.

    Browsers can resolve CSS font fallback stacks at preview time, while PPTX
    needs a single typeface. Rewriting the SVG first makes preview and export
    read the same font name.
    """
    ET.register_namespace("", SVG_NS)

    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return 0

    changed = _normalize_element(tree.getroot(), inherited_font=None)
    if changed:
        tree.write(str(svg_path), xml_declaration=True, encoding="unicode")
    return changed


def _normalize_element(elem: ET.Element, inherited_font: str | None) -> int:
    font_stack = elem.get("font-family") or inherited_font
    changed = 0

    if _is_text_like(elem):
        text = _text_content(elem)
        chosen = select_ppt_font_family(text, font_stack or "Arial")
        if elem.get("font-family") != chosen:
            elem.set("font-family", chosen)
            changed += 1
        font_stack = chosen

    for child in list(elem):
        changed += _normalize_element(child, font_stack)

    return changed


def _is_text_like(elem: ET.Element) -> bool:
    tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    return tag in {"text", "tspan"}


def _text_content(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in list(elem):
        parts.append(_text_content(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()
