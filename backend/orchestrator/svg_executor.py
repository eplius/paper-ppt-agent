"""SVG Executor agent: generates SVG page code from design spec.

The executor runs a page-by-page generation loop. Each page is checked by
the static :mod:`backend.generator.svg_critic` before being accepted. If
the critic finds violations, a targeted repair prompt is fed back to the
LLM (bounded retries, with slightly lower temperature on each retry) so
that regeneration is *informed* rather than blind.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from backend.config import settings
from backend.generator.svg_critic import CriticConfig, CriticReport, check_svg
from backend.llm import LLMMessage, LLMProvider, LLMResponse
from backend.orchestrator.manuscript import split_manuscript_pages
from backend.usage.tracker import reset_usage_context, set_usage_context

PROMPT_PATH = Path(__file__).parent / "prompts" / "executor.md"

# How many repair attempts we're willing to spend per page. 1 = initial only.
MAX_REPAIR_ATTEMPTS = 2

# Initial response plus bounded same-page retries when no SVG can be extracted.
MAX_SVG_EXTRACTION_ATTEMPTS = 3

CriticCallback = Callable[[int, int, CriticReport], Awaitable[None]]


async def generate_svg_pages(
    design_spec: str,
    manuscript: str,
    project_dir: Path,
    llm: LLMProvider,
    model: str,
    *,
    style: str = "academic",
    language: str = "en",
    detail_level: str = "normal",
    extra_instruction: str = "",
    target_pages: set[int] | None = None,
    critic_config: CriticConfig | None = None,
    on_critic: CriticCallback | None = None,
) -> AsyncIterator[tuple[int, str]]:
    """Generate SVG code for each slide page sequentially.

    Every generated page passes through the static critic. When violations
    are detected, we send the critic's structured repair prompt back to
    the model (up to ``MAX_REPAIR_ATTEMPTS`` times). If the page still
    fails, the best available SVG is yielded anyway so the user can see
    what happened and intervene via the refine loop.

    Yields:
        Tuples of (page_number, svg_content).
    """
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    # Load shared standards
    standards_path = settings.references_dir / "shared-standards.md"
    standards = ""
    if standards_path.exists():
        standards = standards_path.read_text(encoding="utf-8")

    # Parse pages from manuscript
    pages = split_manuscript_pages(manuscript)
    svg_output_dir = project_dir / "svg_output"
    svg_output_dir.mkdir(parents=True, exist_ok=True)

    # Build context that accumulates across pages
    extra_block = f"\n\n{extra_instruction}" if extra_instruction else ""
    conversation: list[LLMMessage] = [
        LLMMessage.system(system_prompt),
        LLMMessage.user(
            f"## Design Specification\n\n{design_spec}\n\n"
            f"## SVG Technical Standards\n\n{standards}\n\n"
            f"## Fixed Runtime Configuration\n\n"
            f"- Selected style preset: {style}\n"
            f"- Selected language: {language}\n"
            f"- Selected detail level: {detail_level}\n"
            f"- Do not replace the requested style with another preset.\n"
            f"- All visible SVG text must follow the selected language unless a proper noun must stay in its original form.\n\n"
            f"Total pages to generate: {len(pages)}\n\n"
            f"You will generate SVG code for each page sequentially. "
            f"I will provide the content for each page one at a time."
            f"{extra_block}"
        ),
        LLMMessage.assistant(
            "Understood. I have the design specification and technical constraints. "
            "Please provide the content for page 1."
        ),
    ]

    for i, page_content in enumerate(pages):
        page_num = i + 1
        if target_pages is not None and page_num not in target_pages:
            continue
        page_name = _make_page_name(page_num, page_content)

        conversation.append(
            LLMMessage.user(
                f"## Page {page_num}/{len(pages)}: {page_name}\n\n"
                f"{page_content}\n\n"
                f"## Runtime Reminders\n"
                f"- Style preset: {style}\n"
                f"- Language: {language}\n"
                f"- Detail level: {detail_level}\n"
                f"- Keep all visible text in the requested language.\n\n"
                f"Generate the complete SVG code for this page. "
                f"Output ONLY the SVG code, wrapped in ```svg code block."
            )
        )

        # Attempt 1: initial generation
        snapshot = set_usage_context(stage="generation", page=page_num, attempt=1)
        try:
            response: LLMResponse = await llm.chat(
                conversation, model, temperature=0.3, max_tokens=16384
            )
        finally:
            reset_usage_context(snapshot)

        svg_content = _extract_svg(response.content)
        for extraction_attempt in range(2, MAX_SVG_EXTRACTION_ATTEMPTS + 1):
            if svg_content:
                break
            conversation.append(LLMMessage.assistant(response.content))
            conversation.append(
                LLMMessage.user(
                    _build_svg_extraction_retry_prompt(
                        page_num=page_num,
                        total_pages=len(pages),
                        page_name=page_name,
                        page_content=page_content,
                        attempt=extraction_attempt,
                    )
                )
            )
            snapshot = set_usage_context(
                stage="generation", page=page_num, attempt=extraction_attempt
            )
            try:
                response = await llm.chat(
                    conversation, model, temperature=0.2, max_tokens=16384
                )
            finally:
                reset_usage_context(snapshot)
            svg_content = _extract_svg(response.content)

        # Repair loop driven by the static critic.
        if svg_content:
            conversation.append(LLMMessage.assistant(f"```svg\n{svg_content}\n```"))

            best_svg = svg_content
            for attempt in range(2, MAX_REPAIR_ATTEMPTS + 2):
                report = check_svg(svg_content, critic_config)
                if on_critic is not None:
                    await on_critic(page_num, attempt - 1, report)
                if report.passed:
                    best_svg = svg_content
                    break

                # Ask the model to repair, feeding back structured violations.
                conversation.append(
                    LLMMessage.user(
                        report.to_prompt_block()
                        + "\n\nReturn the complete corrected SVG only, "
                        "wrapped in a ```svg code block."
                    )
                )
                repair_temp = max(0.1, 0.3 - 0.1 * (attempt - 1))
                snapshot = set_usage_context(
                    stage="repair", page=page_num, attempt=attempt
                )
                try:
                    response = await llm.chat(
                        conversation, model, temperature=repair_temp, max_tokens=16384
                    )
                finally:
                    reset_usage_context(snapshot)

                repaired = _extract_svg(response.content)
                if repaired:
                    svg_content = repaired
                    best_svg = repaired
                    conversation.append(
                        LLMMessage.assistant(f"```svg\n{repaired}\n```")
                    )
                else:
                    conversation.append(LLMMessage.assistant(response.content))
                    break

            svg_path = svg_output_dir / f"{page_num:02d}_{page_name}.svg"
            svg_path.write_text(best_svg, encoding="utf-8")
            yield page_num, best_svg
        else:
            conversation.append(LLMMessage.assistant(response.content))
            raise RuntimeError(
                f"Failed to generate parseable SVG for page {page_num}/{len(pages)} "
                f"({page_name}) after {MAX_SVG_EXTRACTION_ATTEMPTS} attempts"
            )


def _make_page_name(num: int, content: str) -> str:
    """Generate a clean filename from page content."""
    # Try to extract heading
    match = re.match(r"^##?\s+(.+)$", content, re.MULTILINE)
    if match:
        name = match.group(1).strip()
        # Sanitize for filename
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"\s+", "_", name)
        return name[:40].lower()
    return f"page_{num}"


def _extract_svg(text: str) -> str | None:
    """Extract SVG content from LLM response."""
    # Try code block first
    match = re.search(r"```(?:svg|xml)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        svg = match.group(1).strip()
        if svg.startswith("<svg"):
            return svg

    # Try raw SVG
    match = re.search(r"(<svg[^>]*>.*?</svg>)", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    return None


def _build_svg_extraction_retry_prompt(
    *,
    page_num: int,
    total_pages: int,
    page_name: str,
    page_content: str,
    attempt: int,
) -> str:
    """Build structured feedback when the model output is not parseable SVG."""
    return (
        "## Generation Validation Report\n\n"
        f"The previous response for page {page_num}/{total_pages} ({page_name}) "
        "did not contain a parseable complete SVG document.\n\n"
        "## Failure\n"
        "- No complete `<svg ...>...</svg>` block could be extracted.\n"
        "- The current page has not been generated yet.\n\n"
        "## Regeneration Instructions\n"
        f"- Regenerate page {page_num}/{total_pages} only; do not move to another page.\n"
        "- Preserve the page content below; do not invent a different slide.\n"
        "- Return one complete SVG document, wrapped in a ```svg code block.\n"
        "- The SVG must start with `<svg` and end with `</svg>`.\n\n"
        f"## Page Content To Render\n\n{page_content}\n\n"
        f"## Retry Attempt\n\n{attempt}"
    )
