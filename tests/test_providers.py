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


def test_openai_default_models_use_gpt55_not_gpt53():
    registry_openai = next(
        provider for provider in registry_module.list_providers() if provider.name == "openai"
    )
    provider = object.__new__(OpenAIProvider)
    provider._provider_name = "openai"

    registry_models = [model.id for model in registry_openai.models]
    runtime_models = [model.id for model in provider.get_provider_info().models]

    assert registry_models == ["gpt-5.5", "gpt-5.4"]
    assert runtime_models == ["gpt-5.5", "gpt-5.4"]
    assert "gpt-5.3" not in registry_models
    assert "gpt-5.3" not in runtime_models


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


@pytest.mark.asyncio
async def test_official_openai_uses_max_completion_tokens_and_gpt5_settings(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
        )

    class FakeAsyncOpenAI:
        def __init__(self, api_key: str, base_url: str | None = None) -> None:
            captured["base_url"] = base_url
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
        provider_name="openai",
        openai_settings={
            "reasoning_effort": "high",
            "verbosity": "medium",
        },
    )
    response = await provider.chat(
        messages=[],
        model="gpt-5.5",
        temperature=0.2,
        max_tokens=4096,
    )

    assert response.content == "ok"
    assert captured["base_url"] is None
    assert captured["max_completion_tokens"] == 4096
    assert "max_tokens" not in captured
    assert "temperature" not in captured
    assert captured["reasoning_effort"] == "high"
    assert captured["verbosity"] == "medium"


@pytest.mark.asyncio
async def test_official_openai_falls_back_to_max_tokens(monkeypatch):
    captured_calls: list[dict[str, object]] = []

    async def fake_create(**kwargs):
        captured_calls.append(dict(kwargs))
        if "max_completion_tokens" in kwargs:
            raise TypeError("unexpected keyword argument 'max_completion_tokens'")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
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

    provider = OpenAIProvider(api_key="sk-test", provider_name="openai")
    response = await provider.chat(messages=[], model="gpt-5.5", max_tokens=2048)

    assert response.content == "ok"
    assert captured_calls[0]["max_completion_tokens"] == 2048
    assert captured_calls[0]["reasoning_effort"] == "medium"
    assert captured_calls[0]["verbosity"] == "high"
    assert captured_calls[1]["max_completion_tokens"] == 2048
    assert "reasoning_effort" not in captured_calls[1]
    assert "verbosity" not in captured_calls[1]
    assert captured_calls[2]["max_tokens"] == 2048
    assert "max_completion_tokens" not in captured_calls[2]
    assert "reasoning_effort" not in captured_calls[2]
    assert "verbosity" not in captured_calls[2]


@pytest.mark.asyncio
async def test_openai_provider_respects_configured_deepseek_thinking(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
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
        deepseek_settings={
            "thinking_enabled": False,
            "reasoning_effort": "high",
        },
    )
    response = await provider.chat(
        messages=[],
        model="deepseek-v4-pro",
        temperature=0.2,
    )

    assert response.content == "ok"
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in captured
    assert captured["temperature"] == 0.2
