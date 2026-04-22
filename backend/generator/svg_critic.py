"""Static SVG critic — detects layout and style violations without LLM.

Runs on a freshly generated SVG string and returns a structured report of
violations. When any violations are detected, the SVG executor uses them
to build a targeted repair prompt, so that the LLM is corrected with
specific feedback instead of blindly regenerating.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal
from xml.etree import ElementTree as ET

Severity = Literal["error", "warning"]

# Character-width heuristic per font-size. 0.55 covers most Latin glyphs;
# CJK characters are approximately full-width (~0.95). We pick 0.58 as a
# blended average that errs on the side of "probably fits" to avoid
# false positives for short, padded titles.
_CHAR_WIDTH_FACTOR = 0.58
_CJK_CHAR_WIDTH_FACTOR = 0.95

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]")
_HEX_COLOR_RE = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")

# Elements explicitly forbidden by executor.md — mirrored here so the
# critic fails fast instead of relying on LLM self-discipline.
_FORBIDDEN_TAGS = {"mask", "style", "clipPath", "filter", "foreignObject"}
# `use` is allowed for icon references; `image` allowed for raster.


@dataclass
class Violation:
    rule: str
    severity: Severity
    detail: str
    element: str | None = None
    bbox: tuple[float, float, float, float] | None = None

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "detail": self.detail,
            "element": self.element,
            "bbox": list(self.bbox) if self.bbox else None,
        }


@dataclass
class CriticReport:
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    canvas: tuple[float, float] | None = None

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "warning")

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "canvas": list(self.canvas) if self.canvas else None,
            "violations": [v.to_dict() for v in self.violations],
        }

    def to_prompt_block(self) -> str:
        """Render the report as a targeted repair instruction block."""
        if self.passed:
            return ""
        lines = ["## Validation Report", ""]
        lines.append(
            f"The previous SVG failed static validation "
            f"({self.error_count} errors, {self.warning_count} warnings). "
            "Fix ONLY the specific issues listed below."
        )
        lines.append("")
        for i, v in enumerate(self.violations, 1):
            bbox_str = ""
            if v.bbox:
                x, y, w, h = v.bbox
                bbox_str = f" at bbox(x={x:.0f}, y={y:.0f}, w={w:.0f}, h={h:.0f})"
            elem_str = f" <{v.element}>" if v.element else ""
            lines.append(f"{i}. [{v.rule}]{elem_str}{bbox_str}: {v.detail}")
        lines.append("")
        lines.append("## Repair Instructions")
        lines.append("- Fix ONLY the violations listed above.")
        lines.append(
            "- PRESERVE the overall layout, content, colors, and information density of the previous SVG. "
            "Do NOT add or remove information. Do NOT restyle unrelated elements."
        )
        lines.append("- Return the complete corrected SVG only, wrapped in ```svg code block.")
        return "\n".join(lines)


@dataclass
class CriticConfig:
    # Minimum font sizes (in SVG user units).
    min_body_font_size: float = 11.0
    min_title_font_size: float = 18.0

    # Bounding-box overlap threshold. IoU above this = overlap violation.
    text_overlap_iou: float = 0.15

    # How much a text box may stick out of the canvas before flagging.
    out_of_bounds_slack: float = 2.0

    # Allowed color-palette hex values (lowercased, without '#').
    # None = don't check.
    allowed_palette: set[str] | None = None

    # Report warnings as blocking violations (affects `passed`).
    warnings_are_blocking: bool = False

    # Maximum violations to include in the report prompt (trim noise).
    max_violations_in_report: int = 20


def _strip_ns(tag: str) -> str:
    """Strip XML namespace from a tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _parse_viewbox(root: ET.Element) -> tuple[float, float] | None:
    vb = root.get("viewBox")
    if vb:
        try:
            parts = [float(p) for p in vb.replace(",", " ").split()]
            if len(parts) == 4:
                return parts[2], parts[3]
        except ValueError:
            pass
    # Fallback to width/height attributes.
    try:
        w = root.get("width")
        h = root.get("height")
        if w and h:
            return float(re.sub(r"[^0-9.]", "", w) or 0), float(re.sub(r"[^0-9.]", "", h) or 0)
    except ValueError:
        pass
    return None


