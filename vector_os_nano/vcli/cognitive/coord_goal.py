# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Goal-authenticity helpers (STEP 13) — does the verify CONSTANT match the user's
real task goal?

The honest moat (R1 structural + R2b actor-causation) proves a step consumed a real
oracle AND the actor caused the state change — but NOT that the verify constant is the
coordinate the USER asked for. A model could do a real actor-caused walk to the WRONG
place and verify ``at_position(<its own landing>)`` to self-certify success. These PURE
helpers let the grader (``classify_step_evidence``) REJECT such a goal-mismatch for
COORDINATE goals.

Properties (rule 5 / honest-by-construction):
- STRICTER-only: the grader uses these ONLY to downgrade GROUNDED -> RAN, never the
  reverse.
- FAIL-OPEN: a None on either side (no coordinate goal, or a non-``at_position`` /
  non-literal verify) means "no mismatch" — the existing classification stands. So
  dev / grasp / facing / coordinate-less turns are untouched.
- Honest: the target is parsed from ``goal_tree.goal`` (the user's NL command, passed
  verbatim by the producer), NEVER from actor-authored state. The model authors only
  the verify expr, never the goal — so it cannot make the parsed target equal its
  landing.
"""
from __future__ import annotations

import ast
import math
import re

# First (x, y) numeric pair in parentheses — matches "走到坐标 (11.0,3.0)" and
# "go to (11,3)" (optional sign / decimals / whitespace).
_COORD_RE = re.compile(r"\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)")


def _at_position_tol() -> float:
    """The SAME tolerance the ``at_position`` oracle uses (single-sourced, fail-safe).

    Re-read, never re-authored, so the check can never disagree with the oracle.
    """
    try:
        from vector_os_nano.vcli.worlds.go2_sim_oracle import _AT_POSITION_TOL_M

        return float(_AT_POSITION_TOL_M)
    except Exception:  # noqa: BLE001
        return 0.5


def parse_goal_coord(goal_text: str | None) -> tuple[float, float] | None:
    """The user's commanded (x, y) target parsed from the NL goal, or None.

    None when there is no coordinate, or MORE THAN ONE DISTINCT coordinate (ambiguous)
    — both fail OPEN. Derived ONLY from the user's words.
    """
    if not goal_text:
        return None
    matches = _COORD_RE.findall(goal_text)
    if not matches:
        return None
    coords = {(float(x), float(y)) for x, y in matches}
    if len(coords) != 1:
        return None  # ambiguous -> fail open
    return next(iter(coords))


def _const_number(node: ast.AST) -> float | None:
    """A numeric literal (incl. a unary +/- on one), else None (never a bool)."""
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        inner = _const_number(node.operand)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    return None


def at_position_const(expr: str | None) -> tuple[float, float] | None:
    """The literal (x, y) of an ``at_position(x, y[, tol])`` verify, or None.

    None for any non-``at_position`` predicate, or an ``at_position`` whose first two
    args are not numeric literals (a state-derived target) -> fail OPEN.
    """
    if not expr:
        return None
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "at_position"
            and len(node.args) >= 2
        ):
            x = _const_number(node.args[0])
            y = _const_number(node.args[1])
            if x is None or y is None:
                return None
            return (x, y)
    return None


def coord_goal_mismatch(
    goal_text: str | None, expr: str | None, tol: float | None = None
) -> bool:
    """True iff BOTH a coordinate goal and an ``at_position`` constant parse AND they
    differ by more than *tol* (default = the at_position oracle tolerance).

    FAIL-OPEN (returns False) whenever either side is not a parseable coordinate, so a
    non-coordinate turn is never rejected.
    """
    goal_xy = parse_goal_coord(goal_text)
    const_xy = at_position_const(expr)
    if goal_xy is None or const_xy is None:
        return False
    t = _at_position_tol() if tol is None else float(tol)
    return math.dist(goal_xy, const_xy) > t
