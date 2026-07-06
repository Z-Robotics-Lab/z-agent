# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""S5c — a REGISTRY-DRIVEN native-attempt hint, shadow/parity with the keyword router.

The native producer routes by the MODEL reading tool DESCRIPTIONS, not by a keyword
table — so the only PRE-gate question ("is it worth attempting native?") collapses to
"does this world expose any actionable tool the model could dispatch?". This is
``should_attempt_native`` — derived SINGLE-SOURCE from ``_build_motor_tools`` (the exact
toolset the native loop offers; Rule 3), never a keyword cascade.

This module PROVES the registry-driven hint is a VIABLE replacement for the keyword
``IntentRouter.should_use_vgg`` (which S8 will retire) WITHOUT changing any behavior yet
(shadow/parity): the critical correctness property is that it NEVER MISSES an actionable
command the keyword router catches — i.e. for every input where ``should_use_vgg`` is
True, ``should_attempt_native`` is also True (a safe SUPERSET). Its extra attempts
(chat / questions, where the keyword router says "skip") are FAIL-OPEN: native takes no
action and falls back to legacy — a wasted LLM call, never a missed or wrong command.
"""
from __future__ import annotations

import pytest

from zeno.vcli import native_loop
from zeno.vcli.intent_router import IntentRouter


# Commands the keyword router routes to VGG (actionable) — the SET that must NOT be missed.
_ACTIONABLE = [
    "走到坐标 (11,3)",
    "抓红色的罐子",
    "探索这个房间",
    "navigate to the kitchen",
    "patrol the area",
    "去厨房然后看看有没有杯子",  # complex (multi-step)
    "stand up",
    "把前面的东西抓起来",
]

# Inputs the keyword router does NOT route to VGG (chat / questions / sim-mgmt / trivial).
_NON_ACTIONABLE = [
    "你好",
    "为什么一开始那么卡?",
    "what is your name?",
    "启动 go2 仿真",   # system bypass
    "",
    "x",               # < 2 chars
]


@pytest.fixture()
def actionable_world(monkeypatch):
    """A world whose _build_motor_tools offers >=1 dispatchable tool (a robot/dev world)."""
    monkeypatch.setattr(
        native_loop, "_build_motor_tools",
        lambda agent, engine: {"walk": object(), "detect": object()},
    )


@pytest.fixture()
def empty_world(monkeypatch):
    """A world with NO actionable tools (a sensorless / unconfigured world)."""
    monkeypatch.setattr(native_loop, "_build_motor_tools", lambda agent, engine: {})


# --- the SUPERSET correctness property (the S8-enabling guarantee) ---------------

@pytest.mark.parametrize("cmd", _ACTIONABLE)
def test_never_misses_an_actionable_command(cmd, actionable_world):
    """For every input the keyword router routes to VGG, the registry hint also attempts."""
    assert IntentRouter().should_use_vgg(cmd) is True, "corpus precondition"
    assert native_loop.should_attempt_native(cmd, agent=object(), engine=object()) is True


# --- the registry-driven semantics (pure, no keyword table) ----------------------

@pytest.mark.parametrize("cmd", _ACTIONABLE + _NON_ACTIONABLE[:4])
def test_attempts_iff_world_actionable_and_input_nontrivial(cmd, actionable_world):
    """An actionable world + non-trivial input -> attempt native (model decides routing)."""
    assert native_loop.should_attempt_native(cmd, agent=object(), engine=object()) is True


@pytest.mark.parametrize("cmd", ["", "x", " "])
def test_trivial_input_never_attempts(cmd, actionable_world):
    assert native_loop.should_attempt_native(cmd, agent=object(), engine=object()) is False


@pytest.mark.parametrize("cmd", _ACTIONABLE[:3])
def test_empty_world_never_attempts(cmd, empty_world):
    """No actionable tool in the world -> never attempt native (nothing to route to)."""
    assert native_loop.should_attempt_native(cmd, agent=None, engine=object()) is False


def test_fail_open_when_toolset_build_raises(monkeypatch):
    """If _build_motor_tools raises, fail OPEN to native (never silently skip the redesign)."""
    def _boom(agent, engine):
        raise RuntimeError("registry exploded")
    monkeypatch.setattr(native_loop, "_build_motor_tools", _boom)
    assert native_loop.should_attempt_native("走到厨房", agent=object(), engine=object()) is True


# --- the documented (safe) divergence: fail-open SUPERSET, never under-attempts ---

def test_real_derivation_against_build_motor_tools():
    """Real-derivation (NO mock): should_attempt_native reflects the ACTUAL _build_motor_tools.

    A real Agent with the default skills exposes a real actionable toolset -> attempt
    native for a command, never for trivial input. A bare-registry engine with no agent
    (empty toolset) -> never attempt (nothing to route to). Proves the registry derivation
    works against the live toolset, not just a monkeypatched one.
    """
    from zeno.core.agent import Agent
    from zeno.skills import get_default_skills
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.permissions import PermissionContext
    from zeno.vcli.tools.base import CategorizedToolRegistry

    from tests.harness.fake_backend import FakeToolScriptBackend

    eng = VectorEngine(
        backend=FakeToolScriptBackend.from_tool_script([]),
        registry=CategorizedToolRegistry(),
        permissions=PermissionContext(),
    )
    agent = Agent(config={})
    for s in get_default_skills():
        agent._skill_registry.register(s)

    assert native_loop.should_attempt_native("抓红色的罐子", agent=agent, engine=eng) is True
    assert native_loop.should_attempt_native("", agent=agent, engine=eng) is False
    # No agent + a bare registry => empty toolset => never attempt (nothing dispatchable).
    assert native_loop.should_attempt_native("抓红色的罐子", agent=None, engine=eng) is False


def test_strip_asymmetry_former_miss_now_attempts(actionable_world):
    """D79 fix — a 1-char-after-strip command that should_use_vgg accepts is no longer dropped.

    `should_use_vgg` checks `len(raw) < 2`; should_attempt_native used to check
    `len(strip()) < 2`, so "去 " (raw len 2, stripped len 1) was a MISS (should_use_vgg=True
    but should_attempt_native=False). The threshold now matches (raw len), restoring the
    superset within an actionable world.
    """
    assert IntentRouter().should_use_vgg("去 ") is True            # keyword router accepts it
    assert native_loop.should_attempt_native(                      # superset: native also attempts
        "去 ", agent=object(), engine=object()
    ) is True


def test_divergence_on_chat_is_fail_open_superset(actionable_world):
    """On chat/questions the keyword router says skip, but the registry hint attempts.

    This is the SAFE divergence: native takes no action on a non-command and FALLS BACK
    to legacy (a wasted LLM call, never a missed command). Asserting it documents that
    the registry-driven hint is a fail-open SUPERSET — the property that makes it a
    drop-in replacement for should_use_vgg at the gate sites (S8) with no missed routing.
    """
    chat = "你好"
    assert IntentRouter().should_use_vgg(chat) is False           # keyword router: skip
    assert native_loop.should_attempt_native(                     # registry hint: attempt (fail-open)
        chat, agent=object(), engine=object()
    ) is True
