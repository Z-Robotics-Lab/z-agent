# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""BackendTextLLM — default TextLLM adapter backed by create_backend.

Bridges the narrow core.scene_graph.TextLLM Protocol to the full LLMBackend
machinery (create_backend + OpenAI-compat / Anthropic backends).

Usage (vcli layer only; never imported by core/):

    from vector_os_nano.vcli.backends import create_backend
    from vector_os_nano.vcli.backends.text_llm_adapter import BackendTextLLM

    backend = create_backend(provider, api_key, model, base_url)
    text_llm = BackendTextLLM(backend)
    rankings = scene_graph.rank_rooms_for_goal(goal, text_llm)

core/ depends only on the TextLLM Protocol, not on this module.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vector_os_nano.vcli.backends import LLMBackend

logger = logging.getLogger(__name__)

__all__ = ["BackendTextLLM"]

# Max tokens for a text-only spatial ranking call (small, deterministic output).
_MAX_TOKENS: int = 300


class BackendTextLLM:
    """TextLLM adapter that delegates to an LLMBackend.

    Satisfies core.scene_graph.TextLLM structurally (duck-typed Protocol).
    Never reads private attributes from the backend and never hardcodes a
    provider name, model name, or API key.

    Args:
        backend: Any LLMBackend instance (Anthropic, OpenAI-compat, etc.).
                 Constructed via create_backend() in the vcli layer.
    """

    def __init__(self, backend: "LLMBackend") -> None:
        self._backend = backend

    def complete_text(self, prompt: str) -> str:
        """Forward *prompt* to the backend and return the text response.

        Args:
            prompt: Full user-side prompt string.

        Returns:
            The model's text response.

        Raises:
            Any exception raised by the backend (caller should handle).
        """
        messages: list[dict] = [{"role": "user", "content": prompt}]
        response = self._backend.call(
            messages=messages,
            tools=[],
            system=[],
            max_tokens=_MAX_TOKENS,
        )
        return response.text or ""
