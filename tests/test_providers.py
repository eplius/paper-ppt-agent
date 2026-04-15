from __future__ import annotations

from backend.llm.types import ModelInfo, ProviderInfo


def test_providers_endpoint_lists_three_backends(client, monkeypatch):
    monkeypatch.setattr(
        "backend.api.endpoints.providers.list_providers",
        lambda: [
            ProviderInfo(name="openai", display_name="OpenAI", models=[ModelInfo(id="gpt-4o", display_name="GPT-4o")]),
            ProviderInfo(name="anthropic", display_name="Anthropic", models=[ModelInfo(id="claude-sonnet", display_name="Claude Sonnet")]),
            ProviderInfo(name="gemini", display_name="Gemini", models=[ModelInfo(id="gemini-2.5-flash", display_name="Gemini Flash")]),
        ],
    )

    response = client.get("/api/providers")

    assert response.status_code == 200
    payload = response.json()
    names = {provider["name"] for provider in payload["providers"]}
    assert names == {"openai", "anthropic", "gemini"}
