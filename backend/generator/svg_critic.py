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
_TEXT_OPEN_RE = re.compile(r"<text\b[^>]*>", re.IGNORECASE)
_TEXT_CLOSE_RE = re.compile(r"</text\s*>", re.IGNORECASE)

# Elements explicitly forbidden by executor.md — mirrored here so the
# critic fails fast instead of relying on LLM self-discipline.
_FORBIDDEN_TAGS = {"mask", "style", "clipPath", "filter", "foreignObject"}
# `use` is allowed for icon references; `image` allowed for raster.


def _count_nested_text(svg_content: str) -> int:
    """Return the number of inner <text> opens found inside another open <text>."""
    n = len(svg_content)
    i = 0
    depth = 0
    nested = 0
    while i < n:
        m_open = _TEXT_OPEN_RE.search(svg_content, i)
        m_close = _TEXT_CLOSE_RE.search(svg_content, i)
        next_open = m_open.start() if m_open else n + 1
        next_close = m_close.start() if m_close else n + 1
        if next_open == n + 1 and next_close == n + 1:
            break
        if next_open < next_close and m_open is not None:
            if depth >= 1:
                nested += 1
            depth += 1
            i = m_open.end()
        elif m_close is not None:
            if depth > 0:
                depth -= 1
            i = m_close.end()
        else:
            break
    return nested


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

    # Accent-line-under-title detector.
    # A near-horizontal line/thin rect within this many user units below a
    # title text baseline counts as a forbidden "AI-slide accent line".
    accent_line_max_gap: float = 24.0
    # A rect/line is considered "thin and horizontal" when height <= this and
    # width >= title_text_width * accent_line_min_width_ratio.
    accent_line_max_thickness: float = 6.0
    accent_line_min_width_ratio: float = 0.5

    # Low-contrast detector.
    # WCAG-style relative-luminance ratio threshold. Anything below 3.0 is
    # flagged. We pick 3.0 (not 4.5) to avoid over-flagging stylized large
    # titles where designers commonly accept slightly looser contrast.
    min_contrast_ratio: float = 3.0

    # Z-order occlusion detector. A visible shape drawn after a text element
    # and covering at least this fraction of the estimated text bbox is treated
    # as a likely overlap. This is intentionally conservative so legitimate
    # chip/card backgrounds, which are normally drawn before their labels, do
    # not trip the rule.
    text_cover_min_ratio: float = 0.18


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

    nested_count = _count_nested_text(svg_content)
    if nested_count > 0:
        violations.append(Violation(
            rule="nested_text",
            severity="error",
            detail=(
                f"Found {nested_count} `<text>` element(s) nested inside another "
                f"`<text>`. SVG forbids this and browsers/PPT export can scramble "
                f"the result. Use `<tspan>` for inline emphasis instead."
            ),
        ))

    # 1. Parse SVG (lenient).
    try:
        root = ET.fromstring(svg_content)
    except ET.ParseError as exc:
        return CriticReport(
            passed=False,
            violations=[Violation("xml_parse", "error", f"SVG is not parseable XML: {exc}")],
        )

    canvas = _parse_viewbox(root)
    ordered_elements = list(_iter_all(root))
    element_order = {id(el): index for index, el in enumerate(ordered_elements)}

    # 2. Forbidden elements.
    for el in _iter_all(root):
        tag = _strip_ns(el.tag)
        if tag == "span":
            violations.append(
                Violation(
                    rule="html_span_in_svg_text",
                    severity="error",
                    detail=(
                        "`<span>` is an HTML element and is invalid inside SVG text. "
                        "Use SVG `<tspan>` for inline styling."
                    ),
                    element=_element_identifier(el),
                )
            )
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
    text_boxes: list[tuple[int, ET.Element, tuple[float, float, float, float]]] = []
    for el in ordered_elements:
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
        text_boxes.append((element_order[id(el)], el, bbox))

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
    for i, (_, el_a, box_a) in enumerate(text_boxes):
        for j in range(i + 1, len(text_boxes)):
            _, el_b, box_b = text_boxes[j]
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

    # 4b. Accent-line-under-title detector.
    #
    # Find titles (the largest font_size text on the page, or any text whose
    # font-size >= min_title_font_size). Then look for any <line> or thin
    # horizontal <rect> sitting directly below it within the configured gap.
    title_boxes: list[tuple[ET.Element, tuple[float, float, float, float]]] = [
        (el, bbox)
        for _, el, bbox in text_boxes
        if _font_size_of(el, 16.0) >= cfg.min_title_font_size
    ]
    if title_boxes:
        for el, bbox in _iter_horizontal_strokes(root):
            for title_entry in title_boxes:
                title_bbox = title_entry[1]
                if _is_accent_line_under_title(
                    title_bbox, bbox, cfg
                ):
                    violations.append(
                        Violation(
                            rule="accent_line_under_title",
                            severity="warning",
                            detail=(
                                "A near-horizontal line/thin rectangle is positioned "
                                "directly under a title. This is a hallmark of AI-generated "
                                "slides. Remove it and use whitespace, a left-side accent "
                                "bar, or a tinted background block instead."
                            ),
                            element=_element_identifier(el),
                            bbox=bbox,
                        )
                    )
                    break

    # 4c. Low-contrast detector.
    #
    # For each text element, find the nearest underlying filled shape (rect /
    # path) whose bbox encloses the text bbox; compare WCAG relative
    # luminances. If the surrounding shape has no fill we fall back to the
    # SVG root background, which we infer from the first full-canvas <rect>
    # if present, otherwise assume white.
    if canvas:
        bg_layers = _collect_background_layers(root, canvas)
        for _, el, bbox in text_boxes:
            text_color = _resolve_text_color(el)
            if text_color is None:
                continue
            bg_color = _resolve_background_under(bbox, bg_layers)
            if bg_color is None:
                continue
            ratio = _contrast_ratio(text_color, bg_color)
            if ratio < cfg.min_contrast_ratio:
                violations.append(
                    Violation(
                        rule="low_contrast",
                        severity="warning",
                        detail=(
                            f"Text color #{text_color} on background #{bg_color} has "
                            f"contrast ratio {ratio:.2f} (minimum {cfg.min_contrast_ratio:.1f}). "
                            "Increase contrast: use a darker text color on light fills, "
                            "or a lighter text color on dark fills."
                        ),
                        element=_element_identifier(el),
                        bbox=bbox,
                    )
                )

    # 4d. Text covered by later-drawn shapes.
    #
    # This catches the common failure where badges, buttons, or diagram blocks
    # are placed on top of prose. It only considers shapes that appear later in
    # document order, so normal backgrounds drawn before their labels are not
    # flagged.
    covering_shapes = _collect_covering_shapes(root, element_order)
    for text_order, text_el, text_bbox in text_boxes:
        for shape_order, shape_el, shape_bbox in covering_shapes:
            if shape_order <= text_order:
                continue
            coverage = _coverage_ratio(text_bbox, shape_bbox)
            if coverage < cfg.text_cover_min_ratio:
                continue
            violations.append(
                Violation(
                    rule="shape_covers_text",
                    severity="error",
                    detail=(
                        "A later-drawn visible shape overlaps this text enough to "
                        "cover or obscure it. Move the shape away, resize it, or "
                        "increase the text/container spacing."
                    ),
                    element=_element_identifier(text_el),
                    bbox=text_bbox,
                )
            )
            break

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


