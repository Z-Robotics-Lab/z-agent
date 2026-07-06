# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2-7 (a): holding_object(target) is target-aware (holds the REQUESTED object).

Pure oracle test with a fake arm/gripper — no MuJoCo — pinning the moat
primitive: a grasp of the wrong (e.g. nearest) object must NOT verify True
against a different named target, while holding_object() (no target) keeps its
"holding anything" meaning so every existing caller is unaffected.
"""
from zeno.vcli.worlds.arm_sim_oracle import make_holding_object


class _FakeArm:
    def __init__(self, objects, ee):
        self._objects = objects
        self._ee = ee
        self._connected = True

    def get_object_positions(self):
        return self._objects

    def get_joint_positions(self):
        return [0.0]

    def fk(self, _joints):
        return (self._ee, None)


class _FakeGripper:
    def __init__(self, holding):
        self._holding = holding

    def is_holding(self):
        return self._holding


class _FakeAgent:
    def __init__(self, arm, gripper):
        self._arm = arm
        self._gripper = gripper


def _agent(holding=True):
    # banana lifted at the EE; mug resting far away on the table.
    arm = _FakeArm(
        objects={"banana": [0.0, 0.0, 0.26], "mug": [0.5, 0.5, 0.0]},
        ee=[0.0, 0.0, 0.26],
    )
    return _FakeAgent(arm, _FakeGripper(holding))


def test_no_target_holds_anything():
    holding_object = make_holding_object(_agent())
    assert holding_object() is True  # backward-compatible "holding something"


def test_target_aware_matches_held_object():
    holding_object = make_holding_object(_agent())
    assert holding_object("banana") is True
    assert holding_object("BANANA") is True  # case-insensitive, structural


def test_target_aware_rejects_a_different_object():
    # The crux: grabbed the banana, but asked to verify holding the apple/mug.
    holding_object = make_holding_object(_agent())
    assert holding_object("apple") is False  # absent target -> not holding it
    assert holding_object("mug") is False  # present but resting, not held


def test_not_holding_is_false_for_any_target():
    holding_object = make_holding_object(_agent(holding=False))
    assert holding_object() is False
    assert holding_object("banana") is False
