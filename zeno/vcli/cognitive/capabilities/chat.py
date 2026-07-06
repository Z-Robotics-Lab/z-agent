# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""LLMChatCapability — the chat LLM as one routable capability.

Wraps the existing ``LLMBackend`` (``backends/``) so the single chat model is no
longer "the backend" but one capability among the model zoo. ``backends/`` is
left intact; this is the adapter that demotes it to a capability behind the
Phase C seam.
"""
from __future__ import annotations

import time
from typing import Any

from vector_os_nano.vcli.cognitive.capabilities.types import CapabilityResult


class LLMChatCapability:
    """A read-only capability that runs a chat completion.

    Payload (``strategy_params`` of the sub-goal):
        - ``prompt``: str  (or ``messages``: list[dict] for a full message list)
        - optional ``system``: list[dict], ``max_tokens``: int
    Output: ``{"text": str}``. Verification is the sub-goal's deterministic
    ``verify`` predicate — the returned text is never self-certifying.
    """

    name = "chat"
    kind = "chat"
    side_effecting = False
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "messages": {"type": "array"},
        },
    }
    output_schema: dict[str, Any] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def estimate(self, payload: dict[str, Any]) -> tuple[float, float]:
        # Cheap, no I/O — a coarse prior for routing/tiebreak.
        return (0.0, 1.0)

    def invoke(self, payload: dict[str, Any], context: Any) -> CapabilityResult:
        start = time.monotonic()
        messages = payload.get("messages")
        if not messages:
            messages = [{"role": "user", "content": str(payload.get("prompt", ""))}]
        try:
            resp = self._backend.call(
                messages=messages,
                tools=[],
                system=payload.get("system", []),
                max_tokens=int(payload.get("max_tokens", 1024)),
            )
        except Exception as exc:  # noqa: BLE001
            return CapabilityResult(
                success=False, error=str(exc), latency_sec=time.monotonic() - start
            )
        text = getattr(resp, "text", "") or ""
        return CapabilityResult(
            success=True,
            output={"text": text},
            latency_sec=time.monotonic() - start,
        )
