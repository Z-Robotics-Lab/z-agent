# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""OpenAI-compatible LLM backend for Vector CLI.

Works with any provider that implements the OpenAI chat completions API:
- OpenRouter (https://openrouter.ai/api/v1)
- Ollama (http://localhost:11434/v1)
- vLLM (http://localhost:8000/v1)
- Any OpenAI-compatible local server

Handles conversion between Anthropic-canonical format (used internally)
and OpenAI chat format (used by these providers).
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable

import openai

from vector_os_nano.vcli.backends.types import LLMResponse, LLMToolCall
from vector_os_nano.vcli.session import TokenUsage

logger = logging.getLogger(__name__)


class ModelUnavailableError(openai.APIStatusError):
    """A BYO model cannot run for a NON-recoverable, user-actionable reason.

    Two cases, both distinct from a transient error (retried) AND from a model that
    simply CHOSE not to act (returns text):
      - hard credit exhaustion: a 402 that a max_tokens downshift cannot fix (the
        prompt itself is unaffordable, or the balance is empty after the one allowed
        downshift);
      - unknown model id: a 404 "No endpoints found" (bad ``VECTOR_MODEL`` / a model
        with no provider on this account).

    Surfaced as ONE clear operator-actionable line instead of a raw traceback — and,
    critically, instead of being swallowed into "native took no action → fall back to
    legacy", which is exactly what made D179 misread balance/routing failures as
    "model over-caution". Subclasses ``APIStatusError`` so every existing catch of the
    OpenAI error type keeps working; adds ``.model`` / ``.reason`` for callers.
    """

    def __init__(self, *, model: str, base_url: str, reason: str,
                 original: openai.APIStatusError) -> None:
        self.model = model
        self.base_url = base_url
        self.reason = reason
        message = (
            f"Model '{model}' unavailable via {base_url}: {reason}. "
            f"Check VECTOR_MODEL and provider credits."
        )
        super().__init__(message, response=original.response, body=original.body)


# ---------------------------------------------------------------------------
# Stop reason mapping: OpenAI → canonical
# ---------------------------------------------------------------------------

_STOP_REASON_MAP: dict[str, str] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "end_turn",
}


def affordable_max_tokens(exc_message: str) -> int | None:
    """Parse an OpenRouter/OpenAI-compat 402 balance error for the affordable cap.

    A budget / low-balance account rejects the UPFRONT max_tokens reservation with
    HTTP 402 "This request requires more credits, or fewer max_tokens. You requested
    up to 8000 tokens, but can only afford 522." — a RECOVERABLE condition: the
    provider tells us the output-token cap the balance CAN cover. Returns that
    integer, or None if the message is not this shape (so the caller re-raises and
    behaviour for every other status/error is unchanged).
    """
    low = exc_message.lower()
    if "afford" not in low and "fewer max_tokens" not in low:
        return None
    m = re.search(r"can only afford (\d+)", low)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Message format converters: Anthropic-canonical → OpenAI
# ---------------------------------------------------------------------------


def convert_system(system_blocks: list[dict[str, Any]]) -> str:
    """Convert Anthropic system blocks to a single OpenAI system message string."""
    parts: list[str] = []
    for block in system_blocks:
        text = block.get("text", "")
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def convert_tools(anthropic_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool schemas to OpenAI function tool format.

    Anthropic: {"name": "...", "description": "...", "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}
    """
    openai_tools: list[dict[str, Any]] = []
    for t in anthropic_tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return openai_tools


def convert_messages(
    anthropic_messages: list[dict[str, Any]],
    system_text: str,
) -> list[dict[str, Any]]:
    """Convert Anthropic message format to OpenAI chat format.

    Handles:
    - user text messages
    - assistant text + tool_use blocks → assistant message + tool_calls
    - user tool_result blocks → one "tool" message per result
    - system prompt as first system message
    """
    openai_msgs: list[dict[str, Any]] = []

    # System message first
    if system_text:
        openai_msgs.append({"role": "system", "content": system_text})

    for msg in anthropic_messages:
        role = msg["role"]
        content = msg.get("content")

        if role == "user":
            if isinstance(content, str):
                openai_msgs.append({"role": "user", "content": content})
            elif isinstance(content, list):
                # Could be tool_result blocks or mixed content
                tool_results = [
                    b for b in content
                    if isinstance(b, dict) and b.get("type") == "tool_result"
                ]
                if tool_results:
                    for tr in tool_results:
                        openai_msgs.append({
                            "role": "tool",
                            "tool_call_id": tr["tool_use_id"],
                            "content": tr.get("content", ""),
                        })
                else:
                    # Plain text blocks
                    text = " ".join(
                        b.get("text", str(b)) if isinstance(b, dict) else str(b)
                        for b in content
                    )
                    openai_msgs.append({"role": "user", "content": text})

        elif role == "assistant":
            if isinstance(content, str):
                openai_msgs.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                # Extract text and tool_use blocks
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(
                                    block.get("input", {}), ensure_ascii=False
                                ),
                            },
                        })

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                openai_msgs.append(assistant_msg)

    return openai_msgs


# ---------------------------------------------------------------------------
# Response parser: OpenAI → canonical
# ---------------------------------------------------------------------------


def parse_usage(raw_usage: Any) -> TokenUsage:
    """Extract token usage from an OpenAI response."""
    if raw_usage is None:
        return TokenUsage()
    return TokenUsage(
        input_tokens=getattr(raw_usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(raw_usage, "completion_tokens", 0) or 0,
        cache_read_tokens=getattr(raw_usage, "prompt_tokens_details", None)
        and getattr(raw_usage.prompt_tokens_details, "cached_tokens", 0) or 0,
    )


# ---------------------------------------------------------------------------
# OpenAICompatBackend
# ---------------------------------------------------------------------------


class OpenAICompatBackend:
    """Backend for any OpenAI-compatible API endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        max_retries: int = 3,
    ) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._base_url = base_url
        self._max_retries = max_retries

    def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: list[dict[str, Any]],
        max_tokens: int,
        on_text: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Call the OpenAI-compatible API with streaming and retry."""
        system_text = convert_system(system)
        oai_messages = convert_messages(messages, system_text)
        oai_tools = convert_tools(tools) if tools else None

        return self._call_with_retry(
            oai_messages, oai_tools, max_tokens, on_text, on_reasoning
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        on_text: Callable[[str], None] | None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Make the API call with exponential backoff retry."""
        last_exc: Exception | None = None
        downshifted = False  # graceful 402: lower max_tokens at most once

        for attempt in range(self._max_retries):
            try:
                return self._call_streaming(
                    messages, tools, max_tokens, on_text, on_reasoning
                )
            except openai.RateLimitError as exc:
                last_exc = exc
                delay = 2**attempt
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %ds",
                    attempt + 1, self._max_retries, delay,
                )
                time.sleep(delay)
            except openai.APIConnectionError as exc:
                last_exc = exc
                delay = 2**attempt
                logger.warning(
                    "Connection error (attempt %d/%d), retrying in %ds",
                    attempt + 1, self._max_retries, delay,
                )
                time.sleep(delay)
            except openai.InternalServerError as exc:
                last_exc = exc
                delay = 2**attempt
                logger.warning(
                    "Server error (attempt %d/%d), retrying in %ds",
                    attempt + 1, self._max_retries, delay,
                )
                time.sleep(delay)
            except openai.APIStatusError as exc:
                # Graceful degradation for a recoverable 402: a low-balance / budget
                # account rejects the upfront max_tokens reservation but tells us the
                # cap it can afford. Retry ONCE at that cap so a BYO model still runs
                # instead of hard-failing (plug-and-play robustness; the honest-verify
                # spine is untouched). Every other status/error re-raises as before.
                afford = (
                    affordable_max_tokens(str(exc))
                    if getattr(exc, "status_code", None) == 402
                    else None
                )
                if afford and 0 < afford < max_tokens and not downshifted:
                    logger.warning(
                        "402 balance cap: max_tokens %d unaffordable, retrying at %d",
                        max_tokens, afford,
                    )
                    max_tokens = afford
                    downshifted = True
                    continue
                # NON-recoverable, user-actionable failures → a clear typed error so
                # the operator fixes VECTOR_MODEL / credits and the caller never
                # misreads "unavailable" as "the model chose not to act" (D179/D180).
                unavailable = self._classify_unavailable(exc)
                if unavailable is not None:
                    raise unavailable from exc
                raise  # Non-retryable, not model-unavailability

        raise last_exc  # type: ignore[misc]

    def _classify_unavailable(
        self, exc: openai.APIStatusError
    ) -> ModelUnavailableError | None:
        """Map a NON-recoverable APIStatusError to a ModelUnavailableError, or None.

        - 402 (any shape that reached here, i.e. a downshift could not save it) →
          hard credit exhaustion.
        - 404 "no endpoints" / "not found" → unknown model id / no provider.
        Every other status returns None so the caller re-raises it unchanged.
        """
        code = getattr(exc, "status_code", None)
        low = str(exc).lower()
        if code == 402:
            return ModelUnavailableError(
                model=self._model, base_url=self._base_url,
                reason="out of credit / account balance exhausted", original=exc,
            )
        if code == 404 and ("no endpoint" in low or "not found" in low
                            or "no allowed provider" in low):
            return ModelUnavailableError(
                model=self._model, base_url=self._base_url,
                reason="unknown model id or no available provider endpoint",
                original=exc,
            )
        return None

    def _call_streaming(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        on_text: Callable[[str], None] | None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Make a streaming API call, accumulate text + tool calls, return LLMResponse."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools

        stream = self._client.chat.completions.create(**kwargs)

        # Accumulators
        text_parts: list[str] = []
        tool_call_acc: dict[int, dict[str, Any]] = {}  # index → {id, name, arguments}
        finish_reason: str | None = None
        usage_data: Any = None

        for chunk in stream:
            if not chunk.choices:
                # Usage-only chunk (some providers send this at the end)
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    usage_data = chunk.usage
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # Finish reason
            if choice.finish_reason is not None:
                finish_reason = choice.finish_reason

            # Reasoning content (reasoning models: DeepSeek `reasoning_content`,
            # some providers `reasoning`). Hidden trace — surfaced ONLY as a live
            # "thinking…" heartbeat, never accumulated into the response text.
            if on_reasoning is not None and delta is not None:
                reasoning_chunk = getattr(delta, "reasoning_content", None) or getattr(
                    delta, "reasoning", None
                )
                if reasoning_chunk:
                    on_reasoning(reasoning_chunk)

            # Text content
            if delta and delta.content:
                text_parts.append(delta.content)
                if on_text is not None:
                    on_text(delta.content)

            # Tool calls (streamed in chunks — accumulate by index)
            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_call_acc:
                        tool_call_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    acc = tool_call_acc[idx]
                    if tc_delta.id:
                        acc["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            acc["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            acc["arguments"] += tc_delta.function.arguments

        # Build canonical tool calls
        llm_tool_calls: list[LLMToolCall] = []
        for idx in sorted(tool_call_acc.keys()):
            acc = tool_call_acc[idx]
            try:
                parsed_input = json.loads(acc["arguments"]) if acc["arguments"] else {}
            except json.JSONDecodeError:
                parsed_input = {"_raw": acc["arguments"]}
                logger.warning("Failed to parse tool arguments for %s", acc["name"])
            llm_tool_calls.append(
                LLMToolCall(id=acc["id"], name=acc["name"], input=parsed_input)
            )

        stop = _STOP_REASON_MAP.get(finish_reason or "stop", "end_turn")
        usage = parse_usage(usage_data)

        return LLMResponse(
            text="".join(text_parts),
            tool_calls=llm_tool_calls,
            stop_reason=stop,
            usage=usage,
        )
