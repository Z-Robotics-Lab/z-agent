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


# A coordinate verify may pass an explicit arrival tolerance (``at_position(x, y, tol)``).
# An HONEST arrival check uses a small radius (the oracle default 0.5 m, or up to a metre
# or two for a generous "reached the vicinity"); a model trying to self-certify from
# anywhere inflates it (``tol=99`` = "within 99 m" = true across the whole map). This is
# the line between the two: an explicit tol ABOVE it makes the predicate vacuous and the
# verify is not an honest "reached (x, y)" assertion. Generous on purpose (accepts honest
# 0.5–2 m), so it only ever rejects an EGREGIOUS tolerance (stricter-only, rule 5).
_MAX_ARRIVAL_TOL_M: float = 2.0


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

    None (fail OPEN) for any non-``at_position`` predicate, or an ``at_position`` whose
    coordinate args are not numeric literals (a state-derived target).

    Hardened (STEP-15) against two model-authored evasions that kept a goal-matching
    constant while making the predicate vacuous:
      * KWARG form ``at_position(x=11, y=3)`` — the ``x=``/``y=`` keywords are read when
        the positional args are absent (a shipped false-green: it used to extract None
        -> fail open -> a wrong-coord kwarg verify passed the per-step gate).
      * TOL-INFLATION ``at_position(11, 3, 99)`` / ``tol=99`` — an explicit tolerance
        LITERAL above ``_MAX_ARRIVAL_TOL_M`` makes the predicate "within 99 m of (11,3)",
        i.e. true almost anywhere; not an honest "reached (x,y)" assertion, so it returns
        None (fail CLOSED for every downstream coordinate check:
        ``coord_goal_mismatch`` and ``at_position_const_matches``). A non-literal
        (state-derived) tol is likewise rejected.
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
        ):
            # Coordinate from positional (x, y) or, failing that, x=/y= keywords.
            x = y = None
            if len(node.args) >= 2:
                x = _const_number(node.args[0])
                y = _const_number(node.args[1])
            else:
                kw = {k.arg: k.value for k in node.keywords if k.arg in ("x", "y")}
                if "x" in kw and "y" in kw:
                    x = _const_number(kw["x"])
                    y = _const_number(kw["y"])
            if x is None or y is None:
                return None
            # Tolerance-bound: a 3rd positional arg or a ``tol=`` kwarg with an inflated
            # literal makes the predicate vacuous -> reject (fail closed).
            tol_node: ast.AST | None = None
            if len(node.args) >= 3:
                tol_node = node.args[2]
            else:
                for k in node.keywords:
                    if k.arg == "tol":
                        tol_node = k.value
                        break
            if tol_node is not None:
                tol_val = _const_number(tol_node)
                if tol_val is None or tol_val > _MAX_ARRIVAL_TOL_M:
                    return None
            return (x, y)
    return None


def at_position_const_matches(
    expr: str | None, goal_xy: tuple[float, float], tol: float | None = None
) -> bool:
    """True iff *expr* is a (bounded-tol) literal ``at_position`` whose constant is
    within *tol* of *goal_xy* (default = the at_position oracle tolerance).

    The POSITIVE dual of ``coord_goal_mismatch`` used by the turn-level coordinate gate
    (``evidence_passed``): it confirms a verify actually ASSERTS the commanded
    coordinate. Fail-CLOSED (returns False) for any non-``at_position`` / non-literal /
    tol-inflated verify (``at_position_const`` is None), so a turn that never honestly
    asserts the coordinate cannot satisfy the requirement.
    """
    const_xy = at_position_const(expr)
    if const_xy is None:
        return False
    t = _at_position_tol() if tol is None else float(tol)
    return math.dist(goal_xy, const_xy) <= t


# A looser coordinate-INTENT detector (paren OR paren-less ``x,y``): a numeric pair
# separated by a comma. Used ONLY to decide whether a coordinate requirement applies to
# a turn whose exact target ``parse_goal_coord`` could not pin (paren-less "导航到 11,3"
# or >=1 distinct coords). It NEVER extracts a target — ``parse_goal_coord`` stays the
# single authority for the actual (x, y).
_COORD_INTENT_RE = re.compile(
    r"[-+]?\d+(?:\.\d+)?\s*,\s*[-+]?\d+(?:\.\d+)?"
)


def goal_has_coordinate_intent(goal_text: str | None) -> bool:
    """True iff the NL goal contains a numeric ``x,y`` pair (parenthesised or not).

    A turn-gate helper for the parse-evasion case: when ``parse_goal_coord`` fails open
    (paren-less or multi-coordinate phrasing) the gate still requires SOME honest
    at_position evidence rather than silently falling back to the weaker all-GROUNDED
    rule. A goal with no numeric pair (room name, "explore", "turn") returns False ->
    fails open (unchanged).
    """
    if not goal_text:
        return False
    return bool(_COORD_INTENT_RE.search(goal_text))


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
