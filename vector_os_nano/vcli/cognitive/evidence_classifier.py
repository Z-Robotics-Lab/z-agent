# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""evidence_classifier — separate GROUNDED verify predicates from RAN (no real,
non-tautological world evidence).

R1 of the Campaign-#13 honest-verification redesign. The legacy evidence gate
short-circuited ``if is_robot: return True``, auto-passing every robot step
regardless of its verify result. The honest replacement keys verification on
whether the deterministic verify expression actually reads world state in a way
the ACTOR (which authors the verify string) cannot trivially satisfy.

Foolability axis (2026-06-18 red-team): a verify string is real evidence only when
it CONSUMES a sim/world oracle AND is not a tautology the author can make true by
choice of string. Two oracle kinds:

- PREDICATE oracles (bool, goal-conditioned; the author supplies the goal as
  arguments, e.g. ``at_position(2.0, 0.0)``, ``arm_at_home()``): a BARE call is
  GROUNDED — it is True only if the world actually reached that goal.
- STATE oracles (return raw values, e.g. ``get_position()``, ``describe_scene()``):
  a bare call is NOT evidence (always truthy / shape-trivial); it is GROUNDED only
  inside a comparison against a CONSTANT (``placed_count() == 2``,
  ``'table' in describe_scene()``).

The GROUNDED test requires the oracle's RESULT to GATE the verdict — every
truth-bearing leaf of the boolean expr must be an oracle term (``_is_grounded_node``,
recursive). A constant/non-oracle operand that could short-circuit the verdict True
(``at_position(99,99) or True``, ``... or 1``) classifies RAN (2026-06-19 review hole).

SCOPE (honest — do not overclaim): this is a STRUCTURAL guard only. It does NOT
verify that the constant is the TASK's real goal (an author could still write
``at_position(<current coords>)``), nor catch shape-trivial state compares
(``len(get_position()) == 3``), nor — for NON-robot predicates — that the actor
CAUSED the state (a dev ``file_exists('/etc/passwd')`` with no write classifies
GROUNDED). Goal AUTHENTICITY / actor-causation for state+dev predicates is DEFERRED
to the actor-causation layer, which today grades only ROBOT predicates (base/arm/
gripper). R1 rejects the obvious tautologies (no oracle; oracle-vs-itself; bare state
oracle; truthy-constant short-circuit) so the moat is not a NEW false-green dressed
up as verification.
"""
from __future__ import annotations

import ast
from typing import Literal

Verdict = Literal["GROUNDED", "RAN"]

# Sentinels the decomposer / robot motor steps emit when there is no predicate.
_NO_EVIDENCE: frozenset[str] = frozenset({"", "True"})

# Oracle names returning a goal-conditioned bool — a BARE call is real evidence.
# A NEW semantic axis (R1): bool-returning, author-supplies-the-goal predicates.
# R2 should derive this from oracle return-type metadata rather than a kernel list.
_PREDICATE_ORACLES: frozenset[str] = frozenset(
    {
        "at_position",
        "facing",
        "visited",
        "holding_object",
        "arm_at_home",
        "file_exists",
        # path_contains(path, substr) is a goal-conditioned bool (the author
        # supplies the substring goal; True only if the file actually contains
        # it) — same category as file_exists, so a bare call is GROUNDED.
        "path_contains",
    }
)


def _oracle_calls(tree: ast.AST, oracle_names: frozenset[str]) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id in oracle_names
    ]


def _calls_predicate_oracle(calls: list[ast.Call]) -> bool:
    return any(
        isinstance(c.func, ast.Name) and c.func.id in _PREDICATE_ORACLES for c in calls
    )


def _contains_oracle(node: ast.AST, oracle_names: frozenset[str]) -> bool:
    return bool(_oracle_calls(node, oracle_names))


def _contains_constant(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Constant) for n in ast.walk(node))


def _is_self_tautology(tree: ast.AST) -> bool:
    """True if any Compare or BinOp has structurally-identical operands (``X op X``).

    Catches ``get_position() == get_position()`` and the self-cancelling
    ``get_position()[0] - get_position()[0]``.
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare):
            operands = [n.left, *n.comparators]
            dumps = [ast.dump(o) for o in operands]
            if len(set(dumps)) < len(dumps):
                return True
        elif isinstance(n, ast.BinOp):
            if ast.dump(n.left) == ast.dump(n.right):
                return True
    return False


