"""OpenAI LLM provider using the native openai SDK."""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from pydantic import BaseModel

from .base import LLMProvider
from .types import (
    ContentBlock,
    LLMMessage,
    LLMResponse,
    LLMStreamChunk,
    ModelInfo,
    ProviderInfo,
    TokenUsage,
)


class OpenAIProvider(LLMProvider):
    """OpenAI provider wrapping AsyncOpenAI."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._base_url = (base_url or "").rstrip("/")

    def _normalize_max_tokens(self, model: str, max_tokens: int | None) -> int | None:
        if not max_tokens:
            return max_tokens

        # DeepSeek's OpenAI-compatible endpoint rejects values above 8192.
        if "api.deepseek.com" in self._base_url or model.startswith("deepseek"):
            return min(max_tokens, 8192)

        return max_tokens

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Convert LLMMessage list to OpenAI message format."""
        result = []
        for msg in messages:
            if isinstance(msg.content, str):
                result.append({"role": msg.role, "content": msg.content})
            else:
                parts = []
                for block in msg.content:
                    if block.type == "text" and block.text:
                        parts.append({"type": "text", "text": block.text})
                    elif block.type == "image" and block.image_data:
                        b64 = base64.b64encode(block.image_data).decode()
                        media = block.image_media_type or "image/png"
                        parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media};base64,{b64}",
                            },
                        })
                result.append({"role": msg.role, "content": parts})
        return result

    async def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: type[BaseModel] | None = None,
    ) -> LLMResponse:
        normalized_max_tokens = self._normalize_max_tokens(model, max_tokens)
        kwargs: dict = {
            "model": model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
        }
        if normalized_max_tokens:
            kwargs["max_tokens"] = normalized_max_tokens

        if response_format:
            resp = await self._client.beta.chat.completions.parse(
                **kwargs,
                response_format=response_format,
            )
        else:
            resp = await self._client.chat.completions.create(**kwargs)

        content = resp.choices[0].message.content or ""
        usage = None
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )
        return LLMResponse(content=content, usage=usage, raw=resp)

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        normalized_max_tokens = self._normalize_max_tokens(model, max_tokens)
        kwargs: dict = {
            "model": model,
            "messages": self._convert_messages(messages),
            "temperature": temperature,
            "stream": True,
        }
        if normalized_max_tokens:
            kwargs["max_tokens"] = normalized_max_tokens

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield LLMStreamChunk(
                    delta=delta.content,
                    finish_reason=chunk.choices[0].finish_reason,
                )

    async def validate(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False

    def get_provider_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="openai",
            display_name="OpenAI",
            models=[
                ModelInfo(
                    id="gpt-5.4",
                    display_name="GPT-5.4",
                    supports_vision=True,
                    supports_structured_output=True,
                    context_window=400000,
                ),
                ModelInfo(
                    id="gpt-5.3",
                    display_name="GPT-5.3",
                    supports_vision=True,
                    supports_structured_output=True,
                    context_window=200000,
                ),
            ],
        )