def _float_attr(el: ET.Element, name: str, default: float = 0.0) -> float:
    raw = el.get(name)
    if raw is None:
        return default
    try:
        return float(re.sub(r"[^0-9.\-]", "", raw) or default)
    except ValueError:
        return default


def _iter_all(root: ET.Element):
    for el in root.iter():
        yield el


def _text_width_estimate(text: str, font_size: float) -> float:
    if not text:
        return 0.0
    cjk_count = sum(1 for c in text if _CJK_RE.match(c))
    latin_count = len(text) - cjk_count
    return font_size * (
        cjk_count * _CJK_CHAR_WIDTH_FACTOR + latin_count * _CHAR_WIDTH_FACTOR
    )


def _text_of(el: ET.Element) -> str:
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        if _strip_ns(child.tag) == "tspan" and child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def _font_size_of(el: ET.Element, inherited: float) -> float:
    raw = el.get("font-size")
    if raw:
        try:
            return float(re.sub(r"[^0-9.]", "", raw))
        except ValueError:
            return inherited
    style = el.get("style") or ""
    m = re.search(r"font-size\s*:\s*([0-9.]+)", style)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return inherited
    return inherited


def _text_bbox(el: ET.Element, font_size: float) -> tuple[float, float, float, float]:
    """Estimate text bbox. y is treated as baseline; widen to include ascender."""
    x = _float_attr(el, "x", 0.0)
    y = _float_attr(el, "y", 0.0)
    text = _text_of(el)
    w = _text_width_estimate(text, font_size)
    h = font_size * 1.25
    # anchor can shift x left/right
    anchor = (el.get("text-anchor") or "").strip().lower()
    if anchor == "middle":
        x = x - w / 2
    elif anchor == "end":
        x = x - w
    return x, y - font_size, w, h


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    union = aw * ah + bw * bh - inter
    if union <= 0:
        return 0.0
    return inter / union


def _element_identifier(el: ET.Element) -> str:
    if el.get("id"):
        return f'{_strip_ns(el.tag)}#{el.get("id")}'
    cls = el.get("class")
    if cls:
        return f'{_strip_ns(el.tag)}.{cls}'
    return _strip_ns(el.tag)


def _collect_colors(el: ET.Element) -> list[str]:
    out: list[str] = []
    for attr in ("fill", "stroke", "color", "stop-color"):
        val = el.get(attr)
        if val and val.startswith("#"):
            out.append(val.lower().lstrip("#"))
    style = el.get("style") or ""
    for m in _HEX_COLOR_RE.finditer(style):
        out.append(m.group(1).lower())
    return out


def _normalize_hex(value: str) -> str:
    v = value.lower().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return v


