"""Research agent: analyzes a parsed paper and produces a slide-structured manuscript."""

from __future__ import annotations

from pathlib import Path

from backend.llm import LLMMessage, LLMProvider, LLMResponse
from backend.orchestrator.provider_guidance import (
    deepseek_research_guidance,
    is_deepseek_provider,
)
from backend.parser.paper_model import ParsedPaper

PROMPT_PATH = Path(__file__).parent / "prompts" / "research.md"
DEEPSEEK_RESEARCH_MAX_TOKENS = 24576


def _language_guidance(language: str) -> str:
    guidance = {
        "zh": (
            "Write all slide titles, bullets, callouts, and presenter-facing content in Simplified Chinese. "
            "Keep paper titles, author names, model names, dataset names, and metric abbreviations in their original form when needed."
        ),
        "en": (
            "Write all slide titles, bullets, callouts, and presenter-facing content in English."
        ),
        "bilingual": (
            "Write slide titles and main bullets in bilingual Chinese and English where useful. "
            "Keep terminology aligned across both languages and avoid mixing untranslated fragments mid-sentence."
        ),
    }
    normalized = language.strip().lower()
    if normalized in guidance:
        return guidance[normalized]
    return (
        "Treat the requested language literally and write all slide titles, bullets, callouts, annotations, "
        f"and presenter-facing content in {language.strip() or 'the requested language'}. "
        "Keep proper nouns, paper titles, dataset names, model names, and metric abbreviations in their original form when needed."
    )


async def analyze_paper(
    paper: ParsedPaper,
    llm: LLMProvider,
    model: str,
    *,
    instruction: str = "",
    num_pages: int | None = None,
    language: str = "en",
    detail_level: str = "normal",
) -> str:
    """Analyze a paper and produce a slide-structured manuscript.

    Args:
        paper: Parsed paper data.
        llm: LLM provider instance.
        model: Model ID to use.
        instruction: Optional user instruction.
        num_pages: Target number of slides (None = auto).
        language: Target language for visible slide text.
        detail_level: Controls how detailed each slide manuscript should be.

    Returns:
        Manuscript markdown with --- page separators.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    # Build user message with paper content
    paper_md = paper.to_markdown()

    user_parts = [f"## Paper Content\n\n{paper_md}"]

    detail_guidance = {
        "normal": (
            "Produce a concise but faithful reading of the paper. Capture the core "
            "problem, method, evidence, and conclusions without overloading each slide."
        ),
        "high": (
            "Read the paper more deeply before writing. Surface the paper's reasoning, "
            "method design choices, assumptions, experimental logic, and non-obvious takeaways. "
            "Slides may be moderately denser when that improves understanding."
        ),
        "very_high": (
            "Perform a thorough reading rather than a surface summary. Explicitly cover the "
            "paper's motivation, mechanism, architecture, training or inference flow, assumptions, "
            "limitations, and the significance of the results. It is acceptable for slides to be "
            "denser and richer so the deck reflects a complete understanding of the paper."
        ),
    }

    if instruction:
        user_parts.append(f"\n## User Instruction\n\n{instruction}")

    if num_pages:
        user_parts.append(
            f"\n## Target Slides\n\n"
            f"Produce exactly {num_pages} slides. Use exactly {num_pages - 1} slide delimiter "
            "lines. A slide delimiter is a line containing only `---`. Do not use standalone "
            "`---` anywhere else."
        )
    else:
        user_parts.append(
            "\n## Target Slides: Auto-determine based on content "
            "(typically 8-15 slides for a standard paper)"
        )

    user_parts.append(
        "\n## Target Language\n\n"
        f"{language}\n\n"
        f"{_language_guidance(language)}"
    )

    user_parts.append(
        "\n## Detail Level\n\n"
        f"{detail_level}\n\n"
        f"{detail_guidance.get(detail_level, detail_guidance['normal'])}"
    )

    is_deepseek = is_deepseek_provider(llm, model)
    if is_deepseek:
        user_parts.append("\n" + deepseek_research_guidance(detail_level))

    user_parts.append(
        "\n\nPlease analyze this paper and produce a slide manuscript. "
        "Separate each slide only with a standalone `---` line. Start now."
    )

    messages = [
        LLMMessage.system(system_prompt),
        LLMMessage.user("\n".join(user_parts)),
    ]

    response: LLMResponse = await llm.chat(
        messages,
        model,
        temperature=0.5,
        max_tokens=DEEPSEEK_RESEARCH_MAX_TOKENS if is_deepseek else None,
    )
    return response.content


async def revise_manuscript(
    manuscript: str,
    llm: LLMProvider,
    model: str,
    *,
    feedback_history: list[str],
    language: str = "en",
    detail_level: str = "normal",
    target_pages: list[int] | None = None,
    allow_structure_changes: bool = False,
) -> str:
    """Revise an existing manuscript using user feedback.

    When ``allow_structure_changes`` is false, preserve slide order/count and
    revise only the requested scope. When true, the model may insert, remove,
    or reorder slides to satisfy the feedback.
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    target_pages = sorted({page for page in (target_pages or []) if page > 0})

    scope_guidance = (
        "Revise only the requested slide pages. Keep all other slides unchanged unless a "
        "small consistency edit is strictly necessary."
        if target_pages
        else "Revise the full deck while preserving its overall structure unless the feedback requires otherwise."
    )
    structure_guidance = (
        "You MAY change slide count, insert new slides, delete slides, split dense slides, or reorder slides "
        "when that is the best way to satisfy the feedback."
        if allow_structure_changes
        else "You MUST preserve slide count and slide order. Do not insert, delete, or reorder slides."
    )

    feedback_block = "\n\n".join(
        f"### Round {index}\n{feedback.strip()}"
        for index, feedback in enumerate(feedback_history, start=1)
        if feedback.strip()
    )

    user_prompt = (
        f"## Existing Manuscript\n\n{manuscript}\n\n"
        f"## Target Language\n\n{language}\n\n"
        f"## Detail Level\n\n{detail_level}\n\n"
        f"## Requested Scope\n\n"
        f"- Target pages: {', '.join(map(str, target_pages)) if target_pages else 'all pages'}\n"
        f"- Scope rule: {scope_guidance}\n"
        f"- Structure rule: {structure_guidance}\n\n"
        f"## User Feedback History\n\n{feedback_block or 'No feedback provided.'}\n\n"
        "Revise the manuscript and output the full updated slide manuscript only. "
        "Keep `---` separators between slides."
    )

    response: LLMResponse = await llm.chat(
        [LLMMessage.system(system_prompt), LLMMessage.user(user_prompt)],
        model,
        temperature=0.4,
        max_tokens=16384,
    )
    return response.content
