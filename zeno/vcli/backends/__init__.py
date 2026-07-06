# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""vcli.backends — unified LLM backend abstraction.

Supports Anthropic API, OpenRouter, and any OpenAI-compatible endpoint
(ollama, vLLM, local models) through a single Protocol.

Public API:
    LLMBackend    — Protocol that all backends implement
    LLMResponse   — Canonical response type
    LLMToolCall   — Canonical tool call type
    create_backend() — Factory that picks the right backend
"""
from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

from zeno.vcli.backends.types import LLMResponse, LLMToolCall

__all__ = [
    "LLMBackend",
    "LLMResponse",
    "LLMToolCall",
    "create_backend",
]


@runtime_checkable
class LLMBackend(Protocol):
    """Structural interface for LLM API backends.

    Each backend handles:
    - Message format conversion (canonical Anthropic-like → native)
    - API call with streaming
    - Response parsing (native → canonical LLMResponse)
    - Retry logic for transient errors
    """

    def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: list[dict[str, Any]],
        max_tokens: int,
        on_text: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Make an LLM API call and return a canonical response.

        Args:
            messages: Conversation history in Anthropic message format.
            tools:    Tool definitions in Anthropic tool schema format.
            system:   System prompt blocks in Anthropic format.
            max_tokens: Max output tokens.
            on_text:  Called incrementally with text chunks during streaming.
            on_reasoning: Called incrementally with hidden reasoning/think chunks
                during streaming (reasoning models only). Used purely for a live
                "thinking…" heartbeat; never accumulated into the response text.

        Returns:
            LLMResponse with text, tool_calls, stop_reason, and usage.
        """
        ...


def create_backend(
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> LLMBackend:
    """Factory: create the right backend for a given provider.

    Args:
        provider: "anthropic" or "openrouter" or "openai_compat".
        api_key:  API key for the provider.
        model:    Model identifier (provider-specific naming).
        base_url: Optional base URL override.

    Returns:
        An LLMBackend instance ready to call().
    """
    if provider == "anthropic":
        from zeno.vcli.backends.anthropic import AnthropicBackend

        return AnthropicBackend(api_key=api_key, model=model, base_url=base_url)

    # openrouter, openai_compat, local — all use OpenAI-compatible API
    from zeno.vcli.backends.openai_compat import OpenAICompatBackend

    return OpenAICompatBackend(
        api_key=api_key,
        model=model,
        base_url=base_url or "https://openrouter.ai/api/v1",
    )
