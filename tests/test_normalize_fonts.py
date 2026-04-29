from __future__ import annotations

from pathlib import Path

from backend.generator.svg_finalize.normalize_fonts import normalize_text_fonts_in_svg


def test_normalize_text_fonts_rewrites_css_stack_for_cjk_preview_parity(workspace_tmp: Path):
    svg_path = workspace_tmp / "fonts.svg"
    svg_path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <text x="64" y="80" font-family="Inter, Noto Sans CJK SC, Microsoft YaHei, Arial, sans-serif">轻量级可见性感知</text>
  <text x="64" y="120" font-family="Consolas, Monaco, Microsoft YaHei, Arial, sans-serif">S-KS = OKS^β</text>
</svg>
""",
        encoding="utf-8",
    )

    changed = normalize_text_fonts_in_svg(svg_path)
    content = svg_path.read_text(encoding="utf-8")

    assert changed == 2
    assert 'font-family="Microsoft YaHei"' in content
    assert 'font-family="Consolas"' in content
    assert "Noto Sans CJK SC" not in content
