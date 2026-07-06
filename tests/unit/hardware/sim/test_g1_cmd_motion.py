# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MuJoCoG1 commanded-motion counter — the actor-causation seam for g1 navigation.

Why this exists (frontier: g1 NAVIGATION honest-verified on the bare face):
``actor_causation._capture_base`` snapshots ``base.cmd_motion()`` (a cumulative
commanded-velocity magnitude). A base predicate step (``at_position`` / ``facing``)
grades CAUSED only when that counter ADVANCED by >= MOTION_EPS *and* the base pose
displaced. MuJoCoGo2 already exposes ``cmd_motion()``; MuJoCoG1 did NOT, so
``_capture_base(g1)`` read ``base_cmd_motion=None`` -> the grader fail-closed to
UNCAUSED and a genuinely skill-caused g1 walk could only reach RAN, never GROUNDED.

This test pins the SAME honest contract go2 meets (mujoco_go2.cmd_motion): the counter
accumulates ``|vx|+|vy|+|vyaw|`` over every ``set_velocity`` command, a terminal stop
adds zero magnitude, and it is monotonically non-decreasing. It is a DRIVER enrichment
(the actor_causation.grade() logic is byte-unchanged) — it lets g1 participate in the
UNCHANGED spine, it does not loosen it: a no-op / teleport still grades UNCAUSED.

Constructs MuJoCoG1() WITHOUT connect() — set_velocity/stop only touch ``self._cmd``
and the counter, so the counter accounting is exercised with no MuJoCo model load.
"""
from __future__ import annotations

import pytest

from zeno.hardware.sim.mujoco_g1 import MuJoCoG1


def _fresh() -> MuJoCoG1:
    # No connect(): the counter must be live from construction (baseline capture may
    # run before the first sim step). set_velocity/stop do not require a connection.
    return MuJoCoG1(gui=False, room=True)


def test_cmd_motion_starts_at_zero() -> None:
    g1 = _fresh()
    assert hasattr(g1, "cmd_motion"), "MuJoCoG1 must expose cmd_motion() (actor-causation seam)"
    assert g1.cmd_motion() == 0.0


def test_cmd_motion_accumulates_command_magnitude() -> None:
    g1 = _fresh()
    g1.set_velocity(0.5, 0.0, 0.0)
    assert g1.cmd_motion() == pytest.approx(0.5)
    # A second command adds |vx|+|vy|+|vyaw| = 0.3 + 0.0 + 0.2 = 0.5.
    g1.set_velocity(0.3, 0.0, 0.2)
    assert g1.cmd_motion() == pytest.approx(1.0)


def test_cmd_motion_uses_absolute_magnitude() -> None:
    # A backward / negative-yaw command is still commanded MOTION (magnitude), so a
    # reversing walk cannot read as "no command" and duck the actor grade.
    g1 = _fresh()
    g1.set_velocity(-0.4, 0.0, -0.1)
    assert g1.cmd_motion() == pytest.approx(0.5)


def test_stop_adds_zero_magnitude() -> None:
    # stop() == set_velocity(0,0,0): a real motor write but zero magnitude, so a step
    # that only stopped never satisfies the grader's MOTION_EPS (mirrors go2 R2b).
    g1 = _fresh()
    g1.set_velocity(0.5, 0.0, 0.0)
    before = g1.cmd_motion()
    g1.stop()
    assert g1.cmd_motion() == pytest.approx(before)


def test_cmd_motion_monotonic_non_decreasing() -> None:
    g1 = _fresh()
    seq = [(0.5, 0.0, 0.0), (0.0, 0.0, 0.3), (0.0, 0.0, 0.0), (0.2, 0.1, 0.0)]
    prev = g1.cmd_motion()
    for vx, vy, vyaw in seq:
        g1.set_velocity(vx, vy, vyaw)
        now = g1.cmd_motion()
        assert now >= prev
        prev = now
