# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Pick fails FAST when the target is genuinely absent (no wasted retries).

Asking to grab an object that isn't in the scene used to exhaust all pick
retries — re-homing and re-detecting the same miss each time (seconds of motion
for a guaranteed failure). The pick skill now breaks out on a target-not-found
diagnosis (object_not_found / no_detections); transient failures still retry.
"""
from __future__ import annotations

import pytest

mujoco = pytest.importorskip("mujoco")  # headless sim oracle; skip if unavailable


def _agent(max_retries: int):
    from zeno.core.agent import Agent
    from zeno.hardware.sim.mujoco_arm import MuJoCoArm
    from zeno.hardware.sim.mujoco_gripper import MuJoCoGripper
    from zeno.hardware.sim.mujoco_perception import MuJoCoPerception

    arm = MuJoCoArm(gui=False)
    arm.connect()
    agent = Agent(
        arm=arm,
        gripper=MuJoCoGripper(arm),
        perception=MuJoCoPerception(arm),
        config={"skills": {"pick": {"hardware_offsets": False, "z_offset": 0.0, "max_retries": max_retries}}},
    )
    return agent, arm


def test_absent_target_fails_after_one_attempt_not_max_retries():
    """An object not in the scene must fail FAST (1 attempt), not exhaust max_retries=3."""
    from zeno.skills.pick import PickSkill

    agent, arm = _agent(max_retries=3)
    try:
        ctx = agent._build_context()
        result = PickSkill().execute({"object_label": "apple"}, ctx)  # apple absent
        assert result.success is False
        assert result.result_data.get("diagnosis") == "object_not_found"
        # Fail-fast: stopped after the first attempt despite max_retries=3.
        assert result.result_data.get("attempts") == 1, (
            f"absent target should fail fast, not retry: {result.result_data}"
        )
    finally:
        arm.disconnect()


def test_present_target_still_succeeds():
    """Sanity: the fail-fast change does not affect a normal, present target."""
    from zeno.skills.pick import PickSkill

    agent, arm = _agent(max_retries=2)
    try:
        ctx = agent._build_context()
        result = PickSkill().execute({"object_label": "banana", "mode": "hold"}, ctx)
        assert result.success is True
    finally:
        arm.disconnect()