def check_svg(svg_content: str, config: CriticConfig | None = None) -> CriticReport:
    """Run the static critic on an SVG string."""
    cfg = config or CriticConfig()
    violations: list[Violation] = []

    # 1. Parse SVG (lenient).
    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError as exc:
        return CriticReport(
            passed=False,
            violations=[Violation("xml_parse", "error", f"SVG is not parseable XML: {exc}")],
        )

    canvas = _parse_viewbox(root)

    # 2. Forbidden elements.
    for el in _iter_all(root):
        tag = _strip_ns(el.tag)
        if tag in _FORBIDDEN_TAGS:
            violations.append(
                Violation(
                    rule="forbidden_element",
                    severity="error",
                    detail=(
                        f"Element <{tag}> is disallowed by the executor specification. "
                        "Remove it and inline the effect if possible."
                    ),
                    element=_element_identifier(el),
                )
            )
        if el.get("class"):
            violations.append(
                Violation(
                    rule="forbidden_class",
                    severity="warning",
                    detail=(
                        "`class=` attribute is disallowed. Move styling to direct "
                        "attributes (fill, stroke, font-size, ...)."
                    ),
                    element=_element_identifier(el),
                )
            )

    # 3. Font-size + text bbox checks.
    text_boxes: list[tuple[ET.Element, tuple[float, float, float, float]]] = []
    for el in _iter_all(root):
        if _strip_ns(el.tag) != "text":
            continue
        # Inherit font-size of nearest ancestor if not set.
        font_size = _font_size_of(el, 16.0)
        text = _text_of(el)
        if not text:
            continue
        is_title = font_size >= cfg.min_title_font_size * 0.9
        min_size = cfg.min_title_font_size if is_title else cfg.min_body_font_size
        if font_size < min_size:
            violations.append(
                Violation(
                    rule="font_too_small",
                    severity="warning",
                    detail=(
                        f"Text font-size {font_size:.1f} is below the minimum "
                        f"({min_size:.0f}). Use at least {min_size:.0f}."
                    ),
                    element=_element_identifier(el),
                )
            )
        bbox = _text_bbox(el, font_size)
        text_boxes.append((el, bbox))

        # Out-of-bounds.
        if canvas:
            cw, ch = canvas
            x, y, w, h = bbox
            slack = cfg.out_of_bounds_slack
            if x < -slack or y < -slack or x + w > cw + slack or y + h > ch + slack:
                violations.append(
                    Violation(
                        rule="out_of_bounds",
                        severity="error",
                        detail=(
                            f"Text extends outside canvas ({cw:.0f}x{ch:.0f}). "
                            f"Estimated bbox ({x:.0f},{y:.0f},{w:.0f},{h:.0f})."
                        ),
                        element=_element_identifier(el),
                        bbox=bbox,
                    )
                )

    # 4. Text-to-text overlap (coarse; tolerates small padding).
    seen_pairs: set[tuple[int, int]] = set()
    for i, (el_a, box_a) in enumerate(text_boxes):
        for j in range(i + 1, len(text_boxes)):
            el_b, box_b = text_boxes[j]
            _ = el_a  # used below in Violation element field
            key = (i, j)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            iou = _iou(box_a, box_b)
            if iou > cfg.text_overlap_iou:
                violations.append(
                    Violation(
                        rule="text_overlap",
                        severity="error",
                        detail=(
                            f"Text overlaps (IoU={iou:.2f}) with another text element "
                            f"{_element_identifier(el_b)}. Separate them or shrink one."
                        ),
                        element=_element_identifier(el_a),
                        bbox=box_a,
                    )
                )

    # 5. Palette compliance (optional).
    if cfg.allowed_palette:
        allowed = {_normalize_hex(c) for c in cfg.allowed_palette}
        for el in _iter_all(root):
            for hex_color in _collect_colors(el):
                norm = _normalize_hex(hex_color)
                if norm in allowed:
                    continue
                # Always allow near-neutral grayscale + pure white/black.
                if _is_neutral(norm):
                    continue
                violations.append(
                    Violation(
                        rule="palette_violation",
                        severity="warning",
                        detail=(
                            f"Color #{norm} is not in the declared palette. "
                            "Use a color from the configured style palette, "
                            "or a neutral (white/black/gray)."
                        ),
                        element=_element_identifier(el),
                    )
                )
                break  # one palette violation per element is enough

    # Trim to avoid prompt bloat.
    if len(violations) > cfg.max_violations_in_report:
        violations = violations[: cfg.max_violations_in_report]

    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")
    blocking = error_count > 0 or (cfg.warnings_are_blocking and warning_count > 0)
    return CriticReport(passed=not blocking, violations=violations, canvas=canvas)


def _is_neutral(hex_value: str) -> bool:
    """Loose check: near-grayscale / near-white / near-black."""
    if len(hex_value) != 6:
        return False
    try:
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
    except ValueError:
        return False
    if max(r, g, b) - min(r, g, b) <= 8:
        return True
    return False
