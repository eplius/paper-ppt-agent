from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.llm import registry as registry_module
from backend.llm.provider_openai import OpenAIProvider, normalize_openai_base_url
from backend.llm.types import ModelInfo, ProviderInfo


def test_providers_endpoint_lists_four_backends(client, monkeypatch):
    monkeypatch.setattr(
        "backend.api.endpoints.providers.list_providers",
        lambda: [
            ProviderInfo(name="openai", display_name="OpenAI", models=[ModelInfo(id="gpt-4o", display_name="GPT-4o")]),
            ProviderInfo(
                name="deepseek",
                display_name="DeepSeek",
                default_base_url="https://api.deepseek.com",
                models=[ModelInfo(id="deepseek-v4-flash", display_name="DeepSeek V4 Flash")],
            ),
            ProviderInfo(name="anthropic", display_name="Anthropic", models=[ModelInfo(id="claude-sonnet", display_name="Claude Sonnet")]),
            ProviderInfo(name="gemini", display_name="Gemini", models=[ModelInfo(id="gemini-2.5-flash", display_name="Gemini Flash")]),
        ],
    )

    response = client.get("/api/providers")

    assert response.status_code == 200
    payload = response.json()
    names = {provider["name"] for provider in payload["providers"]}
    assert names == {"openai", "deepseek", "anthropic", "gemini"}
    deepseek = next(provider for provider in payload["providers"] if provider["name"] == "deepseek")
    assert deepseek["default_base_url"] == "https://api.deepseek.com"


def test_create_provider_defaults_deepseek_base_url(monkeypatch):
    captured: dict[str, str | None] = {}

    class FakeProvider:
        def __init__(
            self,
            api_key: str,
            base_url: str | None = None,
            provider_name: str = "openai",
        ) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["provider_name"] = provider_name

    monkeypatch.setattr(registry_module, "_load_provider_class", lambda name: FakeProvider)

    provider = registry_module.create_provider("deepseek", "sk-test")

    assert isinstance(provider, FakeProvider)
    assert captured == {
        "api_key": "sk-test",
        "base_url": "https://api.deepseek.com",
        "provider_name": "deepseek",
    }


def test_openai_base_url_accepts_full_chat_completions_endpoint():
    assert (
        normalize_openai_base_url("https://proxy.example.com/v1/chat/completions")
        == "https://proxy.example.com/v1"
    )
    assert (
        normalize_openai_base_url("https://proxy.example.com/openai/v1/chat/completions/")
        == "https://proxy.example.com/openai/v1"
    )
    assert (
        normalize_openai_base_url("https://proxy.example.com/v1")
        == "https://proxy.example.com/v1"
    )


@pytest.mark.asyncio
async def test_openai_provider_adds_deepseek_reasoning_kwargs(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7),
        )

    class FakeAsyncOpenAI:
        def __init__(self, api_key: str, base_url: str | None = None) -> None:
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(create=fake_create),
            )
            self.beta = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(parse=fake_create),
                ),
            )
            self.models = SimpleNamespace(list=lambda: fake_create())

    async def passthrough_retry(func):
        return await func()

    monkeypatch.setattr("backend.llm.provider_openai.AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr("backend.llm.provider_openai.call_with_retry", passthrough_retry)

    provider = OpenAIProvider(
        api_key="sk-test",
        base_url="https://api.deepseek.com",
        provider_name="deepseek",
    )
    response = await provider.chat(
        messages=[],
        model="deepseek-v4-pro",
        max_tokens=16384,
    )

    assert response.content == "ok"
    assert captured["reasoning_effort"] == "max"
    assert captured["extra_body"] == {"thinking": {"type": "enabled"}}
    assert captured["max_tokens"] == 16384
