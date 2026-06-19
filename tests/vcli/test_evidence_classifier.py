# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit tests for the R1 evidence classifier (pure, no sim).

These ARE the moat test: the adversarial tautology cases MUST classify RAN, the
legitimate predicates GROUNDED. A regression here means the verify moat is foolable.
"""
import pytest

from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr

# Stand-in for the live verify namespace (predicate + state oracle names).
ORACLES = frozenset(
    {
        # predicate oracles (bool, goal-conditioned) — a bare call is GROUNDED
        "at_position",
        "facing",
        "visited",
        "holding_object",
        "arm_at_home",
        "file_exists",
        # state oracles (raw values) — GROUNDED only vs a constant
        "get_position",
        "get_heading",
        "describe_scene",
        "detect_objects",
        "placed_count",
        "nearest_room",
        "objects_in_room",
        "find_object",
        "room_coverage",
    }
)

GROUNDED = [
    "at_position(2.0, 0.0)",
    "arm_at_home()",
    "holding_object('apple')",
    "facing(-1.57)",
    "visited('kitchen')",
    "not holding_object()",  # the existing place verify
    "'table' in describe_scene()",
    "placed_count() == 2",
    "len(detect_objects()) > 0",
]

RAN = [
    "",
    "True",
    "1 == 1",  # no oracle
    "len([1, 2, 3]) == 3",  # no oracle
    "get_position()",  # bare state oracle (always truthy)
    "get_position() == get_position()",  # oracle vs itself
    "abs(get_position()[0] - get_position()[0]) < 1.0",  # self-cancelling tautology
    "this is not valid python (",  # syntax error -> RAN
]


@pytest.mark.parametrize("expr", GROUNDED)
def test_grounded(expr: str) -> None:
    assert classify_verify_expr(expr, ORACLES) == "GROUNDED", expr


@pytest.mark.parametrize("expr", RAN)
def test_ran(expr: str) -> None:
    assert classify_verify_expr(expr, ORACLES) == "RAN", expr


def test_empty_oracle_names_fails_closed() -> None:
    # With no oracle namespace, even a real predicate cannot be GROUNDED.
    assert classify_verify_expr("at_position(2.0, 0.0)", frozenset()) == "RAN"


@pytest.mark.xfail(
    reason="R1 known gap: a shape-trivial state-vs-constant compare reads an oracle "
    "but proves nothing about the goal; authenticity is deferred to R2's "
    "independent observer.",
    strict=True,
)
def test_r1_gap_shape_trivial_state_compare() -> None:
    assert classify_verify_expr("len(get_position()) == 3", ORACLES) == "RAN"
