# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Ground go2 base verify in RobotWorld (generalize the arm grounding).

RobotWorld.build_verify_namespace must contribute grounded base predicates
(at_position/facing) when a sim go2 base is connected — replacing the engine
stubs — exactly as it does the arm predicates, and COMPOSE both for a go2+arm
agent. Pure stubs (no MuJoCo) so the moat primitive is pinned deterministically.
"""
import math

from zeno.vcli.worlds.go2_sim_oracle import (
    make_at_position,
    make_facing,
    make_visited,
)
from zeno.vcli.worlds.robot import RobotWorld


class _FakeBase:
    def __init__(self, pos, heading):
        self._pos = pos
        self._heading = heading
        self._connected = True

    def get_position(self):
        return self._pos

    def get_heading(self):
        return self._heading


class _FakeArm:
    _connected = True

    def get_object_positions(self):
        return {"banana": [0.0, 0.0, 0.26]}


class _Agent:
    def __init__(self, base=None, arm=None):
        self._base = base
        self._arm = arm


# --- predicate primitives (fake base) -------------------------------------

def test_at_position_grounded():
    at_position = make_at_position(_Agent(base=_FakeBase([1.0, 2.0, 0.3], 0.0)))
    assert at_position(1.0, 2.0) is True
    assert at_position(1.2, 2.1) is True  # within 0.5 m tol
    assert at_position(5.0, 5.0) is False


def test_facing_grounded():
    facing = make_facing(_Agent(base=_FakeBase([0.0, 0.0, 0.3], 0.0)))
    assert facing(0.0) is True
    assert facing(math.radians(10)) is True  # within 20 deg tol
    assert facing(math.radians(90)) is False


def test_predicates_fail_safe_without_base():
    agent = _Agent(base=None)
    assert make_at_position(agent)(0.0, 0.0) is False
    assert make_facing(agent)(0.0) is False
    assert make_visited(agent, {"hall": (0, 0, 1, 1)})("hall") is False


# --- RobotWorld composition ------------------------------------------------

def test_robot_world_grounds_base_predicates():
    agent = _Agent(base=_FakeBase([1.0, 2.0, 0.3], 0.0))
    ns = RobotWorld().build_verify_namespace(agent)
    assert "at_position" in ns and "facing" in ns
    # Grounded against the live base — NOT a stub.
    assert ns["at_position"](1.0, 2.0) is True
    assert ns["facing"](0.0) is True
    # Arm-only predicates absent when there is no arm.
    assert "holding_object" not in ns


def test_robot_world_composes_base_and_arm():
    agent = _Agent(base=_FakeBase([0.0, 0.0, 0.3], 0.0), arm=_FakeArm())
    ns = RobotWorld().build_verify_namespace(agent)
    assert {"at_position", "facing", "holding_object", "detect_objects"} <= set(ns)


def test_robot_world_no_embodiment_is_empty():
    assert RobotWorld().build_verify_namespace(_Agent()) == {}
