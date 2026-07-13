# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.1 native event stream — run_turn_native emits structured display events.

docs/CLI_UX_REDESIGN.md §4 P1.1: the native ReAct chain (round -> tool ->
verify -> nudge -> finish) previously flashed by inside a transient spinner
string; a UI cannot rebuild the chain from a one-line tail. ``on_event`` is an
ADDITIVE, DISPLAY-ONLY callback (default None = byte-identical behavior):

- ordered structured events for every chain node the loop already narrates;
- ``finish`` carries wall-clock + round count + aggregated token usage (the
  native path previously read response.usage NOWHERE);
- a raising consumer NEVER breaks the turn (display is best-effort);
- ``on_progress`` keeps its exact legacy behavior (both may coexist).
"""
from __future__ import annotations

from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
from tests.unit.vcli.test_native_loop import _make_agent, _make_engine, _session
from zeno.vcli.turn_events import NativeEvent


def _run_with_recorder(script, on_event):
    backend = FakeToolScriptBackend.from_tool_script(script)
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    return eng.run_turn_native(
        "event test turn", session=_session(), on_event=on_event
    )


def _walk_verify_finish():
    return [
        tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
        tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 9.0)"})),
        tool_turn(end=True),
    ]


def test_event_sequence_covers_the_chain() -> None:
    events: list[NativeEvent] = []
    trace = _run_with_recorder(_walk_verify_finish(), events.append)

    kinds = [e.kind for e in events]
    # The chain skeleton, in order (text/reasoning chunks may interleave).
    i_round = kinds.index("round")
    i_start = kinds.index("tool_start")
    i_end = kinds.index("tool_end")
    i_verify = kinds.index("verify")
    i_finish = kinds.index("finish")
    assert i_round < i_start < i_end < i_verify < i_finish
    assert len(trace.steps) == 1  # the trace itself is untouched


def test_tool_events_carry_name_and_outcome() -> None:
    events: list[NativeEvent] = []
    _run_with_recorder(_walk_verify_finish(), events.append)

    start = next(e for e in events if e.kind == "tool_start")
    end = next(e for e in events if e.kind == "tool_end")
    assert start.label == "walk"
    assert end.label == "walk" and end.ok is True


def test_verify_event_carries_expr_and_result() -> None:
    events: list[NativeEvent] = []
    _run_with_recorder(_walk_verify_finish(), events.append)

    ver = next(e for e in events if e.kind == "verify")
    assert "at_position" in ver.label
    assert ver.ok is True


def test_finish_event_carries_wallclock_rounds_and_usage() -> None:
    events: list[NativeEvent] = []
    _run_with_recorder(_walk_verify_finish(), events.append)

    fin = next(e for e in events if e.kind == "finish")
    data = fin.data or {}
    assert data.get("wall_sec", 0.0) > 0.0
    assert data.get("turns", 0) >= 1
    # Usage keys always present (fake backend reports zeros — still honest).
    assert "in_tokens" in data and "out_tokens" in data


def test_unverified_stop_emits_nudge_event() -> None:
    events: list[NativeEvent] = []
    # walk then immediate end_turn -> D23 unverified-action nudge fires.
    _run_with_recorder(
        [
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(end=True),
            tool_turn(end=True),
            tool_turn(end=True),
        ],
        events.append,
    )
    assert any(e.kind == "nudge" for e in events)


def test_raising_consumer_never_breaks_the_turn() -> None:
    def _boom(_e: NativeEvent) -> None:
        raise RuntimeError("display crashed")

    trace = _run_with_recorder(_walk_verify_finish(), _boom)
    assert len(trace.steps) == 1
    assert trace.steps[0].verify_result is True


def test_no_consumer_is_byte_identical_default() -> None:
    # on_event omitted -> the pre-P1.1 signature still works end to end.
    backend = FakeToolScriptBackend.from_tool_script(_walk_verify_finish())
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("legacy call", session=_session())
    assert len(trace.steps) == 1
