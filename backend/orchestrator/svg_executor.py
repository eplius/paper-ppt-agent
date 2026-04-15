"""SVG Executor agent: generates SVG page code from design spec."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from pathlib import Path

from backend.config import settings
from backend.llm import LLMMessage, LLMProvider, LLMResponse

PROMPT_PATH = Path(__file__).parent / "prompts" / "executor.md"


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
) -> AsyncIterator[tuple[int, str]]:
    """Generate SVG code for each slide page sequentially.

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
    pages = _split_manuscript(manuscript)
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

        response: LLMResponse = await llm.chat(
            conversation, model, temperature=0.3, max_tokens=16384
        )

        # Extract SVG from response
        svg_content = _extract_svg(response.content)
        if not svg_content:
            # Retry with clarification
            conversation.append(LLMMessage.assistant(response.content))
            conversation.append(
                LLMMessage.user(
                    "Please output ONLY the SVG code for this page, "
                    "starting with <svg and ending with </svg>."
                )
            )
            response = await llm.chat(
                conversation, model, temperature=0.3, max_tokens=16384
            )
            svg_content = _extract_svg(response.content)

        if svg_content:
            # Save SVG file
            svg_path = svg_output_dir / f"{page_num:02d}_{page_name}.svg"
            svg_path.write_text(svg_content, encoding="utf-8")

            # Add to conversation for context continuity
            conversation.append(
                LLMMessage.assistant(f"```svg\n{svg_content}\n```")
            )

            yield page_num, svg_content
        else:
            conversation.append(LLMMessage.assistant(response.content))


def _split_manuscript(manuscript: str) -> list[str]:
    """Split manuscript into individual page contents."""
    pages = re.split(r"\n---\n", manuscript)
    return [p.strip() for p in pages if p.strip()]


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