def _state_oracle_vs_constant(tree: ast.AST, oracle_names: frozenset[str]) -> bool:
    """True if a STATE oracle appears inside a Compare against an ``ast.Constant``.

    Rejects oracle-vs-oracle comparisons (every operand carries an oracle and no
    operand is a bare constant) — those prove nothing about a goal.
    """
    for n in ast.walk(tree):
        if not isinstance(n, ast.Compare):
            continue
        operands = [n.left, *n.comparators]
        has_oracle = any(_contains_oracle(o, oracle_names) for o in operands)
        has_const = any(_contains_constant(o) for o in operands)
        oracle_only = all(_contains_oracle(o, oracle_names) for o in operands)
        if has_oracle and has_const and not oracle_only:
            return True
    return False


def _is_grounded_node(node: ast.AST, oracle_names: frozenset[str]) -> bool:
    """True iff *node*'s truth value is GATED by world-oracle results — i.e. NO
    constant or non-oracle operand can short-circuit it to True.

    Closes the short-circuit moat hole (2026-06-19 review): the old test merely
    checked that a predicate oracle was CALLED somewhere in the AST, so
    ``at_position(99,99) or True`` classified GROUNDED (and short-circuits to True
    regardless of real position). This walks the boolean structure and requires
    EVERY truth-bearing leaf to be an oracle term, recursively:

    - ``and`` / ``or``: every operand must itself be grounded (a constant/non-oracle
      operand could make ``or`` True, or is dead weight in ``and``) — reject either.
    - ``not X``: grounded iff ``X`` is grounded.
    - a Compare: an oracle anchored against a CONSTANT (state-oracle-vs-constant or a
      predicate-oracle-vs-constant), never oracle-vs-oracle (proves no goal) and
      never constant-only.
    - a bare Call: grounded ONLY for a PREDICATE oracle (goal-conditioned bool); a
      bare STATE oracle is not evidence.
    - anything else (a bare Constant, a non-oracle Name/Call, a Subscript, …):
      NOT grounded.

    This only ever makes the gate STRICTER (rule 5): every expr it now rejects was a
    way to satisfy the verdict without the oracle's result determining it.
    """
    if isinstance(node, ast.BoolOp):
        return bool(node.values) and all(
            _is_grounded_node(v, oracle_names) for v in node.values
        )
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_grounded_node(node.operand, oracle_names)
    if isinstance(node, ast.Compare):
        operands = [node.left, *node.comparators]
        has_oracle = any(_contains_oracle(o, oracle_names) for o in operands)
        has_const = any(_contains_constant(o) for o in operands)
        oracle_only = all(_contains_oracle(o, oracle_names) for o in operands)
        return has_oracle and has_const and not oracle_only
    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Name) and node.func.id in _PREDICATE_ORACLES
    return False


def classify_verify_expr(expr: str, oracle_names: frozenset[str]) -> Verdict:
    """Classify a verify expression as GROUNDED or RAN.

    GROUNDED: the expression consumes a world oracle in a non-tautological way —
    either a bare PREDICATE-oracle call (goal-conditioned bool), or a STATE-oracle
    compared against a constant. RAN: a sentinel (``""`` / ``"True"``), a syntax
    error, no oracle at all, or a tautology (oracle-vs-itself / bare state oracle).

    *oracle_names* MUST be the live verify-namespace callable names, single-sourced
    from ``engine._build_verifier_namespace`` / ``World.build_verify_namespace`` and
    passed in — never a hand-authored second copy (rule 3). Goal AUTHENTICITY is
    deferred to R2 (see the module docstring); this is a structural guard only.
    """
    s = (expr or "").strip()
    if s in _NO_EVIDENCE:
        return "RAN"
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return "RAN"
    calls = _oracle_calls(tree, oracle_names)
    if not calls:
        return "RAN"
    if _is_self_tautology(tree):
        return "RAN"
    # GROUNDED only if the expr's truth is GATED by oracle results — no constant /
    # non-oracle operand can short-circuit it (closes the ``... or True`` hole). This
    # subsumes the old "bare predicate-oracle call" and "state-oracle-vs-constant"
    # rules while rejecting a truthy-constant escape.
    if _is_grounded_node(tree.body, oracle_names):
        return "GROUNDED"
    return "RAN"
