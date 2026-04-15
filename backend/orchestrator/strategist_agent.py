"""Strategist agent: produces a design specification from a manuscript."""

from __future__ import annotations

from pathlib import Path

from backend.config import CANVAS_FORMATS, DESIGN_STYLES, settings
from backend.llm import LLMMessage, LLMProvider, LLMResponse

PROMPT_PATH = Path(__file__).parent / "prompts" / "strategist.md"


async def create_design_spec(
    manuscript: str,
    llm: LLMProvider,
    model: str,
    *,
    canvas_format: str = "ppt169",
    style: str = "academic",
    language: str = "en",
    detail_level: str = "normal",
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
    page_count = manuscript.count("---") + 1

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
        f"- Icon Library: tabler-outline (clean, professional)",
        f"- Typography: Sans-serif (Inter/Arial for body, bold for headings)",
        "\n## Hard Constraints",
        "- Respect the selected design style. Do not silently fall back to a default academic theme when another style is selected.",
        f"- The visible slide language must be `{language}`.",
        "- If language is `zh`, all slide titles, labels, bullets, and annotations must be in Simplified Chinese except proper nouns.",
        "- If language is `en`, all slide titles, labels, bullets, and annotations must be in English.",
        "- If language is `bilingual`, page titles and core bullets may include both Chinese and English, but each line must stay readable and deliberate.",
        "- Detail level `normal` should keep pages concise, `high` should allow moderately denser explanatory content, and `very_high` should accommodate richer explanations and fuller evidence coverage without becoming unreadable.",
    ]

    if ref_template:
        user_parts.append(
            f"\n## Design Spec Reference Template\n\n"
            f"Follow this template structure exactly:\n\n{ref_template}"
        )

    user_parts.append(
        "\n\nGenerate the complete design_spec.md following the template structure. "
        "All 11 sections (I through XI) must be present."
    )

    messages = [
        LLMMessage.system(system_prompt),
        LLMMessage.user("\n".join(user_parts)),
    ]

    response: LLMResponse = await llm.chat(
        messages, model, temperature=0.4, max_tokens=8192
    )
    return response.content
