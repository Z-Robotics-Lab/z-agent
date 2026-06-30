# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Moat tests for the receptacle-place oracle (D106, CEO-approved). Pure oracle test with a
fake arm/gripper — no MuJoCo. Pins the monotonicity contract: ``make_resting_on_receptacle``
credits ONLY a genuine placement (in-region + at the rest height + at rest + released), and the
floor-only ``make_placed_count`` is BYTE-UNCHANGED (no existing ACCEPT path widened)."""
from vector_os_nano.vcli.worlds.arm_sim_oracle import (
    make_placed_count,
    make_resting_on_receptacle,
)

# A height receptacle: a 0.2 x 0.2 m region with its rest surface at z = 0.30.
_REGION = (0.4, 0.4, 0.6, 0.6)
_REST_Z = 0.30


class _FakeArm:
    def __init__(self, objects, velocities, ee):
        self._objects = objects
        self._velocities = velocities
        self._ee = ee
        self._connected = True

    def get_object_positions(self):
        return self._objects

    def get_object_velocities(self):
        return self._velocities

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


def _agent(objects, *, velocities=None, ee=(0.0, 0.0, 0.26), holding=False):
    vel = velocities or {name: [0.0, 0.0, 0.0] for name in objects}
    return _FakeAgent(_FakeArm(objects, vel, list(ee)), _FakeGripper(holding))


# --------------------------------------------------------------------------- #
# GENUINE placement credits.
# --------------------------------------------------------------------------- #

def test_credits_a_genuine_receptacle_placement():
    """In region + at the rest height + at rest + released -> credited."""
    agent = _agent({"cup": [0.5, 0.5, 0.30]}, holding=False)
    assert make_resting_on_receptacle(agent, _REGION, _REST_Z)() == 1


def test_released_even_when_gripper_holds_a_different_object():
    """A placed cup far from the EE counts even if the gripper still holds something else
    (held-check is per-object via near-EE, not a blanket gripper flag)."""
    agent = _agent({"cup": [0.5, 0.5, 0.30]}, ee=(0.0, 0.0, 0.26), holding=True)
    assert make_resting_on_receptacle(agent, _REGION, _REST_Z)() == 1


# --------------------------------------------------------------------------- #
# The four reject conditions (no false-green slips through).
# --------------------------------------------------------------------------- #

def test_rejects_held_above_the_receptacle():
    """Object at the rest height + in region BUT still in the gripper (near the EE, holding)
    -> NOT placed."""
    agent = _agent({"cup": [0.5, 0.5, 0.30]}, ee=(0.5, 0.5, 0.30), holding=True)
    assert make_resting_on_receptacle(agent, _REGION, _REST_Z)() == 0


def test_rejects_near_but_not_over_the_receptacle():
    """xy outside the receptacle region -> NOT placed (even at the right height)."""
    agent = _agent({"cup": [0.75, 0.75, 0.30]}, holding=False)
    assert make_resting_on_receptacle(agent, _REGION, _REST_Z)() == 0


def test_rejects_floating_above_or_resting_on_the_floor():
    """z off the rest height (floating high, or on the floor below) -> NOT placed."""
    floating = _agent({"cup": [0.5, 0.5, 0.55]}, holding=False)
    on_floor = _agent({"cup": [0.5, 0.5, 0.00]}, holding=False)
    assert make_resting_on_receptacle(floating, _REGION, _REST_Z)() == 0
    assert make_resting_on_receptacle(on_floor, _REGION, _REST_Z)() == 0


def test_rejects_an_in_flight_object_passing_through_the_rest_height():
    """At the rest height + in region but MOVING fast (a throw mid-arc) -> NOT placed."""
    agent = _agent({"cup": [0.5, 0.5, 0.30]}, velocities={"cup": [0.0, 0.0, 2.0]}, holding=False)
    assert make_resting_on_receptacle(agent, _REGION, _REST_Z)() == 0


def test_fails_safe_to_zero_on_malformed_region():
    agent = _agent({"cup": [0.5, 0.5, 0.30]}, holding=False)
    assert make_resting_on_receptacle(agent, "not-a-region", _REST_Z)() == 0


# --------------------------------------------------------------------------- #
# MONOTONICITY: the floor-only placed_count is byte-unchanged — the new oracle
# adds a credit for a NEW task, it does not alter or widen the existing one.
# --------------------------------------------------------------------------- #

def test_placed_count_floor_behaviour_unchanged_by_the_new_oracle():
    """placed_count still credits ONLY floor rests (z < 0.10) and ignores a receptacle-height
    object — proving the new oracle did not touch the existing ACCEPT path."""
    floor_obj = _agent({"cup": [0.5, 0.5, 0.05]}, holding=False)
    recept_obj = _agent({"cup": [0.5, 0.5, 0.30]}, holding=False)
    assert make_placed_count(floor_obj, default_region=_REGION)() == 1
    # a receptacle-height object is NOT a floor placement -> placed_count stays 0 (unchanged)
    assert make_placed_count(recept_obj, default_region=_REGION)() == 0
