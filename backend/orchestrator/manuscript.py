"""Helpers for slide-structured manuscript Markdown."""

from __future__ import annotations

import re

_SLIDE_DELIMITER_RE = re.compile(r"(?m)^\s*---\s*$")


def split_manuscript_pages(manuscript: str) -> list[str]:
    """Split manuscript Markdown on standalone slide delimiter lines only."""
    return [page.strip() for page in _SLIDE_DELIMITER_RE.split(manuscript) if page.strip()]


def count_manuscript_pages(manuscript: str) -> int:
    """Return the number of actual slide pages in a manuscript."""
    return len(split_manuscript_pages(manuscript))
