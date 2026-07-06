# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Capability gate: an ARMLESS embodiment (g1) must NOT be offered manipulation skills.

Plug-and-play principle (Invariant 3): the toolset a model sees is DERIVED from the
body's capabilities, not hardcoded. ``_build_motor_tools`` already gates ``navigate``
on ``has_base`` and ``detect`` on a registered camera capability. This pins the missing
gate: manipulation skills (pick/place/home/wave/scan/handover/gripper_*) require an ARM,
so a camera-only humanoid (g1: ``_arm is None``) must not see them — otherwise a frontier
model over-reaches into a ``pick`` the body can't do, and the honest verdict false-FAILS
(the g1 acceptance RAN-False bug: ``detect`` GROUNDED but a chained armless ``pick``
dragged the compound verdict to False).

go2+arm (``_arm`` present) keeps the FULL manipulation surface — no behavior change for
the accepted fetch/place path (D172-D174). The gate reads the SAME single-source
``resolve_capability_profile`` as the base gate, so it can't drift.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from zeno.core.skill import SkillRegistry
from zeno.skills import get_default_skills
from zeno.vcli.native_loop import _ARM_REQUIRING_SKILLS, _build_motor_tools


class _Base:
    """A mobile base with a camera (go2/g1 shape) — no ``_config`` -> declared=None."""

    def get_camera_frame(self, width: int = 640, height: int = 480) -> Any:
        return np.zeros((height, width, 3), dtype=np.uint8)

    def get_position(self) -> tuple[float, float, float]:
        return (10.0, 3.0, 0.79)

    def get_heading(self) -> float:
        return 0.0


class _Agent:
    """Minimal agent with a REAL default skill registry (as core.agent.Agent builds)."""

    def __init__(self, *, arm: Any) -> None:
        self._arm = arm
        self._base = _Base()
        self._gripper = arm  # gripper rides with the arm in these fixtures
        self._perception = None
        self._skill_registry = SkillRegistry()
        for skill in get_default_skills():
            self._skill_registry.register(skill)


class _Engine:
    """No code-tool registry, no capability executor (isolates the skill-surfacing gate)."""

    _goal_executor = None
    _registry = None


# The default skills that need an arm (grep-verified) — the gate's target set. ``describe``
# is included because it auto-runs ``scan`` (auto_steps), which needs an arm, so it fails
# "No arm connected" on a camera-only body and false-FAILS the perception turn.
_MANIP = {"pick", "place", "home", "wave", "scan", "handover", "gripper_open",
          "gripper_close", "describe"}


def test_arm_requiring_set_covers_manipulation_defaults():
    """The gate's name-set must include every arm-referencing default skill."""
    assert _MANIP <= _ARM_REQUIRING_SKILLS


def test_armless_g1_drops_arm_requiring_skills():
    tools = _build_motor_tools(_Agent(arm=None), _Engine())
    for name in _MANIP:
        assert name not in tools, f"armless g1 must not be offered arm-requiring skill {name!r}"
    # g1 has a base -> the avoidance navigate route survives (existing has_base gate).
    assert "navigate" in tools


def test_go2_arm_keeps_full_manipulation_surface():
    tools = _build_motor_tools(_Agent(arm=object()), _Engine())
    for name in _MANIP:
        assert name in tools, f"go2+arm must keep arm-requiring skill {name!r} (no regression)"
    assert "navigate" in tools
