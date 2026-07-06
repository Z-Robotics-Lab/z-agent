# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for vcli.backends — message format converters and types.

Covers:
- convert_system: concatenates blocks, handles empty input
- convert_tools: Anthropic → OpenAI function schema, 0/1/many tools
- convert_messages: user text, assistant text, system injection,
  tool_use blocks, tool_result blocks, full round-trip
- parse_usage: OpenAI usage object → TokenUsage, None input
- LLMResponse / LLMToolCall: frozen dataclasses, defaults
- create_backend: factory returns correct backend type
"""
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from typing import Any
from unittest.mock import MagicMock, patch

import openai
import pytest

from zeno.vcli.backends import LLMBackend, create_backend
from zeno.vcli.backends.openai_compat import (
    OpenAICompatBackend,
    affordable_max_tokens,
    convert_messages,
    convert_system,
    convert_tools,
    parse_usage,
)
from zeno.vcli.backends.types import LLMResponse, LLMToolCall
from zeno.vcli.session import TokenUsage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str, description: str = "", schema: dict | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": schema or {"type": "object", "properties": {}},
    }


def _make_usage(prompt: int, completion: int, cached: int = 0) -> Any:
    obj = MagicMock()
    obj.prompt_tokens = prompt
    obj.completion_tokens = completion
    details = MagicMock()
    details.cached_tokens = cached
    obj.prompt_tokens_details = details if cached else None
    return obj


# ---------------------------------------------------------------------------
# convert_system
# ---------------------------------------------------------------------------


class TestConvertSystem:
    def test_empty_list_returns_empty_string(self) -> None:
        assert convert_system([]) == ""

    def test_single_block(self) -> None:
        blocks = [{"type": "text", "text": "You are a helpful robot."}]
        result = convert_system(blocks)
        assert result == "You are a helpful robot."

    def test_multiple_blocks_joined_with_double_newline(self) -> None:
        blocks = [
            {"type": "text", "text": "Block one."},
            {"type": "text", "text": "Block two."},
        ]
        result = convert_system(blocks)
        assert result == "Block one.\n\nBlock two."

    def test_blocks_with_empty_text_ignored(self) -> None:
        blocks = [
            {"type": "text", "text": "Real content."},
            {"type": "text", "text": ""},
        ]
        result = convert_system(blocks)
        assert result == "Real content."

    def test_all_empty_blocks_returns_empty(self) -> None:
        blocks = [{"type": "text", "text": ""}, {"type": "text", "text": ""}]
        assert convert_system(blocks) == ""

    def test_block_missing_text_key_ignored(self) -> None:
        blocks = [{"type": "text"}, {"type": "text", "text": "Present."}]
        result = convert_system(blocks)
        assert result == "Present."


# ---------------------------------------------------------------------------
# convert_tools
# ---------------------------------------------------------------------------


class TestConvertTools:
    def test_empty_list(self) -> None:
        assert convert_tools([]) == []

    def test_single_tool_structure(self) -> None:
        tools = [_make_tool("bash", "Run shell commands", {"type": "object", "properties": {"cmd": {"type": "string"}}})]
        result = convert_tools(tools)

        assert len(result) == 1
        entry = result[0]
        assert entry["type"] == "function"
        func = entry["function"]
        assert func["name"] == "bash"
        assert func["description"] == "Run shell commands"
        assert func["parameters"] == {"type": "object", "properties": {"cmd": {"type": "string"}}}

    def test_multiple_tools_order_preserved(self) -> None:
        tools = [
            _make_tool("read_file", "Read a file"),
            _make_tool("write_file", "Write a file"),
            _make_tool("bash", "Run shell"),
        ]
        result = convert_tools(tools)
        assert len(result) == 3
        names = [r["function"]["name"] for r in result]
        assert names == ["read_file", "write_file", "bash"]

    def test_missing_description_defaults_to_empty_string(self) -> None:
        tools = [{"name": "no_desc", "input_schema": {"type": "object", "properties": {}}}]
        result = convert_tools(tools)
        assert result[0]["function"]["description"] == ""

    def test_missing_input_schema_defaults_to_empty_object(self) -> None:
        tools = [{"name": "no_schema", "description": "Something"}]
        result = convert_tools(tools)
        assert result[0]["function"]["parameters"] == {"type": "object", "properties": {}}

    def test_all_tools_have_type_function(self) -> None:
        tools = [_make_tool("a"), _make_tool("b"), _make_tool("c")]
        for entry in convert_tools(tools):
            assert entry["type"] == "function"


# ---------------------------------------------------------------------------
# convert_messages
# ---------------------------------------------------------------------------


class TestConvertMessages:
    def test_simple_user_text_message(self) -> None:
        msgs = [{"role": "user", "content": "Hello, robot!"}]
        result = convert_messages(msgs, "")
        assert result == [{"role": "user", "content": "Hello, robot!"}]

    def test_simple_assistant_text_message(self) -> None:
        msgs = [{"role": "assistant", "content": "I am ready."}]
        result = convert_messages(msgs, "")
        assert result == [{"role": "assistant", "content": "I am ready."}]

    def test_system_prompt_injected_first(self) -> None:
        msgs = [{"role": "user", "content": "Hi"}]
        result = convert_messages(msgs, "You are a robot.")
        assert result[0] == {"role": "system", "content": "You are a robot."}
        assert result[1] == {"role": "user", "content": "Hi"}

    def test_no_system_message_when_empty(self) -> None:
        msgs = [{"role": "user", "content": "Hi"}]
        result = convert_messages(msgs, "")
        assert all(m["role"] != "system" for m in result)

    def test_assistant_with_tool_use_block(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me look that up."},
                    {
                        "type": "tool_use",
                        "id": "tu_001",
                        "name": "read_file",
                        "input": {"path": "/etc/hosts"},
                    },
                ],
            }
        ]
        result = convert_messages(msgs, "")
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Let me look that up."
        assert len(msg["tool_calls"]) == 1
        tc = msg["tool_calls"][0]
        assert tc["id"] == "tu_001"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "read_file"
        assert json.loads(tc["function"]["arguments"]) == {"path": "/etc/hosts"}

    def test_assistant_with_multiple_tool_use_blocks(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_a",
                        "name": "read_file",
                        "input": {"path": "/a"},
                    },
                    {
                        "type": "tool_use",
                        "id": "tu_b",
                        "name": "bash",
                        "input": {"cmd": "ls"},
                    },
                ],
            }
        ]
        result = convert_messages(msgs, "")
        assert len(result) == 1
        tool_calls = result[0]["tool_calls"]
        assert len(tool_calls) == 2
        assert tool_calls[0]["id"] == "tu_a"
        assert tool_calls[1]["id"] == "tu_b"

    def test_assistant_tool_use_no_text_content_is_none(self) -> None:
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_x",
                        "name": "bash",
                        "input": {"cmd": "pwd"},
                    }
                ],
            }
        ]
        result = convert_messages(msgs, "")
        assert result[0]["content"] is None

    def test_user_with_tool_result_blocks(self) -> None:
        msgs = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu_001",
                        "content": "/etc/hosts content here",
                    }
                ],
            }
        ]
        result = convert_messages(msgs, "")
        assert len(result) == 1
        msg = result[0]
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "tu_001"
        assert msg["content"] == "/etc/hosts content here"

    def test_user_with_multiple_tool_results_expands_to_multiple_messages(self) -> None:
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_a", "content": "Result A"},
                    {"type": "tool_result", "tool_use_id": "tu_b", "content": "Result B"},
                ],
            }
        ]
        result = convert_messages(msgs, "")
        assert len(result) == 2
        assert result[0] == {"role": "tool", "tool_call_id": "tu_a", "content": "Result A"}
        assert result[1] == {"role": "tool", "tool_call_id": "tu_b", "content": "Result B"}

    def test_user_plain_list_blocks_joined(self) -> None:
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Hello"},
                    {"type": "text", "text": "World"},
                ],
            }
        ]
        result = convert_messages(msgs, "")
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert "Hello" in result[0]["content"]
        assert "World" in result[0]["content"]

    def test_full_conversation_round_trip(self) -> None:
        """user → assistant+tool_use → tool_results → assistant"""
        msgs = [
            {"role": "user", "content": "What files are in /tmp?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll check."},
                    {
                        "type": "tool_use",
                        "id": "tu_ls",
                        "name": "bash",
                        "input": {"cmd": "ls /tmp"},
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu_ls",
                        "content": "file1.txt file2.txt",
                    }
                ],
            },
            {"role": "assistant", "content": "Found 2 files: file1.txt, file2.txt."},
        ]
        result = convert_messages(msgs, "System prompt here.")

        # system, user, assistant+tool_call, tool_result, final_assistant
        assert result[0]["role"] == "system"
        assert result[1] == {"role": "user", "content": "What files are in /tmp?"}

        assert result[2]["role"] == "assistant"
        assert result[2]["content"] == "I'll check."
        assert len(result[2]["tool_calls"]) == 1
        assert result[2]["tool_calls"][0]["function"]["name"] == "bash"

        assert result[3]["role"] == "tool"
        assert result[3]["tool_call_id"] == "tu_ls"
        assert result[3]["content"] == "file1.txt file2.txt"

        assert result[4] == {"role": "assistant", "content": "Found 2 files: file1.txt, file2.txt."}
        assert len(result) == 5

    def test_tool_use_arguments_are_json_serialized(self) -> None:
        """Input dict must be JSON-serialized as a string in arguments field."""
        payload = {"nested": {"key": "value"}, "numbers": [1, 2, 3]}
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu_1", "name": "any", "input": payload}
                ],
            }
        ]
        result = convert_messages(msgs, "")
        args_str = result[0]["tool_calls"][0]["function"]["arguments"]
        assert isinstance(args_str, str)
        assert json.loads(args_str) == payload


# ---------------------------------------------------------------------------
# parse_usage
# ---------------------------------------------------------------------------


class TestParseUsage:
    def test_none_returns_zero_usage(self) -> None:
        result = parse_usage(None)
        assert result == TokenUsage()
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_maps_prompt_to_input_and_completion_to_output(self) -> None:
        usage = _make_usage(prompt=100, completion=50)
        result = parse_usage(usage)
        assert result.input_tokens == 100
        assert result.output_tokens == 50

    def test_zero_tokens_explicit(self) -> None:
        usage = _make_usage(prompt=0, completion=0)
        result = parse_usage(usage)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_missing_attributes_default_to_zero(self) -> None:
        obj = MagicMock(spec=[])  # empty spec — no attributes
        result = parse_usage(obj)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_returns_token_usage_instance(self) -> None:
        result = parse_usage(None)
        assert isinstance(result, TokenUsage)

    def test_cache_tokens_extracted_when_present(self) -> None:
        usage = _make_usage(prompt=200, completion=80, cached=50)
        result = parse_usage(usage)
        assert result.input_tokens == 200
        assert result.output_tokens == 80
        assert result.cache_read_tokens == 50


# ---------------------------------------------------------------------------
# LLMToolCall — frozen dataclass
# ---------------------------------------------------------------------------


class TestLLMToolCall:
    def test_construction(self) -> None:
        tc = LLMToolCall(id="tc_1", name="bash", input={"cmd": "ls"})
        assert tc.id == "tc_1"
        assert tc.name == "bash"
        assert tc.input == {"cmd": "ls"}

    def test_frozen_cannot_set_id(self) -> None:
        tc = LLMToolCall(id="tc_1", name="bash", input={})
        with pytest.raises(FrozenInstanceError):
            tc.id = "other"  # type: ignore[misc]

    def test_frozen_cannot_set_name(self) -> None:
        tc = LLMToolCall(id="tc_1", name="bash", input={})
        with pytest.raises(FrozenInstanceError):
            tc.name = "other"  # type: ignore[misc]

    def test_frozen_cannot_set_input(self) -> None:
        tc = LLMToolCall(id="tc_1", name="bash", input={})
        with pytest.raises(FrozenInstanceError):
            tc.input = {"new": "val"}  # type: ignore[misc]

    def test_equality_by_value(self) -> None:
        a = LLMToolCall(id="x", name="y", input={"k": 1})
        b = LLMToolCall(id="x", name="y", input={"k": 1})
        assert a == b

    def test_inequality_different_id(self) -> None:
        a = LLMToolCall(id="x", name="y", input={})
        b = LLMToolCall(id="z", name="y", input={})
        assert a != b


# ---------------------------------------------------------------------------
# LLMResponse — frozen dataclass with defaults
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_construction_minimal(self) -> None:
        resp = LLMResponse(text="Hello")
        assert resp.text == "Hello"
        assert resp.tool_calls == []
        assert resp.stop_reason == "end_turn"
        assert resp.usage == TokenUsage()

    def test_construction_with_tool_calls(self) -> None:
        tc = LLMToolCall(id="tc_1", name="bash", input={"cmd": "pwd"})
        resp = LLMResponse(text="", tool_calls=[tc], stop_reason="tool_use")
        assert len(resp.tool_calls) == 1
        assert resp.stop_reason == "tool_use"

    def test_frozen_cannot_set_text(self) -> None:
        resp = LLMResponse(text="Hi")
        with pytest.raises(FrozenInstanceError):
            resp.text = "Bye"  # type: ignore[misc]

    def test_frozen_cannot_set_stop_reason(self) -> None:
        resp = LLMResponse(text="Hi")
        with pytest.raises(FrozenInstanceError):
            resp.stop_reason = "max_tokens"  # type: ignore[misc]

    def test_default_tool_calls_is_empty_list(self) -> None:
        resp = LLMResponse(text="")
        assert resp.tool_calls == []

    def test_default_usage_is_zero(self) -> None:
        resp = LLMResponse(text="")
        assert resp.usage.input_tokens == 0
        assert resp.usage.output_tokens == 0

    def test_equality_by_value(self) -> None:
        a = LLMResponse(text="hi", stop_reason="end_turn")
        b = LLMResponse(text="hi", stop_reason="end_turn")
        assert a == b

    def test_stop_reason_max_tokens(self) -> None:
        resp = LLMResponse(text="cut off", stop_reason="max_tokens")
        assert resp.stop_reason == "max_tokens"


# ---------------------------------------------------------------------------
# create_backend factory
# ---------------------------------------------------------------------------


class TestCreateBackend:
    def test_openrouter_returns_openai_compat_backend(self) -> None:
        from zeno.vcli.backends.openai_compat import OpenAICompatBackend

        with patch("openai.OpenAI"):
            backend = create_backend(
                provider="openrouter",
                api_key="test-key",
                model="openai/gpt-4o",
            )
        assert isinstance(backend, OpenAICompatBackend)

    def test_anthropic_returns_anthropic_backend(self) -> None:
        from zeno.vcli.backends.anthropic import AnthropicBackend

        with patch("anthropic.Anthropic"):
            backend = create_backend(
                provider="anthropic",
                api_key="test-key",
                model="claude-sonnet-4-6",
            )
        assert isinstance(backend, AnthropicBackend)

    def test_openai_compat_provider_returns_openai_compat_backend(self) -> None:
        from zeno.vcli.backends.openai_compat import OpenAICompatBackend

        with patch("openai.OpenAI"):
            backend = create_backend(
                provider="openai_compat",
                api_key="test-key",
                model="llama3",
                base_url="http://localhost:11434/v1",
            )
        assert isinstance(backend, OpenAICompatBackend)

    def test_openrouter_backend_satisfies_llm_backend_protocol(self) -> None:
        with patch("openai.OpenAI"):
            backend = create_backend(
                provider="openrouter",
                api_key="test-key",
                model="openai/gpt-4o",
            )
        assert isinstance(backend, LLMBackend)

    def test_anthropic_backend_satisfies_llm_backend_protocol(self) -> None:
        with patch("anthropic.Anthropic"):
            backend = create_backend(
                provider="anthropic",
                api_key="test-key",
                model="claude-sonnet-4-6",
            )
        assert isinstance(backend, LLMBackend)


# ---------------------------------------------------------------------------
# BackendTextLLM adapter
# ---------------------------------------------------------------------------


class TestBackendTextLLM:
    """Unit tests for vcli.backends.text_llm_adapter.BackendTextLLM.

    Verifies:
    - complete_text forwards the prompt to backend.call()
    - complete_text returns response.text
    - No private attribute access on the backend
    - Returns '' when response.text is None
    """

    def _make_adapter(self, response_text: str) -> "tuple[Any, Any]":
        """Return (adapter, mock_backend) with response_text canned."""
        from zeno.vcli.backends.text_llm_adapter import BackendTextLLM
        from zeno.vcli.backends.types import LLMResponse

        mock_backend = MagicMock()
        mock_backend.call.return_value = LLMResponse(text=response_text)
        adapter = BackendTextLLM(mock_backend)
        return adapter, mock_backend

    def test_complete_text_returns_response_text(self) -> None:
        adapter, _ = self._make_adapter("ranked rooms here")
        result = adapter.complete_text("some prompt")
        assert result == "ranked rooms here"

    def test_complete_text_forwards_prompt_as_user_message(self) -> None:
        adapter, mock_backend = self._make_adapter("ok")
        adapter.complete_text("my prompt")
        call_kwargs = mock_backend.call.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
        assert any(
            m.get("role") == "user" and "my prompt" in m.get("content", "")
            for m in messages
        )

    def test_complete_text_passes_empty_tools_and_system(self) -> None:
        adapter, mock_backend = self._make_adapter("ok")
        adapter.complete_text("hello")
        _, kw = mock_backend.call.call_args
        assert kw.get("tools") == [] or mock_backend.call.call_args.args
        # Check via keyword args (preferred path)
        if mock_backend.call.call_args.kwargs:
            assert mock_backend.call.call_args.kwargs["tools"] == []
            assert mock_backend.call.call_args.kwargs["system"] == []

    def test_complete_text_none_response_returns_empty_string(self) -> None:
        from zeno.vcli.backends.text_llm_adapter import BackendTextLLM
        from zeno.vcli.backends.types import LLMResponse

        mock_backend = MagicMock()
        mock_backend.call.return_value = LLMResponse(text=None)  # type: ignore[arg-type]
        adapter = BackendTextLLM(mock_backend)
        result = adapter.complete_text("any")
        assert result == ""

    def test_adapter_does_not_read_private_attributes_from_backend(self) -> None:
        """BackendTextLLM must never read dunder/private attrs from the backend."""
        from zeno.vcli.backends.text_llm_adapter import BackendTextLLM
        from zeno.vcli.backends.types import LLMResponse

        accessed_private: list[str] = []

        class _WatchdogBackend:
            def call(self, **kw: Any) -> LLMResponse:
                return LLMResponse(text="ok")

            def __getattr__(self, name: str) -> Any:
                if name.startswith("_"):
                    accessed_private.append(name)
                    raise AttributeError(f"private: {name}")
                raise AttributeError(name)

        adapter = BackendTextLLM(_WatchdogBackend())
        adapter.complete_text("test")
        # Filter out Python internals triggered during construction
        user_private = [n for n in accessed_private if not n.startswith("__")]
        assert user_private == [], f"private attrs accessed: {user_private}"

    def test_openrouter_uses_default_base_url(self) -> None:
        """When base_url is None, OpenRouter default URL is used."""
        with patch("openai.OpenAI") as mock_openai:
            create_backend(
                provider="openrouter",
                api_key="test-key",
                model="openai/gpt-4o",
            )
        call_kwargs = mock_openai.call_args
        assert "openrouter.ai" in call_kwargs.kwargs.get("base_url", "")

    def test_custom_base_url_passed_through(self) -> None:
        custom_url = "http://localhost:8000/v1"
        with patch("openai.OpenAI") as mock_openai:
            create_backend(
                provider="openrouter",
                api_key="test-key",
                model="local-model",
                base_url=custom_url,
            )
        call_kwargs = mock_openai.call_args
        assert call_kwargs.kwargs.get("base_url") == custom_url


# ---------------------------------------------------------------------------
# Streaming: reasoning-model deltas (on_reasoning heartbeat, never in text)
# ---------------------------------------------------------------------------


def _delta(content: Any = None, reasoning_content: Any = None) -> Any:
    """Build a fake OpenAI streaming delta. No tool_calls; optional reasoning."""
    d = MagicMock()
    d.content = content
    d.tool_calls = None
    # getattr(delta, "reasoning_content", None) must return the value (or None).
    d.reasoning_content = reasoning_content
    d.reasoning = None
    return d


def _chunk(delta: Any, finish_reason: Any = None) -> Any:
    choice = MagicMock()
    choice.delta = delta
    choice.finish_reason = finish_reason
    chunk = MagicMock()
    chunk.choices = [choice]
    chunk.usage = None
    return chunk


class TestOpenAICompatReasoningStream:
    """A reasoning model emits hidden reasoning deltas (delta.content is None),
    then the real answer. on_reasoning fires for the think phase; on_text for the
    answer; the reasoning trace never lands in the response text."""

    def _backend(self) -> Any:
        from zeno.vcli.backends.openai_compat import OpenAICompatBackend

        with patch("openai.OpenAI"):
            return OpenAICompatBackend(api_key="k", model="deepseek-v4-flash")

    def test_reasoning_deltas_routed_to_on_reasoning_not_text(self) -> None:
        backend = self._backend()
        # Think phase: content is None, reasoning_content carries the trace.
        # Answer phase: content carries the text, reasoning_content is None.
        stream = [
            _chunk(_delta(content=None, reasoning_content="let me ")),
            _chunk(_delta(content=None, reasoning_content="think")),
            _chunk(_delta(content="Hello")),
            _chunk(_delta(content=" world"), finish_reason="stop"),
        ]
        backend._client = MagicMock()
        backend._client.chat.completions.create.return_value = iter(stream)

        seen_text: list[str] = []
        seen_reasoning: list[str] = []
        resp = backend.call(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            system=[],
            max_tokens=128,
            on_text=seen_text.append,
            on_reasoning=seen_reasoning.append,
        )

        assert seen_reasoning == ["let me ", "think"]
        assert seen_text == ["Hello", " world"]
        # The hidden reasoning trace must NOT be in the final response text.
        assert resp.text == "Hello world"
        assert "think" not in resp.text

    def test_no_on_reasoning_callback_is_safe(self) -> None:
        # Backwards compatible: omitting on_reasoning must not error even when the
        # provider emits reasoning deltas.
        backend = self._backend()
        stream = [
            _chunk(_delta(content=None, reasoning_content="thinking")),
            _chunk(_delta(content="done"), finish_reason="stop"),
        ]
        backend._client = MagicMock()
        backend._client.chat.completions.create.return_value = iter(stream)

        resp = backend.call(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            system=[],
            max_tokens=128,
        )
        assert resp.text == "done"


# ---------------------------------------------------------------------------
# affordable_max_tokens — recoverable 402 balance-cap parser
# ---------------------------------------------------------------------------


class TestAffordableMaxTokens:
    """Parse the OpenRouter/OpenAI-compat 402 'fewer max_tokens' balance error."""

    def test_parses_afford_integer(self) -> None:
        msg = (
            "Error code: 402 - This request requires more credits, or fewer "
            "max_tokens. You requested up to 8000 tokens, but can only afford 522."
        )
        assert affordable_max_tokens(msg) == 522

    def test_case_insensitive(self) -> None:
        assert affordable_max_tokens("Can Only Afford 6510 tokens") == 6510

    def test_non_balance_error_returns_none(self) -> None:
        assert affordable_max_tokens("Error code: 404 - No endpoints found") is None

    def test_afford_wording_without_number_returns_none(self) -> None:
        # Recognises the shape but no parseable cap -> caller re-raises.
        assert affordable_max_tokens("you cannot afford this request") is None

    def test_empty_string_returns_none(self) -> None:
        assert affordable_max_tokens("") is None


# ---------------------------------------------------------------------------
# _call_with_retry — graceful 402 downshift
# ---------------------------------------------------------------------------


def _make_402(afford: int) -> Any:
    """Build a real openai.APIStatusError with status_code 402 and an afford msg."""
    import httpx

    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(402, request=req)
    return openai.APIStatusError(
        f"Error code: 402 - You requested up to 8000 tokens, but can only afford {afford}.",
        response=resp,
        body=None,
    )


class TestGraceful402Downshift:
    """A low-balance account rejects the upfront max_tokens reservation with a
    recoverable 402; the backend must retry ONCE at the affordable cap instead of
    hard-failing, so a BYO model still runs. Every other status error re-raises."""

    def _backend(self) -> Any:
        with patch("openai.OpenAI"):
            return OpenAICompatBackend(api_key="k", model="mistralai/mistral-medium-3-5")

    def test_402_downshifts_and_succeeds(self) -> None:
        backend = self._backend()
        ok = LLMResponse(text="", tool_calls=[LLMToolCall(id="1", name="start_simulation", input={"sim_type": "g1"})], stop_reason="tool_use")
        calls: list[int] = []

        def _fake(messages, tools, max_tokens, on_text, on_reasoning=None):  # noqa: ANN001
            calls.append(max_tokens)
            if len(calls) == 1:
                raise _make_402(522)
            return ok

        backend._call_streaming = _fake  # type: ignore[method-assign]
        resp = backend.call(messages=[{"role": "user", "content": "启动 g1 仿真"}], tools=[], system=[], max_tokens=8000)
        assert resp.tool_calls and resp.tool_calls[0].name == "start_simulation"
        assert calls == [8000, 522]  # retried at the affordable cap

    def test_402_downshifts_at_most_once_then_raises(self) -> None:
        backend = self._backend()
        calls: list[int] = []

        def _always_402(messages, tools, max_tokens, on_text, on_reasoning=None):  # noqa: ANN001
            calls.append(max_tokens)
            raise _make_402(300)

        backend._call_streaming = _always_402  # type: ignore[method-assign]
        with pytest.raises(openai.APIStatusError):
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        # First at 8000, downshift to 300, then raise (no infinite loop).
        assert calls == [8000, 300]

    def test_non_402_status_error_still_raises_immediately(self) -> None:
        backend = self._backend()
        import httpx

        req = httpx.Request("POST", "https://openrouter.ai/api/v1")
        resp404 = httpx.Response(404, request=req)
        exc404 = openai.APIStatusError("Error code: 404 - No endpoints found", response=resp404, body=None)
        calls: list[int] = []

        def _fake404(messages, tools, max_tokens, on_text, on_reasoning=None):  # noqa: ANN001
            calls.append(max_tokens)
            raise exc404

        backend._call_streaming = _fake404  # type: ignore[method-assign]
        with pytest.raises(openai.APIStatusError):
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert calls == [8000]  # no downshift retry for a non-402


# ---------------------------------------------------------------------------
# ModelUnavailableError — NON-recoverable, user-actionable BYO-model failures
# (D180: surface 'this model can't run' clearly instead of silently degrading
# to legacy — the swallow at cli.py that made D179 misread balance/routing
# failures as 'model over-caution'). A subclass of APIStatusError so every
# existing catch still holds; adds .model / .reason for a clean one-liner.
# ---------------------------------------------------------------------------


def _make_status_error(code: int, message: str) -> Any:
    """Build a real openai.APIStatusError with a given status_code + message."""
    import httpx

    req = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    resp = httpx.Response(code, request=req)
    return openai.APIStatusError(message, response=resp, body=None)


class TestModelUnavailableError:
    def _backend(self) -> Any:
        with patch("openai.OpenAI"):
            return OpenAICompatBackend(api_key="k", model="google/gemini-3.5-flash")

    def _raise_once(self, backend: Any, exc: Any) -> list[int]:
        calls: list[int] = []

        def _fake(messages, tools, max_tokens, on_text, on_reasoning=None):  # noqa: ANN001
            calls.append(max_tokens)
            raise exc

        backend._call_streaming = _fake  # type: ignore[method-assign]
        return calls

    def test_hard_402_prompt_exceeds_budget_is_model_unavailable(self) -> None:
        """The prompt itself is unaffordable ('Prompt tokens limit exceeded:
        1114 > 428') — a downshift of max_tokens cannot help, so it must become a
        clear ModelUnavailableError, not a raw 402 (or a silent no-action)."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        exc = _make_status_error(402, "Error code: 402 - Prompt tokens limit exceeded: 1114 > 428.")
        calls = self._raise_once(backend, exc)
        with pytest.raises(ModelUnavailableError) as ei:
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert ei.value.model == "google/gemini-3.5-flash"
        assert "credit" in str(ei.value).lower() or "balance" in str(ei.value).lower()
        assert calls == [8000]  # no phantom downshift — the prompt, not max_tokens, is the problem
        assert isinstance(ei.value, openai.APIStatusError)  # existing catches still hold

    def test_404_no_endpoints_is_model_unavailable(self) -> None:
        """A bad / unknown model id (404 'No endpoints found for X') is
        user-actionable — surface it as ModelUnavailableError naming the model."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        exc = _make_status_error(404, "Error code: 404 - No endpoints found for google/gemini-3.5-flash.")
        self._raise_once(backend, exc)
        with pytest.raises(ModelUnavailableError) as ei:
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert "google/gemini-3.5-flash" in str(ei.value)
        assert "unknown" in str(ei.value).lower() or "endpoint" in str(ei.value).lower()

    def test_400_invalid_model_id_is_model_unavailable(self) -> None:
        """The most common BYO typo: a bad VECTOR_MODEL. OpenRouter rejects it with
        400 'X is not a valid model ID' (not 404) — still user-actionable."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        exc = _make_status_error(400, "Error code: 400 - vector/does-not-exist-xyz is not a valid model ID")
        self._raise_once(backend, exc)
        with pytest.raises(ModelUnavailableError) as ei:
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert "valid model" in str(ei.value).lower()

    def test_400_generic_still_raises_raw(self) -> None:
        """A non-model 400 (e.g. a malformed request) is NOT model-unavailability."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        exc = _make_status_error(400, "Error code: 400 - messages: field required")
        self._raise_once(backend, exc)
        with pytest.raises(openai.APIStatusError) as ei:
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert not isinstance(ei.value, ModelUnavailableError)

    def test_recoverable_402_still_downshifts_not_unavailable(self) -> None:
        """Regression: the recoverable 'can only afford N' 402 must STILL retry at
        the affordable cap — it is NOT a ModelUnavailableError on the first hit."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        ok = LLMResponse(text="ok", stop_reason="end_turn")
        calls: list[int] = []

        def _fake(messages, tools, max_tokens, on_text, on_reasoning=None):  # noqa: ANN001
            calls.append(max_tokens)
            if len(calls) == 1:
                raise _make_402(522)
            return ok

        backend._call_streaming = _fake  # type: ignore[method-assign]
        resp = backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert resp.text == "ok"
        assert calls == [8000, 522]
        assert not isinstance(resp, ModelUnavailableError)

    def test_persistent_recoverable_402_becomes_unavailable_after_downshift(self) -> None:
        """A 'can only afford N' 402 that persists AFTER the one allowed downshift is
        genuine credit exhaustion — it must escalate to ModelUnavailableError, not a
        raw 402 traceback."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        calls = self._raise_once(backend, _make_402(300))
        with pytest.raises(ModelUnavailableError):
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert calls == [8000, 300]  # tried the downshift once, then escalated

    def test_other_status_error_still_raises_raw(self) -> None:
        """A non-402/404 status error (e.g. 403 auth) is NOT model-unavailability —
        it must re-raise the raw APIStatusError, unchanged."""
        from zeno.vcli.backends.openai_compat import ModelUnavailableError

        backend = self._backend()
        exc = _make_status_error(403, "Error code: 403 - Forbidden: bad api key")
        self._raise_once(backend, exc)
        with pytest.raises(openai.APIStatusError) as ei:
            backend.call(messages=[{"role": "user", "content": "x"}], tools=[], system=[], max_tokens=8000)
        assert not isinstance(ei.value, ModelUnavailableError)