# ── Accent-line-under-title helpers ──────────────────────────────────────────


def _iter_horizontal_strokes(
    root: ET.Element,
) -> list[tuple[ET.Element, tuple[float, float, float, float]]]:
    """Find <line> and thin horizontal <rect>/path-h elements with bboxes."""
    out: list[tuple[ET.Element, tuple[float, float, float, float]]] = []
    for el in _iter_all(root):
        tag = _strip_ns(el.tag)
        if tag == "line":
            x1 = _float_attr(el, "x1", 0.0)
            y1 = _float_attr(el, "y1", 0.0)
            x2 = _float_attr(el, "x2", 0.0)
            y2 = _float_attr(el, "y2", 0.0)
            if abs(y1 - y2) <= 2.0 and abs(x2 - x1) > 1.0:
                bbox = (min(x1, x2), min(y1, y2) - 1.0, abs(x2 - x1), 2.0)
                out.append((el, bbox))
        elif tag == "rect":
            x = _float_attr(el, "x", 0.0)
            y = _float_attr(el, "y", 0.0)
            w = _float_attr(el, "width", 0.0)
            h = _float_attr(el, "height", 0.0)
            if w > 0.0 and 0.0 < h <= 8.0 and w / max(h, 0.5) >= 8.0:
                out.append((el, (x, y, w, h)))
    return out


