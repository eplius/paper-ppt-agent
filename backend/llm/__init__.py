"""LLM abstraction layer with multi-provider support."""

from .base import LLMProvider
from .types import LLMMessage, LLMResponse, LLMStreamChunk, TokenUsage


def create_provider(*args, **kwargs):
    from .registry import create_provider as _create_provider

    return _create_provider(*args, **kwargs)


def list_providers():
    from .registry import list_providers as _list_providers

    return _list_providers()

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMStreamChunk",
    "TokenUsage",
    "create_provider",
    "list_providers",
]
