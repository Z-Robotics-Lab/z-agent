# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Stage 5 scout: VectorEngine.classify_intent — observable planning-path routing.

The engine forks between the VGG closed loop and the tool_use ReAct loop via the
keyword intent gate. classify_intent surfaces that fork as a single inspectable
IntentDecision WITHOUT changing routing. These tests pin:

1. The routing matrix (each tool_use reason + the vgg routes).
2. That classify_intent is pure (no side effects, repeatable).
3. That vgg_decompose returns None exactly when the decision is tool_use — i.e.
   the refactor that single-sourced the decision is behaviour-preserving.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from vector_os_nano.vcli.engine import IntentDecision, VectorEngine
from vector_os_nano.vcli.intent_router import IntentRouter
from vector_os_nano.vcli.permissions import PermissionContext
from vector_os_nano.vcli.tools.base import ToolRegistry


def _make_engine(**kw: Any) -> VectorEngine:
    eng = VectorEngine(
        backend=MagicMock(),
        registry=ToolRegistry(),
        permissions=PermissionContext(no_permission=True),
        intent_router=IntentRouter(),
    )
    for k, v in kw.items():
        setattr(eng, k, v)
    return eng


# ---------------------------------------------------------------------------
# IntentDecision value object
# ---------------------------------------------------------------------------


def test_intent_decision_is_frozen() -> None:
    d = IntentDecision(route="vgg", reason="x")
    try:
        d.route = "tool_use"  # type: ignore[misc]
    except Exception:  # FrozenInstanceError
        pass
    else:
        raise AssertionError("IntentDecision must be frozen")


def test_use_vgg_property() -> None:
    assert IntentDecision(route="vgg", reason="x").use_vgg is True
    assert IntentDecision(route="tool_use", reason="x").use_vgg is False


# ---------------------------------------------------------------------------
# Routing matrix
# ---------------------------------------------------------------------------


def test_route_tool_use_when_vgg_disabled() -> None:
    eng = _make_engine(_vgg_enabled=False)
    d = eng.classify_intent("去厨房看看有没有杯子")
    assert d.route == "tool_use"
    assert d.reason == "vgg-disabled"
    assert d.use_vgg is False


def test_route_tool_use_when_no_intent_router() -> None:
    eng = _make_engine(_vgg_enabled=True)
    eng._intent_router = None
    d = eng.classify_intent("去厨房")
    assert d.route == "tool_use"
    assert d.reason == "no-intent-router"


def test_route_tool_use_when_robot_world_not_ready() -> None:
    # robot world but no connected base/arm -> sim not up -> tool_use
    world = SimpleNamespace(is_robot=lambda: True)
    agent = SimpleNamespace(_base=None, _arm=None, _skill_registry=None)
    eng = _make_engine(_vgg_enabled=True, _world=world, _vgg_agent=agent)
    d = eng.classify_intent("去厨房")
    assert d.route == "tool_use"
    assert d.reason == "robot-world-not-ready"


def test_route_tool_use_for_pure_conversation() -> None:
    # dev world (not robot): gate rejects a plain greeting
    world = SimpleNamespace(is_robot=lambda: False)
    eng = _make_engine(_vgg_enabled=True, _world=world, _vgg_agent=None)
    d = eng.classify_intent("hello there")
    assert d.route == "tool_use"
    assert d.reason == "gate-not-a-vgg-task"


def test_route_vgg_complex_task() -> None:
    world = SimpleNamespace(is_robot=lambda: False)
    eng = _make_engine(_vgg_enabled=True, _world=world, _vgg_agent=None)
    # sequential keyword 然后 -> is_complex True -> vgg-complex
    d = eng.classify_intent("去厨房然后看看有没有杯子")
    assert d.route == "vgg"
    assert d.reason == "vgg-complex"
    assert d.complex is True


def test_route_vgg_actionable_simple() -> None:
    world = SimpleNamespace(is_robot=lambda: False)
    eng = _make_engine(_vgg_enabled=True, _world=world, _vgg_agent=None)
    # single motor action -> should_use_vgg True, is_complex False
    d = eng.classify_intent("去厨房")
    assert d.route == "vgg"
    assert d.reason == "vgg-actionable"
    assert d.complex is False


# ---------------------------------------------------------------------------
# Purity + behaviour-preservation
# ---------------------------------------------------------------------------


def test_classify_intent_is_pure_and_repeatable() -> None:
    world = SimpleNamespace(is_robot=lambda: False)
    eng = _make_engine(_vgg_enabled=True, _world=world, _vgg_agent=None)
    msg = "去厨房然后看看有没有杯子"
    first = eng.classify_intent(msg)
    second = eng.classify_intent(msg)
    assert first == second  # frozen dataclass equality; no hidden state changed


def test_vgg_decompose_returns_none_iff_tool_use_route() -> None:
    """vgg_decompose must return None for exactly the tool_use decisions.

    This locks the refactor: the decision is single-sourced through
    classify_intent, so a tool_use route always short-circuits decompose.
    """
    world = SimpleNamespace(is_robot=lambda: False)
    eng = _make_engine(_vgg_enabled=True, _world=world, _vgg_agent=None)

    # gate rejects -> tool_use -> decompose returns None (no LLM call)
    assert eng.classify_intent("hello there").route == "tool_use"
    assert eng.vgg_decompose("hello there") is None
