# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""HandoverSkill DoF-awareness regression (the Piper 6-vs-5 fix).

The default handover/home pose is the 5-DoF SO-101 pose; sending it to a 6-DoF
arm (Piper) must NOT crash ('expected 6 positions, got 5') — handover adapts to
the arm's DoF by falling back to the URDF-zero neutral pose (`[0.0]*dof`).
SO-101 (5-DoF) behavior is byte-identical to the original.

Ported from the same D96 fix already applied to skills/home.py.
"""
from __future__ import annotations

from vector_os_nano.core.skill import SkillContext
from vector_os_nano.skills.handover import HandoverSkill, _DEFAULT_HOME_JOINTS


class _Arm6Dof:
    """Piper-like: 6-DoF, exposes .dof, rejects a wrong-length move_joints call."""

    dof = 6

    def __init__(self) -> None:
        self.calls: list[list[float]] = []

    def get_joint_positions(self) -> list[float]:
        return [0.0] * 6

    def move_joints(self, positions: list[float], duration: float = 3.0) -> bool:
        if len(positions) != self.dof:
            raise ValueError(f"expected {self.dof} positions, got {len(positions)}")
        self.calls.append(list(positions))
        return True


class _Arm5Dof:
    """SO-101-like: 5-DoF, no .dof attr (DoF inferred from joint count)."""

    def __init__(self) -> None:
        self.calls: list[list[float]] = []

    def get_joint_positions(self) -> list[float]:
        return [0.0] * 5

    def move_joints(self, positions: list[float], duration: float = 3.0) -> bool:
        if len(positions) != 5:
            raise ValueError(f"expected 5 positions, got {len(positions)}")
        self.calls.append(list(positions))
        return True


class _Gripper:
    def __init__(self) -> None:
        self.open_count = 0
        self.close_count = 0

    def open(self) -> None:
        self.open_count += 1

    def close(self) -> None:
        self.close_count += 1


# ---------------------------------------------------------------------------
# RED → GREEN tests
# ---------------------------------------------------------------------------


def test_handover_does_not_crash_on_6dof_arm():
    """Core regression: handover with a 6-DoF arm must not raise ValueError."""
    arm = _Arm6Dof()
    gripper = _Gripper()
    result = HandoverSkill().execute(
        {"direction": "right"},
        SkillContext(arm=arm, gripper=gripper, config={}),
    )
    assert result.success, f"unexpected failure: {result.error_message}"
    # Two move_joints calls: rotate-to-handover + return-home
    assert len(arm.calls) == 2, f"expected 2 move calls, got {len(arm.calls)}"
    for call in arm.calls:
        assert len(call) == 6, f"wrong DoF sent to arm: {call}"


def test_handover_6dof_left_direction():
    """Left-hand rotation also adapts correctly on a 6-DoF arm."""
    arm = _Arm6Dof()
    gripper = _Gripper()
    result = HandoverSkill().execute(
        {"direction": "left"},
        SkillContext(arm=arm, gripper=gripper, config={}),
    )
    assert result.success, result.error_message
    # first call = handover position (negative rotation on joint[0])
    first_call = arm.calls[0]
    assert len(first_call) == 6
    assert first_call[0] < 0.0, "left rotation should be negative on joint[0]"


def test_handover_5dof_so101_behavior_unchanged():
    """5-DoF SO-101 path is byte-identical to the original."""
    arm = _Arm5Dof()
    gripper = _Gripper()
    result = HandoverSkill().execute(
        {"direction": "right"},
        SkillContext(arm=arm, gripper=gripper, config={}),
    )
    assert result.success, result.error_message
    assert len(arm.calls) == 2
    # home call (second call) should match the 5-DoF default home
    home_call = arm.calls[1]
    assert home_call == _DEFAULT_HOME_JOINTS, (
        f"SO-101 home joints changed: expected {_DEFAULT_HOME_JOINTS}, got {home_call}"
    )


def test_handover_gripper_open_then_close():
    """Gripper is opened and then closed during handover."""
    arm = _Arm6Dof()
    gripper = _Gripper()
    HandoverSkill().execute(
        {"direction": "right"},
        SkillContext(arm=arm, gripper=gripper, config={}),
    )
    assert gripper.open_count == 1
    assert gripper.close_count == 1


def test_handover_no_arm_fails_cleanly():
    """Missing arm returns a clean failure, not an exception."""
    result = HandoverSkill().execute(
        {},
        SkillContext(arm=None, config={}),
    )
    assert not result.success
    assert result.result_data.get("diagnosis") == "no_arm"


def test_handover_config_override_6dof():
    """A 6-element config override is used verbatim on a 6-DoF arm."""
    arm = _Arm6Dof()
    gripper = _Gripper()
    custom = [0.1, -0.5, 0.2, 0.3, -0.1, 0.4]
    cfg = {"skills": {"home": {"joint_values": custom}}}
    result = HandoverSkill().execute(
        {"direction": "right"},
        SkillContext(arm=arm, gripper=gripper, config=cfg),
    )
    assert result.success, result.error_message
    # The home-return call (second) should be the custom joints
    home_call = arm.calls[1]
    assert home_call == custom, f"config override not respected: {home_call}"
