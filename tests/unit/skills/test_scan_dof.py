# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""ScanSkill DoF-awareness regression (the Piper 6-vs-5 fix).

The default scan pose is the 5-DoF SO-101 pose; sending it to a 6-DoF arm (Piper)
must NOT crash ('expected 6 positions, got 5') — scan adapts to the arm's DoF by
holding the current pose. SO-101 (5-DoF) behavior is byte-identical.
"""
from __future__ import annotations

from vector_os_nano.core.skill import SkillContext
from vector_os_nano.skills.scan import ScanSkill, _DEFAULT_SCAN_JOINTS


class _ArmWithDof:  # Piper-like: 6-DoF, exposes .dof + rejects a wrong-length move
    dof = 6

    def __init__(self) -> None:
        self.moved = None

    def get_joint_positions(self):
        return [0.1] * 6

    def move_joints(self, positions, duration=3.0):
        assert len(positions) == self.dof, f"expected {self.dof}, got {len(positions)}"
        self.moved = list(positions)
        return True


class _ArmNoDof:  # SO-101-like: 5-DoF, no .dof attr (DoF inferred from joint count)
    def __init__(self) -> None:
        self.moved = None

    def get_joint_positions(self):
        return [0.0] * 5

    def move_joints(self, positions, duration=3.0):
        assert len(positions) == 5, f"expected 5, got {len(positions)}"
        self.moved = list(positions)
        return True


def test_scan_adapts_to_6dof_piper():
    arm = _ArmWithDof()
    res = ScanSkill().execute({}, SkillContext(arm=arm, config={}))
    assert res.success, res.error_message
    assert arm.moved is not None and len(arm.moved) == 6  # adapted to 6-DoF, no crash


def test_scan_so101_5dof_unchanged():
    arm = _ArmNoDof()
    res = ScanSkill().execute({}, SkillContext(arm=arm, config={}))
    assert res.success, res.error_message
    assert arm.moved == _DEFAULT_SCAN_JOINTS  # 5==5: byte-identical SO-101 behavior


def test_scan_no_arm_still_fails_cleanly():
    res = ScanSkill().execute({}, SkillContext(arm=None, config={}))
    assert not res.success and res.result_data.get("diagnosis") == "no_arm"
