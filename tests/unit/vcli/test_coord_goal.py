# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""STEP 13 — goal-authenticity: the verify CONSTANT must match the user's coordinate goal.

A model that does a REAL actor-caused walk to the WRONG place then verifies
``at_position(<its own landing>)`` used to grade verified=True (the moat never compared
the verify constant to the user's commanded target). These tests pin the pure helpers
and the spine downgrade: a goal-mismatched coordinate verify -> RAN; an honest one ->
GROUNDED; every non-coordinate turn fails OPEN (unchanged). Stricter-only (rule 5)."""
from __future__ import annotations

import pytest

from vector_os_nano.vcli.cognitive.coord_goal import (
    at_position_const,
    coord_goal_mismatch,
    parse_goal_coord,
)

_ORACLES = frozenset(
    {"at_position", "facing", "visited", "holding_object", "arm_at_home",
     "file_exists", "path_contains"}
)


@pytest.mark.parametrize(
    "goal, expected",
    [
        ("走到坐标 (11.0,3.0)", (11.0, 3.0)),
        ("go to (11,3)", (11.0, 3.0)),
        ("走到坐标 (-2.5, 0)", (-2.5, 0.0)),
        ("create out.txt containing ready", None),
        ("把香蕉抓起来拿在手里", None),
        ("(1,2) then (3,4)", None),           # ambiguous -> fail open
        ("到 (5,5) 再回 (5,5)", (5.0, 5.0)),   # same coord twice -> unambiguous
        ("", None),
        (None, None),
    ],
)
def test_parse_goal_coord(goal, expected) -> None:
    assert parse_goal_coord(goal) == expected


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("at_position(11.0, 3.0)", (11.0, 3.0)),
        ("at_position(11, 3, 0.5)", (11.0, 3.0)),
        ("at_position(-2, 0)", (-2.0, 0.0)),
        ("facing(1.5708)", None),
        ("holding_object('banana')", None),
        ("path_contains('out.txt', 'ready')", None),
        ("at_position(get_x(), 3)", None),    # non-literal target -> fail open
        ("len(get_position()) == 3", None),
        ("", None),
    ],
)
def test_at_position_const(expr, expected) -> None:
    assert at_position_const(expr) == expected


def test_coord_goal_mismatch() -> None:
    # mismatch: a real walk to the WRONG place (dist 1.0 > 0.5 tol)
    assert coord_goal_mismatch("走到坐标 (11.0,3.0)", "at_position(10.0, 3.0)", 0.5) is True
    # match: at the goal
    assert coord_goal_mismatch("走到坐标 (11.0,3.0)", "at_position(11.0, 3.0)", 0.5) is False
    # within tol -> no mismatch
    assert coord_goal_mismatch("走到坐标 (11.0,3.0)", "at_position(11.3, 3.0)", 0.5) is False
    # fail-open: no coordinate goal
    assert coord_goal_mismatch("把香蕉抓起来", "at_position(99.0, 99.0)", 0.5) is False
    # fail-open: non-coordinate verify
    assert coord_goal_mismatch("走到坐标 (11.0,3.0)", "facing(0.0)", 0.5) is False
    # default tol re-reads the oracle's _AT_POSITION_TOL_M (0.5) -> still a mismatch
    assert coord_goal_mismatch("走到坐标 (11.0,3.0)", "at_position(8.0, 3.0)") is True


# ---------------------------------------------------------------------------
# Spine: classify_step_evidence downgrades a goal-mismatched CAUSED at_position
# to RAN, keeps an honest one GROUNDED, and fails OPEN for everything else.
# ---------------------------------------------------------------------------


def _caused_step(verify: str):
    from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused
    from vector_os_nano.vcli.cognitive.types import StepRecord, SubGoal

    sg = SubGoal(name="s0", description="walk", verify=verify, strategy="walk")
    step = StepRecord(
        sub_goal_name="s0", strategy="walk", success=True,
        verify_result=True, duration_sec=0.1, actor_caused=ActorCaused.CAUSED,
    )
    return step, sg


def test_spine_wrong_place_caused_walk_downgrades_to_ran() -> None:
    from vector_os_nano.vcli.cognitive.trace_store import classify_step_evidence

    step, sg = _caused_step("at_position(8.0, 3.0)")  # verified its OWN landing
    # No goal threaded -> unchanged GROUNDED (the pre-STEP-13 residual).
    assert classify_step_evidence(step, sg, _ORACLES) == "GROUNDED"
    # With the user's real goal (11,3): the constant (8,3) mismatches -> RAN.
    assert classify_step_evidence(step, sg, _ORACLES, "走到坐标 (11.0,3.0)") == "RAN"


def test_spine_honest_coordinate_stays_grounded() -> None:
    from vector_os_nano.vcli.cognitive.trace_store import classify_step_evidence

    step, sg = _caused_step("at_position(11.0, 3.0)")
    assert classify_step_evidence(step, sg, _ORACLES, "走到坐标 (11.0,3.0)") == "GROUNDED"


@pytest.mark.parametrize(
    "verify, goal",
    [
        ("holding_object('banana')", "把香蕉抓起来拿在手里"),        # non-coord verify + goal
        ("path_contains('out.txt', 'ready')", "create out.txt containing ready"),
        ("facing(0.0)", "走到坐标 (11.0,3.0)，然后转向"),            # coord goal but facing verify
        ("at_position(8.0, 3.0)", "向前走两米"),                     # at_position verify, no coord goal
    ],
)
def test_spine_non_coordinate_fails_open_stays_grounded(verify, goal) -> None:
    from vector_os_nano.vcli.cognitive.trace_store import classify_step_evidence

    step, sg = _caused_step(verify)
    assert classify_step_evidence(step, sg, _ORACLES, goal) == "GROUNDED"
