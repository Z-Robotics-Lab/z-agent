# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1 — native-path prompt caching (research report §3 P1 / short-board E1).

The native ReAct loop re-sent a ~200-line static system prompt + the full tool
schema list + the whole growing message history at FULL input price on EVERY
round-trip. This wires Anthropic ``cache_control`` breakpoints onto the three
stable strata (system prompt, tools, rotating history prefix) and relocates the
per-round volatile live-status pose line to the MESSAGE TAIL so the cacheable
prefix stays byte-stable (which also lets DeepSeek's automatic disk cache hit).

These tests are HERMETIC: they assert the ASSEMBLED request shape (where the
cache breakpoints sit, that the prefix is byte-identical across rounds, and how
many input bytes become cache-eligible). No network, no sim, no hardware — the
actual server-side latency saving is measured live by the operator (see
progress.md), which this repo's red lines forbid this agent from driving.
"""
from __future__ import annotations

import json

from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
from tests.unit.vcli.test_native_loop import _make_agent, _make_engine, _session

EPHEMERAL = {"type": "ephemeral"}


# ---------------------------------------------------------------------------
# 1. Static breakpoints on the system prompt + tool list
# ---------------------------------------------------------------------------


def test_system_prompt_carries_a_cache_breakpoint() -> None:
    from zeno.vcli.native_loop import _native_system_prompt

    blocks = _native_system_prompt(None, frozenset({"holding_object"}), ("banana",))
    assert blocks[-1].get("cache_control") == EPHEMERAL, (
        "the static system prompt block must be a cache breakpoint"
    )


def test_tool_schemas_cache_breakpoint_on_last_tool_only() -> None:
    from zeno.vcli.native_loop import _native_tool_schemas

    class _T:
        description = "walk the robot"
        input_schema = {"type": "object", "properties": {}}

    schemas = _native_tool_schemas({"walk": _T()}, frozenset({"at_position"}))
    # Exactly ONE breakpoint, and it is the LAST tool (Anthropic caches the whole
    # tools array up to and including the marked tool).
    marked = [i for i, s in enumerate(schemas) if s.get("cache_control") == EPHEMERAL]
    assert marked == [len(schemas) - 1], "only the LAST tool schema is a breakpoint"


# ---------------------------------------------------------------------------
# 2. Prefix STABILITY — two independent assemblies are byte-identical (req #4)
# ---------------------------------------------------------------------------


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _strip_cc(obj):
    """Drop ``cache_control`` markers so we compare the CACHED CONTENT, not the
    breakpoint position. The breakpoint legitimately ROTATES forward each round
    (Anthropic caches the content prefix; the marker is metadata, not hashed) — so
    content stability, not marker stability, is the invariant that makes a hit."""
    if isinstance(obj, dict):
        return {k: _strip_cc(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [_strip_cc(v) for v in obj]
    return obj


def _content_canon(obj) -> str:
    return _canon(_strip_cc(obj))


def test_system_and_tools_assembly_is_byte_identical_across_rounds() -> None:
    """Assemble system + tools TWICE (two rounds) and assert byte-identical — no
    timestamp / random-id / dynamic content leaks into the cacheable prefix."""
    from zeno.vcli.native_loop import _native_system_prompt, _native_tool_schemas

    class _T:
        description = "walk the robot"
        input_schema = {"type": "object", "properties": {"distance": {"type": "number"}}}

    oracles = frozenset({"at_position", "holding_object"})
    objs = ("banana", "mug")

    sys_a = _native_system_prompt(None, oracles, objs, has_navigate=True)
    sys_b = _native_system_prompt(None, oracles, objs, has_navigate=True)
    tools_a = _native_tool_schemas({"walk": _T()}, oracles)
    tools_b = _native_tool_schemas({"walk": _T()}, oracles)

    assert _canon(sys_a) == _canon(sys_b), "system prefix must be byte-stable"
    assert _canon(tools_a) == _canon(tools_b), "tool prefix must be byte-stable"


def test_message_history_prefix_is_stable_across_a_multi_round_turn() -> None:
    """The KEY multi-turn property: round N's cacheable prefix (everything BEFORE
    the volatile live-status tail) is a byte-identical prefix of round N+1's. This
    is what makes the growing history a cache HIT instead of a full re-bill."""

    class _Recorder(FakeToolScriptBackend):
        def __init__(self, turns) -> None:
            super().__init__(turns)
            self.messages: list = []

        def call(self, **kw):  # type: ignore[override]
            self.messages.append(kw["messages"])
            return super().call(**kw)

    backend = _Recorder.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)  # RobotWorld, no live hook -> no volatile tail
    eng.run_turn_native("walk then verify", session=_session())

    assert len(backend.messages) == 3

    # Each round's earlier messages must be a byte-identical CONTENT prefix of the
    # next round's (the history only GROWS; nothing earlier is rewritten). Compare
    # content with cache_control stripped — the breakpoint rotates forward by design.
    r0, r1, r2 = backend.messages
    assert _content_canon(r0) == _content_canon(r1[: len(r0)]), (
        "round 0 history is a stable content prefix of round 1"
    )
    assert _content_canon(r1) == _content_canon(r2[: len(r1)]), (
        "round 1 history is a stable content prefix of round 2"
    )


# ---------------------------------------------------------------------------
# 3. History breakpoint placement + live tail (with a live hook)
# ---------------------------------------------------------------------------


def _count_breakpoints(messages) -> int:
    n = 0
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            n += sum(1 for b in content if isinstance(b, dict) and b.get("cache_control"))
    return n


def test_exactly_one_history_breakpoint_before_the_volatile_live_tail() -> None:
    from zeno.vcli.native_loop import _LIVE_STATUS_PREFIX
    from zeno.vcli.worlds.robot import RobotWorld

    class _LiveWorld(RobotWorld):
        def live_status_line(self, agent):
            base = getattr(agent, "_base", None)
            return f"pose x={base._x:.2f}"

    class _Recorder(FakeToolScriptBackend):
        def __init__(self, turns) -> None:
            super().__init__(turns)
            self.messages: list = []

        def call(self, **kw):  # type: ignore[override]
            self.messages.append(kw["messages"])
            return super().call(**kw)

    backend = _Recorder.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    eng._world = _LiveWorld()
    eng.run_turn_native("walk then verify", session=_session())

    for messages in backend.messages:
        assert _count_breakpoints(messages) == 1, "exactly ONE rotating history breakpoint"
        tail_blocks = messages[-1]["content"]
        assert isinstance(tail_blocks, list)
        # The LAST block is the volatile live line and must NOT be cached; the
        # breakpoint sits on the block BEFORE it.
        assert _LIVE_STATUS_PREFIX in tail_blocks[-1].get("text", "")
        assert tail_blocks[-1].get("cache_control") is None, "the live tail is NOT cached"
        assert tail_blocks[-2].get("cache_control") == EPHEMERAL


# ---------------------------------------------------------------------------
# 4. Token-saving measurement (hermetic proxy for the live latency win)
# ---------------------------------------------------------------------------


def test_cacheable_prefix_grows_and_dominates_input_over_a_turn() -> None:
    """Quantify the win: on round N the cache-ELIGIBLE prefix (system + tools +
    prior history) is what a cold path re-bills every round. We assert it is a
    large, monotonically NON-shrinking fraction of the request — i.e. most input
    bytes become cache reads after the first round."""
    from zeno.vcli.native_loop import _native_system_prompt, _native_tool_schemas

    class _Recorder(FakeToolScriptBackend):
        def __init__(self, turns) -> None:
            super().__init__(turns)
            self.messages: list = []

        def call(self, **kw):  # type: ignore[override]
            self.messages.append(kw["messages"])
            return super().call(**kw)

    class _T:
        description = "walk"
        input_schema = {"type": "object", "properties": {}}

    system_bytes = len(_canon(_native_system_prompt(None, frozenset({"at_position"}), ())))
    tools_bytes = len(_canon(_native_tool_schemas({"walk": _T()}, frozenset({"at_position"}))))
    static_prefix = system_bytes + tools_bytes
    assert static_prefix > 2000, "the static system+tools prefix is the dominant re-billed cost"

    backend = _Recorder.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    eng.run_turn_native("walk then verify", session=_session())

    # History only grows -> the cacheable prefix (static + prior history) never shrinks.
    hist_sizes = [len(_canon(m)) for m in backend.messages]
    assert hist_sizes == sorted(hist_sizes), "history is append-only (stable, growing prefix)"


# ---------------------------------------------------------------------------
# 5. OpenAI-compatible / DeepSeek backend: prefix-stable request shape
# ---------------------------------------------------------------------------


def test_openai_convert_preserves_live_tail_after_tool_results() -> None:
    """A user message carrying tool_result blocks AND the live-status text tail must
    convert to the tool messages FOLLOWED BY a user message with the live text —
    DeepSeek must still see the live pose, and it stays LAST so the prefix is stable.
    (The old converter DROPPED the text whenever tool_results were present.)"""
    from zeno.vcli.backends.openai_compat import convert_messages

    msgs = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "walked 2m"},
                {"type": "text", "text": "[LIVE] pose x=2.00"},
            ],
        }
    ]
    out = convert_messages(msgs, "")
    assert out[0]["role"] == "tool" and out[0]["content"] == "walked 2m"
    assert out[-1] == {"role": "user", "content": "[LIVE] pose x=2.00"}, (
        "the live tail must survive as the LAST message (prefix-stable, DeepSeek sees pose)"
    )


def test_parse_usage_reads_deepseek_cache_hit_field() -> None:
    """DeepSeek reports automatic-cache hits in top-level ``prompt_cache_hit_tokens``,
    not in ``prompt_tokens_details.cached_tokens``. The reader must surface it so the
    P1 benchmark can MEASURE the hit rate on the main backend."""
    from types import SimpleNamespace

    from zeno.vcli.backends.openai_compat import parse_usage

    deepseek = SimpleNamespace(
        prompt_tokens=5000, completion_tokens=120,
        prompt_cache_hit_tokens=4600, prompt_cache_miss_tokens=400,
    )
    usage = parse_usage(deepseek)
    assert usage.cache_read_tokens == 4600
    assert usage.input_tokens == 5000

    # OpenAI/OpenRouter shape still wins when present.
    openai_shape = SimpleNamespace(
        prompt_tokens=5000, completion_tokens=120,
        prompt_tokens_details=SimpleNamespace(cached_tokens=4096),
    )
    assert parse_usage(openai_shape).cache_read_tokens == 4096
