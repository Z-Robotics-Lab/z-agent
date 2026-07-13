# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.4 honest timing — native trace durations are REAL wall-clock, never 0.0 stubs.

Field forensics (2026-07-13, docs/CLI_UX_REDESIGN.md §1.4): the REPL showed
"0.0s" everywhere on the native path because ``NativeStepRunner`` hardcoded
``duration_sec=0.0`` and ``build_trace`` hardcoded ``total_duration_sec=0.0``.
Displaying a fabricated timing is worse than displaying none — these tests pin
that the producer measures what actually elapsed:

- a step whose action skill takes ~50ms records duration_sec >= that sleep;
- the per-step anchor RESETS between (chain -> verify) pairs, so a fast second
  step never inherits the slow first step's wall-clock;
- a verify-only step (no skill dispatched) times just its own verify handling;
- total_duration_sec covers the whole turn (>= the slowest step, > 0 even for
  an empty trace, since the loop itself ran).

Display-only fix: verified/evidence/actor grading are untouched (the moat does
not read durations).
"""
from __future__ import annotations

import time

from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
from tests.unit.vcli.test_native_loop import (
    _make_agent,
    _make_engine,
    _session,
)


class _SlowWalkSkill:
    """Walk variant whose execute takes a measurable ~50ms of wall-clock."""

    name = "slow_walk"
    description = "Walk slowly (test skill with a measurable execution time)."
    parameters = {
        "distance": {"type": "number", "required": False, "default": 1.0},
    }
    preconditions = ["base"]
    effects = {"is_moving": False}

    def execute(self, params, context):
        from zeno.core.types import SkillResult

        base = context.base
        if base is None:
            return SkillResult(success=False, error_message="no base")
        time.sleep(0.05)
        base.walk(0.3, 0.0, 0.0, float(params.get("distance", 1.0)) / 0.3)
        return SkillResult(success=True, result_data={})


def _run(script) -> "object":
    backend = FakeToolScriptBackend.from_tool_script(script)
    agent, _base = _make_agent(0.0, 0.0)
    agent._skill_registry.register(_SlowWalkSkill())
    eng = _make_engine(agent, backend)
    return eng.run_turn_native("timing test turn", session=_session())


def test_step_duration_is_real_wallclock() -> None:
    trace = _run(
        [
            tool_turn(("slow_walk", {"distance": 1.0})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 9.0)"})),
            tool_turn(end=True),
        ]
    )
    assert len(trace.steps) == 1
    step = trace.steps[0]
    # The skill slept 50ms — a real measurement must see it; a 0.0 stub fails.
    assert step.duration_sec >= 0.05, step.duration_sec
    assert step.duration_sec < 30.0, step.duration_sec


def test_second_step_does_not_inherit_first_steps_clock() -> None:
    trace = _run(
        [
            tool_turn(("slow_walk", {"distance": 1.0})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 9.0)"})),
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 9.0)"})),
            tool_turn(end=True),
        ]
    )
    assert len(trace.steps) == 2
    slow, fast = trace.steps[0], trace.steps[1]
    assert slow.duration_sec >= 0.05, slow.duration_sec
    # The anchor reset at the first verify: the instant second pair must be
    # clearly cheaper than the slept first pair (would fail if the anchor
    # leaked across steps — both would then include the 50ms sleep).
    assert fast.duration_sec < slow.duration_sec, (fast.duration_sec, slow.duration_sec)


def test_verify_only_step_times_its_own_handling() -> None:
    trace = _run(
        [
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 9.0)"})),
            tool_turn(end=True),
        ]
    )
    assert len(trace.steps) == 1
    step = trace.steps[0]
    # No skill dispatched: the duration is just the verify handling — tiny but
    # non-negative, and honestly bounded (never a leftover anchor from nowhere).
    assert step.duration_sec >= 0.0
    assert step.duration_sec < 5.0, step.duration_sec


def test_total_duration_covers_turn_and_is_never_a_stub() -> None:
    trace = _run(
        [
            tool_turn(("slow_walk", {"distance": 1.0})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 9.0)"})),
            tool_turn(end=True),
        ]
    )
    assert trace.total_duration_sec >= trace.steps[0].duration_sec
    assert trace.total_duration_sec < 60.0


def test_empty_trace_total_duration_still_measured() -> None:
    trace = _run([tool_turn(end=True)])
    assert trace.steps == ()
    # The loop ran a real round-trip; the turn took SOME time. A 0.0 stub fails.
    assert trace.total_duration_sec > 0.0
