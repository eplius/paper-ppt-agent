from __future__ import annotations

import pytest

from backend.llm import LLMResponse
from backend.llm.types import ProviderInfo
from backend.orchestrator import research_agent
from backend.orchestrator.provider_guidance import is_deepseek_provider
from backend.parser.paper_model import ParsedPaper, PaperSection


class _FakeLLM:
    def __init__(self, provider_name: str, content: str = "# Slide\n\n- Body") -> None:
        self.provider_name = provider_name
        self.content = content
        self.calls: list[dict] = []

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(name=self.provider_name, display_name=self.provider_name)

    async def chat(self, messages, model, **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, "model": model, **kwargs})
        return LLMResponse(content=self.content)


def test_is_deepseek_provider_detects_runtime_provider_info() -> None:
    assert is_deepseek_provider(_FakeLLM("deepseek"), "deepseek-v4-pro")
    assert not is_deepseek_provider(_FakeLLM("openai"), "gpt-5.5")


@pytest.mark.asyncio
async def test_research_agent_adds_deepseek_depth_guidance() -> None:
    paper = ParsedPaper(
        title="Test Paper",
        abstract="A test abstract.",
        sections=[PaperSection(title="Method", level=1, content="Detailed method.")],
    )
    llm = _FakeLLM("deepseek")

    await research_agent.analyze_paper(
        paper,
        llm,
        "deepseek-v4-pro",
        detail_level="very_high",
    )

    call = llm.calls[0]
    user_prompt = call["messages"][-1].content
    assert "DeepSeek Calibration" in user_prompt
    assert "mechanism, evidence/data, and implication" in user_prompt
    assert call["max_tokens"] == research_agent.DEEPSEEK_RESEARCH_MAX_TOKENS


@pytest.mark.asyncio
async def test_research_agent_keeps_openai_prompt_unchanged() -> None:
    paper = ParsedPaper(title="Test Paper", abstract="A test abstract.")
    llm = _FakeLLM("openai")

    await research_agent.analyze_paper(
        paper,
        llm,
        "gpt-5.5",
        detail_level="very_high",
    )

    call = llm.calls[0]
    user_prompt = call["messages"][-1].content
    assert "DeepSeek Calibration" not in user_prompt
    assert call["max_tokens"] is None
