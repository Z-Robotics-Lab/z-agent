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
        # resting_on_receptacle() — the D106 CEO-APPROVED, D116 moat-proven place
        # oracle, PRE-BOUND to the scene receptacle (zero "goal" args; robot.py wraps
        # it arg-tolerant). Returns >=1 ONLY when a held->released object is AT REST on
        # the receptacle at its rest height (xy in region AND |z-rest_z|<=band AND
        # speed<at-rest AND not held) — strictly STRONGER than placed_count (which would
        # also count a FLOOR drop in the same xy). A bare call is True only if the world
        # reached the place goal, so it is GROUNDED like the other goal-conditioned
        # predicates. RED-TEAMED: 0 before the place, 0 for a floor/mid-air/held object,
        # 1 only after a real settled placement (D116 adversarial + D133 in-cli). This
        # is the 2nd deliberate vcli/cognitive edit since D69 — additive, recognising the
        # already-approved+moat-proven oracle so a bare-cli pick-AND-place can GROUND.
        "resting_on_receptacle",
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


def _is_oracle_call(node: ast.AST, oracle_names: frozenset[str]) -> bool:
    """True iff *node* is DIRECTLY an oracle call (its value comes from the world)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in oracle_names
    )


def _truth_bearing_oracle(node: ast.AST, oracle_names: frozenset[str]) -> bool:
    """True iff *node*'s VALUE is determined by an oracle result — the oracle's value
    actually reaches the node's value, not discarded into a constant structure or a
    non-oracle reduction.

    A direct oracle call carries its value; so does an index / arithmetic over one
    (``get_position()[0]``, ``get_heading() - 1``), and a reduction whose ARGUMENT is
    itself truth-bearing (``len(detect_objects()) > 0`` — the count reflects the
    oracle's actual return). But an oracle buried inside a LITERAL or builtin-constructed
    CONTAINER (``len(tuple((at_position(x,y), True)))`` — the tuple's length is constant
    and the oracle is an inert element, never reduced) is dead weight, NOT truth-bearing.
    Closes the callable-container bypass (2026-06-20 review). STRICTER-only.
    """
    if _is_oracle_call(node, oracle_names):
        return True
    if isinstance(node, ast.Subscript):
        return _truth_bearing_oracle(node.value, oracle_names)
    if isinstance(node, ast.BinOp):
        return _truth_bearing_oracle(node.left, oracle_names) or _truth_bearing_oracle(
            node.right, oracle_names
        )
    if isinstance(node, ast.UnaryOp) and not isinstance(node.op, ast.Not):
        return _truth_bearing_oracle(node.operand, oracle_names)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        # A non-oracle reduction (len/bool/sorted/...) carries the oracle's value IFF it
        # reduces a DIRECTLY truth-bearing ARGUMENT (len(detect_objects())). An oracle
        # buried inside a literal / builtin-constructed CONTAINER (len(tuple((x, True))))
        # is inert — we do NOT descend into literal container ELEMENTS, only call args.
        return any(_truth_bearing_oracle(a, oracle_names) for a in node.args)
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
    - a Compare (equality/ordering): a TRUTH-BEARING oracle (its value reaches the
      operand — a direct call, or an index/arithmetic over one) anchored against a
      CONSTANT; an oracle buried inside a non-oracle reduction (``len(...)``,
      ``tuple(...)``, ``bool(...)``) is dead weight, NOT grounded.
    - a Compare (membership ``in``/``not in``): grounded ONLY if the CONTAINER is a
      DIRECT oracle call (``'table' in describe_scene()``); a literal container OR a
      builtin constructor (``True in tuple((at_position(9,9), True))``) is a constant-
      structure container — the oracle is dead weight — so it is NOT grounded.
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
        # Membership (`X in Y` / `X not in Y`): grounded ONLY if the CONTAINER being
        # searched is oracle-derived (its collection comes from the world, e.g.
        # `'table' in describe_scene()`). A constant-literal container (tuple/list/
        # set/dict) makes membership constant-structure-determined — an oracle buried
        # inside it is dead weight, the `... or True` short-circuit hidden in an `in`
        # node (e.g. `True in (at_position(9,9), True)`). -> NOT grounded. [STEP-12]
        if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
            for op, container in zip(node.ops, node.comparators):
                if not isinstance(op, (ast.In, ast.NotIn)):
                    continue
                # The container must be a DIRECT oracle call (its collection comes from
                # the world, e.g. `describe_scene()`). A literal collection OR a builtin
                # container constructor (`tuple(...)`/`list(...)`/`set(...)`) is a
                # constant-structure container — an oracle buried inside is dead weight
                # (`... or True` hidden in an `in` node). -> NOT grounded. [STEP-12/14]
                if not _is_oracle_call(container, oracle_names):
                    return False
            return True
        # Equality / ordering: an oracle anchored against a CONSTANT (state-oracle-vs-
        # constant or predicate-oracle-vs-constant), never oracle-vs-oracle (proves no
        # goal) and never constant-only.
        operands = [node.left, *node.comparators]
        # A TRUTH-BEARING oracle operand (value reaches it) vs a constant — never an
        # oracle buried inside a non-oracle reduction like len()/tuple()/bool(), which
        # discards the oracle's value into a structural constant. [STEP-14]
        has_oracle = any(_truth_bearing_oracle(o, oracle_names) for o in operands)
        has_const = any(_contains_constant(o) for o in operands)
        oracle_only = all(_truth_bearing_oracle(o, oracle_names) for o in operands)
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
