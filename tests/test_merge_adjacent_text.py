from __future__ import annotations

from pathlib import Path

from backend.generator.svg_finalize.merge_adjacent_text import merge_adjacent_text_in_svg


def test_merge_adjacent_text_merges_inline_formula_fragments(workspace_tmp: Path):
    svg_path = workspace_tmp / "formula.svg"
    svg_path.write_text(
        """<?xml version='1.0' encoding='utf-8'?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <g>
    <text x="980" y="242" font-size="22" text-anchor="middle">f</text>
    <text x="980" y="235" font-size="16" text-anchor="middle">(t)</text>
    <text x="980" y="242" font-size="22" text-anchor="middle">= f</text>
    <text x="980" y="235" font-size="16" text-anchor="middle">(t-1)</text>
    <text x="980" y="242" font-size="22" text-anchor="middle">⊙ m</text>
  </g>
</svg>
""",
        encoding="utf-8",
    )

    merged = merge_adjacent_text_in_svg(svg_path)
    content = svg_path.read_text(encoding="utf-8")

    assert merged == 1
    assert content.count("<text") == 1
    assert "(t-1)" in content
    assert "⊙ m" in content
