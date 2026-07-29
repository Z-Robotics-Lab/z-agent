# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Zeno — Python SDK for robot arm and mobile base control.

Quick start:

    from zeno import Agent, SO101, Skill, SkillResult

    arm = SO101(port="/dev/ttyACM0")
    agent = Agent(arm=arm)
    agent.execute_skill("pick", {"object_label": "red cup"})

The Agent, SO101, Skill, and SkillResult names are the four public entry
points. Everything else is importable from sub-packages but not part of
the stable public API in v0.1.
"""
from __future__ import annotations

from typing import Any

from zeno.version import __version__
from zeno.core.agent import Agent
from zeno.core.skill import Skill
from zeno.core.types import ExecutionResult, SkillResult

# Optional hardware/sim entry points are loaded lazily (PEP 562). Importing them
# eagerly dragged the whole MuJoCo → numpy stack (~57ms measured) into EVERY
# `import zeno` — including the go2w_real CLI startup path, which never touches the
# sim arm. Deferring keeps `from zeno import MuJoCoArm` working (and still resolving
# to None when the optional deps are absent) without paying the cost at package load.
_LAZY_OPTIONAL = {
    "SO101": ("zeno.hardware.so101.arm", "SO101Arm"),
    "MuJoCoArm": ("zeno.hardware.sim.mujoco_arm", "MuJoCoArm"),
    "MuJoCoGripper": ("zeno.hardware.sim.mujoco_gripper", "MuJoCoGripper"),
}


def __getattr__(name: str) -> Any:
    """Resolve optional hardware symbols on first access (None if deps missing)."""
    target = _LAZY_OPTIONAL.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    try:
        import importlib

        value = getattr(importlib.import_module(module_name), attr)
    except ImportError:
        value = None  # optional sim/hardware deps absent — preserve legacy contract
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


__all__ = [
    "__version__",
    "Agent",
    "ExecutionResult",
    "MuJoCoArm",
    "MuJoCoGripper",
    "SO101",
    "Skill",
    "SkillResult",
]