def _is_accent_line_under_title(
    title_bbox: tuple[float, float, float, float],
    line_bbox: tuple[float, float, float, float],
    cfg: CriticConfig,
) -> bool:
    """Decide whether `line_bbox` looks like a decorative line under a title."""
    tx, ty, tw, th = title_bbox
    lx, ly, lw, lh = line_bbox
    if lh > cfg.accent_line_max_thickness:
        return False
    title_bottom = ty + th
    gap = ly - title_bottom
    if gap < -2.0 or gap > cfg.accent_line_max_gap:
        return False
    # Horizontal proximity: the line should overlap or sit close to the
    # title horizontally.
    line_right = lx + lw
    title_right = tx + tw
    horiz_overlap = max(0.0, min(line_right, title_right) - max(lx, tx))
    if horiz_overlap < tw * 0.3:
        return False
    # Width sanity: a left-side accent BAR (very short, well to the left of
    # the title) should NOT be flagged. Only flag lines wide enough to read
    # as "underline."
    if lw < tw * cfg.accent_line_min_width_ratio:
        return False
    return True


# ── Low-contrast helpers ─────────────────────────────────────────────────────


def _resolve_text_color(el: ET.Element) -> str | None:
    """Return the text fill as a 6-char lowercase hex, or None if unknown."""
    fill = (el.get("fill") or "").strip()
    if fill.startswith("#"):
        return _normalize_hex(fill)
    style = el.get("style") or ""
    m = re.search(r"fill\s*:\s*#([0-9a-fA-F]{3,6})", style)
    if m:
        return _normalize_hex(m.group(1))
    # Default SVG fill is black.
    return "000000"


def _collect_background_layers(
    root: ET.Element,
    canvas: tuple[float, float],
) -> list[tuple[tuple[float, float, float, float], str]]:
    """Collect filled rects ordered front-to-back (later in document = on top)."""
    layers: list[tuple[tuple[float, float, float, float], str]] = []
    cw, ch = canvas
    # Implicit canvas background.
    layers.append(((0.0, 0.0, cw, ch), "ffffff"))
    for el in _iter_all(root):
        tag = _strip_ns(el.tag)
        if tag != "rect":
            continue
        fill = (el.get("fill") or "").strip()
        hex_color: str | None = None
        if fill.startswith("#"):
            hex_color = _normalize_hex(fill)
        else:
            style = el.get("style") or ""
            m = re.search(r"fill\s*:\s*#([0-9a-fA-F]{3,6})", style)
            if m:
                hex_color = _normalize_hex(m.group(1))
        if hex_color is None or len(hex_color) != 6:
            continue
        x = _float_attr(el, "x", 0.0)
        y = _float_attr(el, "y", 0.0)
        w = _float_attr(el, "width", 0.0)
        h = _float_attr(el, "height", 0.0)
        if w <= 0 or h <= 0:
            continue
        layers.append(((x, y, w, h), hex_color))
    return layers


