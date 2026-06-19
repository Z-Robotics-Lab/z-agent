# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Regression — the truthy-constant SHORT-CIRCUIT moat hole (2026-06-19 review).

A milestone-review skeptic found that a verify expr which short-circuits the oracle
with a truthy constant — ``at_position(99,99) or True``, ``holding_object('x') or 1``
— classified GROUNDED (the old test merely checked a predicate oracle was CALLED
somewhere in the AST) AND evaluates True in the GoalVerifier regardless of real world
state. Net: a step could earn ``verified=True`` with the robot nowhere near the goal,
just by appending ``or True`` to the verify string.

The fix (``_is_grounded_node``) requires the oracle's RESULT to GATE the verdict:
every truth-bearing leaf of the boolean expr must be an oracle term. These tests pin
that the bypass is RAN, that legitimate boolean combinations stay GROUNDED, and that
the spine evidence gate (``classify_step_evidence``) flips a short-circuit step to RAN
even when it was actor-CAUSED. The guard may only ever get STRICTER (rule 5).
"""
from __future__ import annotations

import pytest

from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr

# A representative live oracle namespace (predicate + state oracles).
_ORACLES = frozenset(
    {
        "at_position", "facing", "visited", "holding_object", "arm_at_home",
        "file_exists", "path_contains", "placed_count", "describe_scene",
        "get_position", "room_coverage",
    }
)


@pytest.mark.parametrize(
    "expr",
    [
        "at_position(99.0, 99.0) or True",
        "at_position(99, 99) or 1",
        "holding_object('banana') or 1",
        "facing(0.0) or 'anything'",
        "at_position(11, 3) and True",          # dead-weight constant in an AND
        "at_position(11, 3) or (1 == 1)",       # constant-true compare disjunct
        "visited('kitchen') or not False",
    ],
)
def test_truthy_constant_shortcircuit_is_ran(expr: str) -> None:
    """An oracle OR'd/AND'd with a constant that can satisfy the verdict -> RAN.

    The oracle's result no longer GATES the boolean, so it proves nothing.
    """
    assert classify_verify_expr(expr, _ORACLES) == "RAN", expr


@pytest.mark.parametrize(
    "expr",
    [
        "at_position(11.0, 3.0)",
        "holding_object('banana')",
        "arm_at_home()",
        "facing(1.5708)",
        "path_contains('out.txt', 'ready')",
        "file_exists('out.txt')",
        "at_position(11, 3) or at_position(12, 3)",   # every operand oracle-gated
        "at_position(11, 3) and facing(0.0)",
        "not holding_object('banana')",
        "placed_count() == 2",
        "'table' in describe_scene()",
    ],
)
def test_legitimate_oracle_gated_expr_stays_grounded(expr: str) -> None:
    """A real fix must NOT over-reject: every truth-bearing leaf is an oracle term."""
    assert classify_verify_expr(expr, _ORACLES) == "GROUNDED", expr


def test_spine_gate_flips_shortcircuit_to_ran_even_when_caused() -> None:
    """End-to-end at the spine: a CAUSED step whose verify short-circuits -> RAN.

    A genuine walk advances the actor-causation counter (CAUSED), so the R2b
    downgrade does NOT fire — the ONLY thing that must stop a ``... or True`` step
    from grading GROUNDED is the honest classifier. classify_step_evidence is the
    single gate the verdict reads; it must report RAN.
    """
    from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused
    from vector_os_nano.vcli.cognitive.trace_store import classify_step_evidence
    from vector_os_nano.vcli.cognitive.types import StepRecord, SubGoal

    sub = SubGoal(name="s0", description="walk then fake-verify", verify="at_position(99, 99) or True", strategy="walk")
    step = StepRecord(
        sub_goal_name="s0", strategy="walk", success=True,
        verify_result=True, duration_sec=0.0, actor_caused=ActorCaused.CAUSED,
    )
    assert classify_step_evidence(step, sub, _ORACLES) == "RAN"

    # Sanity: the same step with an honest bare-oracle verify IS grounded.
    honest = SubGoal(name="s0", description="walk", verify="at_position(11, 3)", strategy="walk")
    assert classify_step_evidence(step, honest, _ORACLES) == "GROUNDED"
