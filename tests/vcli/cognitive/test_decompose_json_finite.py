# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""E192 — the untrusted LLM-plan JSON boundary rejects non-finite numbers LOUD.

DEFENSE-IN-DEPTH / CONSOLIDATION, not a fresh fail-open. E187-E191 gated each
downstream sink against NaN/inf (manifest loader / arm ``move_joints`` / base
``set_velocity`` / nav goal / blocking ``walk_forward``+``turn``) — so post-E191
every KNOWN numeric sink already raises loudly, and this source gate does NOT
close a currently-open hole. What it adds:

  1. It moves the check to the ROOT — the single untrusted-input boundary all
     five sinks funnel through (the goal decomposer parses ``response.text``, i.e.
     whatever the model emits). This is the E154 "a root-fix beats an enumeration
     of sinks that rots" recipe + the security floor "validate ALL external input
     at the boundary": a FUTURE primitive added without its own finiteness gate
     can't be reached by a non-finite plan value.
  2. It closes a foot-gun the E187-E191 threat models never named: an OVERFLOWING
     numeric literal (e.g. ``1e999``) is coerced to ``inf`` by ``json.loads``
     WITHOUT ``parse_constant`` ever firing — so the strict loader also scans the
     parsed tree, not just the bareword ``NaN``/``Infinity``/``-Infinity`` tokens.

A source-mirror (ast) test keeps a future parse site from silently skipping it.

Hermetic: no LLM, no mujoco.
"""
from __future__ import annotations

import ast
import inspect
import json
import math
from pathlib import Path
from typing import Any

import pytest

from vector_os_nano.vcli.cognitive import goal_decomposer as gd
from vector_os_nano.vcli.cognitive.goal_decomposer import GoalDecomposer, _loads_finite
from vector_os_nano.vcli.cognitive.types import GoalTree


# ---------------------------------------------------------------------------
# Mock backend (mirrors test_decompose_json_robust.py)
# ---------------------------------------------------------------------------


class _MockBackend:
    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0

    def call(self, messages, tools, system, max_tokens, on_text=None):
        self.calls += 1
        resp = self._response

        class _R:
            text = resp

        return _R()


_STRATEGIES = frozenset({"walk_forward", "turn", "home_skill"})
_VERIFY_FNS = frozenset({"detect_objects", "arm_at_home"})


def _decomposer(backend: Any) -> GoalDecomposer:
    return GoalDecomposer(
        backend,
        strategies=_STRATEGIES,
        verify_functions=_VERIFY_FNS,
        fallback_verify="True",
        has_base=True,
    )


# ---------------------------------------------------------------------------
# Foot-gun 1 — the bareword constants NaN / Infinity / -Infinity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_loads_finite_rejects_bareword_nonfinite(token: str) -> None:
    with pytest.raises(json.JSONDecodeError):
        _loads_finite('{"distance": %s}' % token)


# ---------------------------------------------------------------------------
# Foot-gun 2 — an OVERFLOWING literal (parse_constant never fires for this).
# ---------------------------------------------------------------------------


def test_loads_finite_rejects_overflow_literal() -> None:
    # 1e999 overflows to +inf; bare json.loads accepts it silently.
    assert math.isinf(json.loads("1e999"))
    with pytest.raises(json.JSONDecodeError):
        _loads_finite('{"distance": 1e999}')
    with pytest.raises(json.JSONDecodeError):
        _loads_finite('{"distance": -1e999}')


def test_loads_finite_rejects_nested_nonfinite() -> None:
    with pytest.raises(json.JSONDecodeError):
        _loads_finite('{"sub_goals": [{"strategy_params": {"angle": Infinity}}]}')
    with pytest.raises(json.JSONDecodeError):
        _loads_finite('{"a": [1.0, 2.0, [3.0, 1e999]]}')


# ---------------------------------------------------------------------------
# No false-reject — every finite plan still round-trips unchanged.
# ---------------------------------------------------------------------------


def test_loads_finite_accepts_finite_plan() -> None:
    src = json.dumps(
        {
            "goal": "walk",
            "sub_goals": [
                {"name": "go", "strategy_params": {"distance": 2.0, "angle": -90}}
            ],
            "count": 0,
            "flag": True,
            "nothing": None,
        }
    )
    data = _loads_finite(src)
    assert data["sub_goals"][0]["strategy_params"]["distance"] == 2.0
    assert data["sub_goals"][0]["strategy_params"]["angle"] == -90
    assert data["flag"] is True and data["nothing"] is None


# ---------------------------------------------------------------------------
# End-to-end — a non-finite plan from the (untrusted) LLM must NOT reach a
# primitive: decompose fails the parse LOUD and falls back to a single step.
# ---------------------------------------------------------------------------


def _nonfinite_walk_plan_json() -> str:
    plan = {
        "goal": "walk forward a bit",
        "sub_goals": [
            {
                "name": "walk",
                "description": "walk forward",
                "verify": "True",
                "strategy": "walk_forward",
                "depends_on": [],
                "strategy_params": {"distance": float("nan")},
            }
        ],
        "context_snapshot": "",
    }
    # allow_nan=True (default) emits the bare `NaN` token — exactly what a
    # hallucinating / adversarial model can return.
    return json.dumps(plan)


def test_decompose_nonfinite_plan_falls_back_no_phantom() -> None:
    raw = _nonfinite_walk_plan_json()
    assert "NaN" in raw  # sanity: the untrusted text really carries the token
    backend = _MockBackend(raw)
    tree = _decomposer(backend).decompose("walk forward a bit", "scene")
    assert isinstance(tree, GoalTree)
    # Parse rejected -> bounded retry -> single-step fallback. NEVER a phantom
    # multi-step plan carrying a non-finite distance into walk_forward.
    assert len(tree.sub_goals) == 1
    assert tree.sub_goals[0].name == "execute_task"
    # And no sub_goal anywhere carries a non-finite numeric param.
    for sg in tree.sub_goals:
        for value in sg.strategy_params.values():
            if isinstance(value, float):
                assert math.isfinite(value)


# ---------------------------------------------------------------------------
# Source mirror — every json.loads in the module goes through _loads_finite, so
# a NEW parse site cannot silently skip the finiteness gate (E188-E191 pattern).
# ---------------------------------------------------------------------------


def test_all_json_loads_go_through_strict_loader() -> None:
    source = Path(inspect.getsourcefile(gd)).read_text(encoding="utf-8")
    tree = ast.parse(source)

    helper: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_loads_finite":
            helper = node
            break
    assert helper is not None, "strict loader _loads_finite must exist"
    lo, hi = helper.lineno, helper.end_lineno or helper.lineno

    loads_lines = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "loads"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "json"
    ]
    assert loads_lines, "expected at least one json.loads (inside the strict loader)"
    stray = [ln for ln in loads_lines if not (lo <= ln <= hi)]
    assert not stray, (
        "bare json.loads outside _loads_finite (skips the finiteness gate) at "
        f"lines {stray}"
    )