def _resolve_background_under(
    text_bbox: tuple[float, float, float, float],
    layers: list[tuple[tuple[float, float, float, float], str]],
) -> str | None:
    """Return the topmost rect color whose bbox encloses the text bbox."""
    tx, ty, tw, th = text_bbox
    cx = tx + tw / 2.0
    cy = ty + th / 2.0
    best: str | None = None
    for (x, y, w, h), color in layers:
        if x <= cx <= x + w and y <= cy <= y + h:
            best = color  # later layers in doc order win
    return best


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG 2.x contrast ratio between two 6-char hex colors."""
    def _luminance(hex_value: str) -> float:
        r = int(hex_value[0:2], 16) / 255.0
        g = int(hex_value[2:4], 16) / 255.0
        b = int(hex_value[4:6], 16) / 255.0

        def _ch(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)

    try:
        l1 = _luminance(fg_hex)
        l2 = _luminance(bg_hex)
    except ValueError:
        return 21.0  # Treat parse failure as "fine" to avoid false positives.
    lighter, darker = (l1, l2) if l1 > l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


# ── Z-order text occlusion helpers ───────────────────────────────────────────


def _collect_covering_shapes(
    root: ET.Element,
    element_order: dict[int, int],
) -> list[tuple[int, ET.Element, tuple[float, float, float, float]]]:
    """Collect simple visible shapes that can cover earlier text."""
    shapes: list[tuple[int, ET.Element, tuple[float, float, float, float]]] = []
    for el in _iter_all(root):
        if not _is_visible_filled_shape(el):
            continue
        bbox = _shape_bbox(el)
        if bbox is None:
            continue
        x, y, w, h = bbox
        if w <= 0 or h <= 0 or w * h < 64:
            continue
        shapes.append((element_order.get(id(el), 0), el, bbox))
    return shapes


def _is_visible_filled_shape(el: ET.Element) -> bool:
    tag = _strip_ns(el.tag)
    if tag not in {"rect", "circle", "ellipse"}:
        return False
    fill = (el.get("fill") or "").strip().lower()
    style = el.get("style") or ""
    if not fill:
        fill_match = re.search(r"fill\s*:\s*([^;]+)", style)
        fill = fill_match.group(1).strip().lower() if fill_match else "black"
    if fill in {"none", "transparent"}:
        return False
    opacity_values = [el.get("opacity"), el.get("fill-opacity")]
    for raw in opacity_values:
        if raw is None:
            continue
        try:
            if float(raw) < 0.18:
                return False
        except ValueError:
            pass
    opacity_match = re.search(r"(?:^|;)\s*(?:fill-)?opacity\s*:\s*([0-9.]+)", style)
    if opacity_match:
        try:
            if float(opacity_match.group(1)) < 0.18:
                return False
        except ValueError:
            pass
    return True


def _shape_bbox(el: ET.Element) -> tuple[float, float, float, float] | None:
    tag = _strip_ns(el.tag)
    if tag == "rect":
        x = _float_attr(el, "x", 0.0)
        y = _float_attr(el, "y", 0.0)
        w = _float_attr(el, "width", 0.0)
        h = _float_attr(el, "height", 0.0)
        return x, y, w, h
    if tag == "circle":
        cx = _float_attr(el, "cx", 0.0)
        cy = _float_attr(el, "cy", 0.0)
        r = _float_attr(el, "r", 0.0)
        return cx - r, cy - r, r * 2, r * 2
    if tag == "ellipse":
        cx = _float_attr(el, "cx", 0.0)
        cy = _float_attr(el, "cy", 0.0)
        rx = _float_attr(el, "rx", 0.0)
        ry = _float_attr(el, "ry", 0.0)
        return cx - rx, cy - ry, rx * 2, ry * 2
    return None


def _coverage_ratio(
    target: tuple[float, float, float, float],
    cover: tuple[float, float, float, float],
) -> float:
    tx, ty, tw, th = target
    cx, cy, cw, ch = cover
    if tw <= 0 or th <= 0:
        return 0.0
    ix0 = max(tx, cx)
    iy0 = max(ty, cy)
    ix1 = min(tx + tw, cx + cw)
    iy1 = min(ty + th, cy + ch)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return ((ix1 - ix0) * (iy1 - iy0)) / (tw * th)
