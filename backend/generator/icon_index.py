"""Icon semantic search using pre-built Gemini Embedding 2 index.

Provides fast cosine-similarity search over all icon libraries.
Index files (index.npz + index_meta.json) are pre-built and committed to Git.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-2"
EMBED_DIM = 768


def _np():
    """Lazy import numpy."""
    import numpy as np
    return np


def _genai():
    """Lazy import google.genai."""
    from google import genai
    from google.genai import types
    return genai, types


class IconIndex:
    """Pre-loaded icon vector index with semantic search."""

    def __init__(self, icons_dir: Path) -> None:
        self._icons_dir = icons_dir
        self._vectors = None  # np.ndarray | None
        self._meta: dict | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        npz_path = self._icons_dir / "index.npz"
        meta_path = self._icons_dir / "index_meta.json"

        if not npz_path.exists() or not meta_path.exists():
            logger.warning(
                "Icon index not found at %s. "
                "Run `python scripts/build_icon_index.py` to build it.",
                self._icons_dir,
            )
            self._loaded = True
            return

        np = _np()
        data = np.load(npz_path)
        self._vectors = data["vectors"]  # shape: (N, EMBED_DIM)
        self._meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._loaded = True
        logger.info(
            "Loaded icon index: %d icons, %d dimensions",
            self._meta["count"],
            self._meta["dimension"],
        )

    @property
    def is_loaded(self) -> bool:
        self._ensure_loaded()
        return self._vectors is not None

    @property
    def is_available(self) -> bool:
        """Alias for is_loaded."""
        return self.is_loaded

    def search(
        self,
        query: str,
        lib: str | None = None,
        k: int = 5,
    ) -> list[dict]:
        """Search icons by semantic similarity.

        Args:
            query: Natural language description of the desired icon.
            lib: Restrict to a specific library (chunk/tabler-filled/tabler-outline).
            k: Number of top results to return.

        Returns:
            List of dicts with keys: path, name, lib, category, tags, score.
            Empty list if index not loaded.
        """
        self._ensure_loaded()
        if self._vectors is None or self._meta is None:
            return []

        np = _np()

        # Embed query
        query_vec = self._embed_query(query)
        if query_vec is None:
            return []

        # Filter by library if specified
        icons = self._meta["icons"]
        if lib:
            mask = np.array([ic["lib"] == lib for ic in icons])
            indices = np.where(mask)[0]
            if len(indices) == 0:
                return []
            vecs = self._vectors[indices]
        else:
            indices = np.arange(len(icons))
            vecs = self._vectors

        # Cosine similarity (vectors are already normalized)
        sims = vecs @ query_vec

        # Top-k
        top_k_idx = np.argsort(sims)[-k:][::-1]

        results = []
        for idx in top_k_idx:
            real_idx = indices[idx]
            ic = icons[real_idx]
            results.append({
                "path": ic["path"],
                "name": ic["name"],
                "lib": ic["lib"],
                "category": ic.get("category", ""),
                "tags": ic.get("tags", []),
                "score": float(sims[idx]),
            })

        return results

    def _embed_query(self, query: str):
        """Embed a search query using Gemini Embedding 2. Returns np.ndarray or None."""
        np = _np()
        try:
            genai, types = _genai()
            client = genai.Client()
            formatted = f"task: search result | query: {query}"
            result = client.models.embed_content(
                model=EMBED_MODEL,
                contents=formatted,
                config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
            )
            vec = np.array(result.embeddings[0].values, dtype=np.float32)
            # Normalize (gemini-embedding-2 auto-normalizes, but ensure)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec
        except Exception:
            logger.exception("Failed to embed icon query: %s", query)
            return None

    def get_all_icons(self, lib: str | None = None) -> list[dict]:
        """Return all icon metadata, optionally filtered by library."""
        self._ensure_loaded()
        if self._meta is None:
            return []

        icons = self._meta["icons"]
        if lib:
            return [ic for ic in icons if ic["lib"] == lib]
        return icons


# Module-level singleton
_icon_index: IconIndex | None = None


def get_icon_index(icons_dir: Path | None = None) -> IconIndex:
    """Get or create the global IconIndex instance."""
    global _icon_index
    if _icon_index is None:
        if icons_dir is None:
            from backend.config import settings
            icons_dir = settings.icons_dir
        _icon_index = IconIndex(icons_dir)
    return _icon_index
