# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Plug-and-play manipulation-gate completeness (R384/E173, self-fixed strictly-stricter).

The D175 manipulation gate (``native_loop._build_motor_tools`` withholds pick/place/... from
an armless body) classified "is this a manipulation skill?" by a HARDCODED name denylist
(``_ARM_REQUIRING_SKILLS``). That list is complete for the SHIPPED skills, but it fails OPEN
for the North-Star plug-and-play path ("bring a skill — no kernel edit"): a BYO manipulation
skill whose NAME the kernel has never seen is NOT in the list -> offered to an armless body ->
the exact false-reach the gate exists to prevent (the model dispatches it, it executes
"No arm connected", and the honest compound verdict false-FAILS).

This is a SIBLING of E172 via a DIFFERENT mechanism: E172 is a manifest DECLARING has_arm:true
with no runtime arm (a flag-authority bug, gated G-383-1); this is a correctly-armless body
(has_arm:false) offered a novel skill the name-list doesn't cover (a gate-classifier gap).

FIX (R384, strictly stricter, Invariant-1 sanctioned — the sandbox only gets STRICTER): the
gate withholds a skill from an armless body iff its name is curated OR its OWN structured
metadata (preconditions + effects) declares arm/gripper hardware
(``SkillWrapperTool._requires_arm``). Provably behavior-IDENTICAL for every shipped skill on
every shipped body (the only armless-offered shipped skill, ``detect``, is arm-silent;
``scan``/``describe``/``wave`` stay withheld via the retained name-list), and strictly
STRICTER for a novel plug-and-play manipulator. No interface change, no flag-authority change,
non-spine.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from zeno.core.skill import SkillRegistry
from zeno.embodiments.config import load_embodiment_config
from zeno.skills import get_default_skills
from zeno.vcli.native_loop import _build_motor_tools

_SHIPPED_MANIP = {"pick", "place", "home", "wave", "scan", "handover",
                  "gripper_open", "gripper_close", "describe"}


class _TwistSkill:
    """A BYO manipulation skill (no kernel edit). Its STRUCTURED metadata declares arm/gripper
    hardware, exactly as a real manipulator skill would."""
    name = "twist_valve"
    description = "Twist a valve to open it."
    parameters = {"object": {"type": "string"}}
    preconditions = ["gripper_holding_any"]
    postconditions = ["valve rotated"]
    effects = {"arm": "rotated", "gripper_state": "closed"}
    failure_modes = ["no arm connected"]

    def execute(self, params: dict, context: Any) -> Any:  # pragma: no cover - never armless-run
        raise RuntimeError("No arm connected")


class _SingSkill:
    """A BYO NON-manipulation skill: no arm/gripper in its structured metadata and not curated.
    Must stay OFFERED to an armless body — the fix must not over-withhold."""
    name = "sing"
    description = "Emit a tune through the speaker."
    parameters: dict = {}
    preconditions: list = []
    postconditions = ["tune played"]
    effects = {"audio": "played"}
    failure_modes = ["no speaker"]

    def execute(self, params: dict, context: Any) -> Any:  # pragma: no cover
        return None


class _Base:
    def __init__(self, config: Any) -> None:
        self._config = config

    def get_camera_frame(self, width: int = 640, height: int = 480) -> Any:
        return np.zeros((height, width, 3), dtype=np.uint8)

    def get_position(self) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.3)

    def get_heading(self) -> float:
        return 0.0


class _Agent:
    def __init__(self, *, base: Any, arm: Any, extra: list | None = None) -> None:
        self._base = base
        self._arm = arm
        self._gripper = arm
        self._perception = None
        self._skill_registry = SkillRegistry()
        for skill in get_default_skills():
            self._skill_registry.register(skill)
        for skill in extra or []:
            self._skill_registry.register(skill)


class _Engine:
    _goal_executor = None
    _registry = None


def _armless_agent(extra: list | None = None) -> _Agent:
    cfg = load_embodiment_config("go2")  # manifest declares has_arm:false
    return _Agent(base=_Base(cfg), arm=None, extra=extra)


def _armed_agent(extra: list | None = None) -> _Agent:
    cfg = load_embodiment_config("go2")
    return _Agent(base=_Base(cfg), arm=object(), extra=extra)


def test_plugin_manip_skill_withheld_from_armless_body():
    """The FIX: a BYO manipulation skill (arm/gripper in structured metadata) whose NAME the
    kernel has never seen is NOT offered to an armless body."""
    agent = _armless_agent(extra=[_TwistSkill()])
    tools = _build_motor_tools(agent, _Engine())
    assert "twist_valve" not in tools, (
        "plug-and-play manip skill must be withheld from an armless body (D175 false-reach)"
    )


def test_plugin_nonmanip_skill_still_offered_to_armless_body():
    """The guard must not OVER-withhold: a BYO non-arm skill (no arm/gripper metadata, not
    curated) stays offered to an armless body."""
    agent = _armless_agent(extra=[_SingSkill()])
    tools = _build_motor_tools(agent, _Engine())
    assert "sing" in tools, "a non-arm plug-and-play skill must stay offered to an armless body"


def test_plugin_manip_skill_offered_when_arm_present():
    """No regression to armed bodies: the same BYO manip skill IS offered when an arm is bound."""
    agent = _armed_agent(extra=[_TwistSkill()])
    tools = _build_motor_tools(agent, _Engine())
    assert "twist_valve" in tools


def test_shipped_gate_unchanged_on_armless_body():
    """Regression witness that the fix changes ZERO shipped behavior: on an armless body every
    shipped manipulation skill stays withheld and ``detect`` stays offered."""
    agent = _armless_agent()
    tools = _build_motor_tools(agent, _Engine())
    assert not (_SHIPPED_MANIP & set(tools)), "shipped manip must stay withheld from armless"
    assert "detect" in tools, "detect (camera-only, arm-silent) must stay offered to armless"


def test_shipped_gate_unchanged_on_armed_body():
    """On an armed body every shipped manipulation skill stays offered (unchanged)."""
    agent = _armed_agent()
    tools = _build_motor_tools(agent, _Engine())
    assert _SHIPPED_MANIP <= set(tools)
