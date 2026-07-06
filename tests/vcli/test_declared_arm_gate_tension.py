# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Latent capability-gate tension: a manifest that DECLARES ``has_arm:true`` but has NO
runtime arm bound is offered the FULL manipulation surface it cannot execute.

WHY THIS EXISTS (a real Inv-3/plug-and-play coverage hole found R383, latent — no shipped
manifest triggers it because go2 AND g1 both declare ``has_arm:false``):

Two accepted rulings collide.
  - **D72** (S5a, 2026-06-24) built ``resolve_capability_profile`` and ruled the ENRICHMENT
    flags ``has_arm/has_gripper/lidar`` reconcile **runtime-OR-declared**, justified as
    "behavior-inert today — **no current gate reads the enrichment flags**" (the go2+Piper
    runtime-attach motivation is served by the RUNTIME member; declared is false there).
  - **D175** (g1 2nd embodiment, 2026-07-01) then made ``has_arm`` a **live manipulation
    gate** (``native_loop._build_motor_tools`` withholds pick/place/... when ``not has_arm``),
    whose stated purpose is to NOT offer skills a body cannot execute (else a frontier model
    over-reaches into a ``pick`` and the honest compound verdict false-FAILS).

D175 invalidates D72's "no gate reads it" premise. The GATED flags ``has_base``/``camera``
are runtime-authoritative for exactly this reason; ``has_arm`` became a gate WITHOUT being
reclassified, so its declared-OR authority now lets a body advertise a manifest arm it has
not bound -> manipulation offered -> executes "No arm connected" -> the false-reach the gate
was built to prevent.

This test PINS the current (latent-buggy) behavior so it cannot change silently, and
documents the tension. Changing the resolver's ``has_arm`` authority touches accepted ruling
D72's semantics -> a **CEO gate (G-383-1)**, NOT crossed here. When that gate is approved the
fix flips ``test_declared_arm_without_runtime_LATENT_offers_manipulation`` to assert the
manipulation surface is WITHHELD.
"""
from __future__ import annotations

import dataclasses as dc
from typing import Any

import numpy as np

from zeno.core.skill import SkillRegistry
from zeno.embodiments.capability_profile import resolve_capability_profile
from zeno.embodiments.config import load_embodiment_config
from zeno.skills import get_default_skills
from zeno.vcli.native_loop import _build_motor_tools

# The manipulation skills the D175 gate withholds from an armless body.
_MANIP = {"pick", "place", "home", "wave", "scan", "handover",
          "gripper_open", "gripper_close", "describe"}


def _config_declaring_arm() -> Any:
    """A REAL EmbodimentConfig (go2's) whose manifest capability is flipped to has_arm:true.

    Uses ``dataclasses.replace`` so it is a bona-fide ``EmbodimentConfig`` instance
    (``_declared_profile`` isinstance-checks it), matching a plug-and-play robot.yaml that
    declares a manipulator body.
    """
    cfg = load_embodiment_config("go2")
    assert cfg.capabilities.has_arm is False  # the shipped manifest declares NO arm
    return dc.replace(cfg, capabilities=dc.replace(cfg.capabilities, has_arm=True))


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
    def __init__(self, *, base: Any, arm: Any) -> None:
        self._base = base
        self._arm = arm
        self._gripper = arm
        self._perception = None
        self._skill_registry = SkillRegistry()
        for skill in get_default_skills():
            self._skill_registry.register(skill)


class _Engine:
    _goal_executor = None
    _registry = None


def test_declared_arm_without_runtime_resolves_has_arm_true():
    """The declared-OR authority (D72) yields has_arm True even with NO runtime arm bound."""
    agent = _Agent(base=_Base(_config_declaring_arm()), arm=None)
    assert resolve_capability_profile(agent).has_arm is True


def test_declared_arm_without_runtime_LATENT_offers_manipulation():
    """LATENT MISGATE (D72xD175, pending gate G-383-1): a body declaring an arm it has not
    runtime-bound is offered the full manipulation surface it cannot execute.

    Pins current behavior so it cannot change silently. When G-383-1 lands (has_arm gate
    made runtime-authoritative like has_base/camera), this assertion FLIPS to
    ``assert not (_MANIP & set(tools))``.
    """
    agent = _Agent(base=_Base(_config_declaring_arm()), arm=None)
    tools = _build_motor_tools(agent, _Engine())
    offered = _MANIP & set(tools)
    assert offered == _MANIP, (
        "documented latent misgate: declared-arm-without-runtime is offered manipulation"
    )


def test_runtime_arm_present_offers_manipulation_no_regression():
    """The accepted go2+Piper path: a RUNTIME arm -> manipulation offered (unchanged by any
    future authority fix, since the fix keeps runtime-authoritative behavior)."""
    agent = _Agent(base=_Base(_config_declaring_arm()), arm=object())
    tools = _build_motor_tools(agent, _Engine())
    assert _MANIP <= set(tools)


def test_no_arm_no_declaration_drops_manipulation_no_regression():
    """The g1 path: no runtime arm AND manifest declares has_arm:false -> withheld (D175)."""
    cfg_false = load_embodiment_config("go2")  # declares has_arm:false
    agent = _Agent(base=_Base(cfg_false), arm=None)
    assert resolve_capability_profile(agent).has_arm is False
    tools = _build_motor_tools(agent, _Engine())
    assert not (_MANIP & set(tools))
