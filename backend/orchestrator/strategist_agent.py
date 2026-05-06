"""Strategist agent: produces a design specification from a manuscript."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.config import CANVAS_FORMATS, DESIGN_STYLES, settings
from backend.generator.icon_index import get_icon_index
from backend.llm import LLMMessage, LLMProvider, LLMResponse
from backend.orchestrator.manuscript import count_manuscript_pages
from backend.orchestrator.provider_guidance import (
    deepseek_strategy_guidance,
    is_deepseek_provider,
)

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "strategist.md"
DESIGN_SPEC_MAX_TOKENS = 24576
MAX_DESIGN_SPEC_ATTEMPTS = 2

# Number of icon candidates to pre-select via RAG
ICON_CANDIDATE_COUNT = 60
# Number of search queries to extract from manuscript
ICON_QUERY_COUNT = 12


def _extract_icon_queries(manuscript: str) -> list[str]:
    """Extract semantic queries for icon search from manuscript content.

    Parses page titles and key concepts from the slide-structured manuscript
    to generate targeted icon search queries.
    """
    queries: list[str] = []

    # Extract page titles (## headings)
    for m in re.finditer(r"^##\s+(.+)$", manuscript, re.MULTILINE):
        title = m.group(1).strip()
        # Clean up numbering like "1. " or "Page 1: "
        title = re.sub(r"^\d+[\.\):\s]+", "", title).strip()
        if title and len(title) > 2:
            queries.append(title)

    # Extract bold concepts (**text**)
    for m in re.finditer(r"\*\*([^*]{3,50})\*\*", manuscript):
        concept = m.group(1).strip()
        if concept not in queries:
            queries.append(concept)

    return queries[:ICON_QUERY_COUNT]


def _retrieve_icon_candidates(
    manuscript: str,
    lib: str,
) -> str:
    """Retrieve icon candidates for the chosen library using RAG.

    Returns a formatted string listing candidate icons for injection
    into the strategist prompt.
    """
    index = get_icon_index()
    if not index.is_available:
        logger.warning("Icon index not available, skipping RAG retrieval")
        return ""

    queries = _extract_icon_queries(manuscript)
    if not queries:
        return ""

    # Collect candidates from all queries
    seen_paths: set[str] = set()
    candidates: list[dict] = []

    for query in queries:
        results = index.search(query, lib=lib, k=5)
        for r in results:
            if r["path"] not in seen_paths:
                seen_paths.add(r["path"])
                candidates.append(r)

    # Sort by score descending, take top N
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:ICON_CANDIDATE_COUNT]

    if not candidates:
        return ""

    # Format as a compact table for prompt injection
    lines = [
        f"\n## Pre-selected Icon Candidates ({lib} library, {len(candidates)} icons)",
        "",
        "These icons were retrieved by semantic search from the full icon index "
        "based on your manuscript content. **You MUST choose icons from this list.**",
        "",
        "| # | Icon Path | Category | Tags |",
        "|---|-----------|----------|------|",
    ]

    for i, c in enumerate(candidates, 1):
        tags = ", ".join(c.get("tags", [])[:5])
        cat = c.get("category", "-")
        lines.append(f"| {i} | `{c['path']}` | {cat} | {tags} |")

    lines.append("")
    lines.append(
        "Use the icon path with the `<use data-icon=\"...\"/>` placeholder syntax. "
        "Example: `<use data-icon=\"chart-bar\" x=\"100\" y=\"200\" width=\"32\" height=\"32\" fill=\"#0076A8\"/>`"
    )

    return "\n".join(lines)


def _design_spec_validation_error(content: str) -> str | None:
    text = content.strip()
    if len(text) < 1200:
        return f"design_spec.md is too short ({len(text)} characters)"

    required = {
        "I": "Project Information",
        "II": "Canvas Specification",
        "III": "Visual Theme",
        "IX": "Content Outline",
        "XI": "Technical Constraints",
    }
    for roman, title in required.items():
        pattern = rf"(?im)^#+\s*{roman}\.\s+.*{re.escape(title)}"
        if not re.search(pattern, text):
            return f"design_spec.md is missing section {roman}. {title}"
    return None


def _language_constraint(language: str) -> str:
    normalized = language.strip().lower()
    if normalized == "zh":
        return "All slide titles, labels, bullets, and annotations must be in Simplified Chinese except proper nouns."
    if normalized == "en":
        return "All slide titles, labels, bullets, and annotations must be in English."
    if normalized == "bilingual":
        return (
            "Page titles and core bullets may include both Chinese and English, but each line must stay readable and deliberate."
        )
    return (
        f"Treat `{language}` as a literal target-language request and keep all visible slide text fully in {language}, "
        "except proper nouns that must remain in their original form."
    )


async def create_design_spec(
    manuscript: str,
    llm: LLMProvider,
    model: str,
    *,
    canvas_format: str = "ppt169",
    style: str = "academic",
    language: str = "en",
    detail_level: str = "normal",
    icon_library: str = "chunk",
    style_overrides: dict | None = None,
    enable_icon_rag: bool = True,
) -> str:
    """Generate a design specification from a manuscript.

    Args:
        manuscript: Slide-structured manuscript markdown.
        llm: LLM provider instance.
        model: Model ID to use.
        canvas_format: Canvas format key.
        style: Design style key.
        language: Output language.
        detail_level: Requested content depth and density target.
        icon_library: Icon library to use (chunk/tabler-filled/tabler-outline).

    Returns:
        Design specification markdown (design_spec.md content).
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    # Load the design spec reference template
    ref_path = settings.templates_dir / "design_spec_reference.md"
    ref_template = ""
    if ref_path.exists():
        ref_template = ref_path.read_text(encoding="utf-8")

    fmt = CANVAS_FORMATS.get(canvas_format, CANVAS_FORMATS["ppt169"])
    style_info = DESIGN_STYLES.get(style, DESIGN_STYLES["academic"])

    # Count pages in manuscript
    page_count = count_manuscript_pages(manuscript)

    user_parts = [
        f"## Manuscript\n\n{manuscript}",
        f"\n## Canvas Format: {fmt['name']} ({fmt['ratio']}), viewBox: `{fmt['viewbox']}`",
        f"\n## Design Style: {style_info['name']}",
        f"\n## Page Count: {page_count}",
        f"\n## Language: {language}",
        f"\n## Detail Level: {detail_level}",
        f"\n## Pre-resolved Confirmations",
        f"- Canvas Format: {fmt['name']}",
        f"- Page Count: {page_count}",
        f"- Audience: Academic/Research community",
        f"- Style: {style_info['name']}",
        f"- Primary Color: {style_info['primary']}",
        f"- Accent Color: {style_info['accent']}",
        "- Compact symbols are optional; use only when they carry clear semantic value.",
        f"- Typography: Sans-serif (Inter/Arial for body, bold for headings)",
        "\n## Hard Constraints",
        "- Respect the selected design style. Do not silently fall back to a default academic theme when another style is selected.",
        f"- The visible slide language must be `{language}`.",
        f"- {_language_constraint(language)}",
        "- Detail level `normal` should keep pages concise, `high` should allow moderately denser explanatory content, and `very_high` should accommodate richer explanations and fuller evidence coverage without becoming unreadable.",
    ]

    if is_deepseek_provider(llm, model):
        user_parts.append("\n" + deepseek_strategy_guidance(detail_level))

    # RAG icon retrieval: pre-select candidates from the full icon index
    icon_candidates_block = ""
    if enable_icon_rag:
        icon_candidates_block = _retrieve_icon_candidates(manuscript, icon_library)
    if icon_candidates_block:
        user_parts.append(icon_candidates_block)

    if style_overrides:
        override_lines = ["\n## Style Overrides (must override defaults)"]
        palette = style_overrides.get("palette") if isinstance(style_overrides, dict) else None
        font = style_overrides.get("font") if isinstance(style_overrides, dict) else None
        density = style_overrides.get("density") if isinstance(style_overrides, dict) else None
        if palette:
            try:
                colors = ", ".join(str(c) for c in palette if c)
            except TypeError:
                colors = ""
            if colors:
                override_lines.append(
                    f"- Palette: {colors} — use these as the primary / accent / background colors "
                    f"in every slide's color system. Do NOT fall back to the default style colors."
                )
        if font:
            override_lines.append(
                f"- Font-family: `{font}` — use this family for every text element throughout."
            )
        if density:
            override_lines.append(
                f"- Layout density: `{density}` — respect this target spacing/whitespace aesthetic."
            )
        user_parts.append("\n".join(override_lines))

    if ref_template:
        user_parts.append(
            f"\n## Design Spec Reference Template\n\n"
            f"Follow this template structure exactly:\n\n{ref_template}"
        )

    user_parts.append(
        "\n\nGenerate the complete design_spec.md following the template structure. "
        "All 11 sections (I through XI) must be present."
    )

    base_messages = [
        LLMMessage.system(system_prompt),
        LLMMessage.user("\n".join(user_parts)),
    ]

    last_error = ""
    for attempt in range(1, MAX_DESIGN_SPEC_ATTEMPTS + 1):
        messages = list(base_messages)
        if last_error:
            messages.append(
                LLMMessage.user(
                    "The previous design_spec.md response was invalid: "
                    f"{last_error}. Regenerate the complete design_spec.md now. "
                    "Do not return an empty response. Include all required sections I through XI."
                )
            )

        response: LLMResponse = await llm.chat(
            messages,
            model,
            temperature=0.25 if attempt > 1 else 0.4,
            max_tokens=DESIGN_SPEC_MAX_TOKENS,
        )
        content = response.content.strip()
        error = _design_spec_validation_error(content)
        if error is None:
            return content
        last_error = error

    raise RuntimeError(f"Invalid design specification from strategist: {last_error}")
