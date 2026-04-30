from __future__ import annotations

import pytest

from backend.generator.svg_critic import CriticReport
from backend.generator.visual_critic import VisualCheckOutcome
from backend.llm import LLMResponse
from backend.orchestrator import svg_executor
from backend.orchestrator.svg_executor import generate_svg_pages
from backend.usage.tracker import current_usage_context


class _FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0
        self.message_snapshots = []

    async def chat(self, *args, **kwargs) -> LLMResponse:
        self.message_snapshots.append(list(args[0]))
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return LLMResponse(content=response)


@pytest.mark.asyncio
async def test_generate_svg_pages_retries_same_page_after_svg_extraction_failure(
    workspace_tmp,
) -> None:
    manuscript = "# Page One\n\nBody\n\n---\n\n# Page Two\n\nBody"
    valid_svg = (
        '```svg\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
        '<rect width="1280" height="720" fill="#fff"/>'
        '<text x="100" y="100" font-size="24">ok</text></svg>\n```'
    )
    llm = _FakeLLM(
        [
            "not svg",
            "still not svg",
            valid_svg,
            valid_svg,
        ]
    )

    pages = [
        page_num
        async for page_num, _ in generate_svg_pages(
            "# Design", manuscript, workspace_tmp, llm, "fake-model"
        )
    ]

    assert pages == [1, 2]
    assert llm.calls == 4
    assert (workspace_tmp / "svg_output" / "01_page_one.svg").exists()
    retry_prompt = llm.message_snapshots[1][-1].content
    assert "## Generation Validation Report" in retry_prompt
    assert "No complete `<svg ...>...</svg>` block could be extracted." in retry_prompt
    assert "Regenerate page 1/2 only" in retry_prompt
    assert "# Page One" in retry_prompt


@pytest.mark.asyncio
async def test_generate_svg_pages_fails_after_bounded_same_page_retries(
    workspace_tmp,
) -> None:
    manuscript = "# Page One\n\nBody\n\n---\n\n# Page Two\n\nBody"
    llm = _FakeLLM(["not svg"])

    with pytest.raises(
        RuntimeError,
        match=r"Failed to generate parseable SVG for page 1/2 .* after 3 attempts",
    ):
        [
            page_num
            async for page_num, _ in generate_svg_pages(
                "# Design", manuscript, workspace_tmp, llm, "fake-model"
            )
        ]

    assert llm.calls == 3
    assert not list((workspace_tmp / "svg_output").glob("*.svg"))


@pytest.mark.asyncio
async def test_visual_critic_uses_distinct_usage_stage(
    workspace_tmp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manuscript = "# Page One\n\nBody"
    valid_svg = (
        '```svg\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">'
        '<rect width="1280" height="720" fill="#fff"/>'
        '<text x="100" y="100" font-size="24">ok</text></svg>\n```'
    )
    llm = _FakeLLM([valid_svg])
    seen_contexts: list[dict] = []

    async def fake_visual_check(*args, **kwargs) -> VisualCheckOutcome:
        seen_contexts.append(current_usage_context())
        return VisualCheckOutcome(rendered=True, report=CriticReport(passed=True))

    monkeypatch.setattr(svg_executor, "visual_check", fake_visual_check)

    pages = [
        page_num
        async for page_num, _ in generate_svg_pages(
            "# Design",
            manuscript,
            workspace_tmp,
            llm,
            "fake-model",
            enable_visual_critic=True,
        )
    ]

    assert pages == [1]
    assert len(seen_contexts) == 1
    assert seen_contexts[0]["stage"] == "visual_qa"
    assert seen_contexts[0]["page"] == 1
    assert seen_contexts[0]["attempt"] == 1
