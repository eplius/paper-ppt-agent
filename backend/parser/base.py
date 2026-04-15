"""Abstract base class for paper parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .paper_model import ParsedPaper


class PaperParser(ABC):
    """Abstract interface for paper parsing."""

    @abstractmethod
    async def parse(self, file_path: Path, output_dir: Path) -> ParsedPaper:
        """Parse a paper file and return structured data.

        Args:
            file_path: Path to the paper file (PDF or .tex).
            output_dir: Directory to write extracted images and intermediate files.

        Returns:
            ParsedPaper with extracted structure.
        """
        ...
