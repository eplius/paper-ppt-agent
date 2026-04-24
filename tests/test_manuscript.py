from __future__ import annotations

from backend.orchestrator.manuscript import count_manuscript_pages, split_manuscript_pages


def test_manuscript_page_count_ignores_markdown_table_separator_rows():
    manuscript = """# Slide One

| Metric | Value |
|--------|-------|
| Hit@1 | 79.5% |

---

# Slide Two

Body text with an inline range 2024---2026.

---

# Slide Three
"""

    pages = split_manuscript_pages(manuscript)

    assert count_manuscript_pages(manuscript) == 3
    assert len(pages) == 3
    assert "|--------|-------|" in pages[0]
    assert "2024---2026" in pages[1]
