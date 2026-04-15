"""Repair common malformed SVG/XML patterns before structured post-processing."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from lxml import etree


_AMP_RE = re.compile(r"&(?!#\d+;|#x[0-9A-Fa-f]+;|[A-Za-z_][\w.-]*;)")
_TEXT_CLOSE_RE = re.compile(r"(<text\b[^>]*>[^<]*)</tspan>", re.IGNORECASE)
_STRAY_TSPAN_CLOSE_RE = re.compile(r"</tspan>\s*</text>", re.IGNORECASE)


def repair_svg_file(svg_path: Path) -> int:
    """Repair common malformed XML patterns in-place.

    Returns 1 when the file was modified and became parseable, else 0.
    """
    content = svg_path.read_text(encoding="utf-8")

    try:
        ET.fromstring(content)
        return 0
    except ET.ParseError:
        pass

    repaired = content
    repaired = _AMP_RE.sub("&amp;", repaired)

    previous = None
    while previous != repaired:
        previous = repaired
        repaired = _TEXT_CLOSE_RE.sub(r"\1</text>", repaired)
        repaired = _STRAY_TSPAN_CLOSE_RE.sub("</text>", repaired)

    try:
        ET.fromstring(repaired)
    except ET.ParseError:
        try:
            parser = etree.XMLParser(recover=True)
            recovered_root = etree.fromstring(repaired.encode("utf-8"), parser=parser)
            repaired = etree.tostring(recovered_root, encoding="unicode")
            ET.fromstring(repaired)
        except Exception:
            return 0

    if repaired != content:
        svg_path.write_text(repaired, encoding="utf-8")
        return 1
    return 0
