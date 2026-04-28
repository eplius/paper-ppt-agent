from __future__ import annotations

from pathlib import Path

from backend.generator.svg_critic import check_svg
from backend.generator.svg_finalize.repair_svg import repair_svg_file


def test_critic_rejects_html_span_inside_svg_text() -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="76" y="180" font-size="18">Pixel interpolation<span fill="#64748B"> - MAE 0.3598</span></text>
</svg>"""

    report = check_svg(svg)

    assert not report.passed
    assert any(v.rule == "html_span_in_svg_text" for v in report.violations)


def test_critic_rejects_nested_text_elements() -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="76" y="180" font-size="18">Pixel interpolation<text x="76" y="210">MAE 0.3598</text></text>
</svg>"""

    report = check_svg(svg)

    assert not report.passed
    assert any(v.rule == "nested_text" for v in report.violations)


def test_repair_converts_html_span_inside_svg_text(workspace_tmp: Path) -> None:
    svg_path = workspace_tmp / "span.svg"
    svg_path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="76" y="180" font-size="18">Pixel interpolation<span fill="#64748B"> - MAE 0.3598</span></text>
</svg>""",
        encoding="utf-8",
    )

    changed = repair_svg_file(svg_path)
    content = svg_path.read_text(encoding="utf-8")

    assert changed == 1
    assert "<span" not in content
    assert "</span>" not in content
    assert '<tspan fill="#64748B"> - MAE 0.3598</tspan>' in content
