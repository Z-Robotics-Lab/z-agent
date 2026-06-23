# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R39 — the terminal dock (unit, fully mocked, no sim).

FAR un-parks the dog and brings it to within ~0.8 m of a goal at an ARBITRARY,
oblique heading (probe: ~169 deg off → the d435 frames the floor/wall → perception
mislocalizes the can). The terminal dock dead-reckons the dog to a FIXED proven
table-approach pose BEFORE perceiving, so the proven colour grasp runs from the
head-on pose it expects. The dock target is FIXED (NOT can-relative) — there is no
chicken-and-egg, the dog need not perceive the can to dock to it.

These tests pin the dock's contract WITHOUT a sim:
  1. from an arbitrary oblique FAR arrival the dock REACHES the fixed dock pose
     (the simulated base converges to (dock_x, dock_y, dock_heading)).
  2. the dock is a BENIGN near no-op when the dog is ALREADY at the dock pose
     (the scripted-from-spawn path — no material motion, so D34-D51 is preserved).
  3. a base lacking get_heading/walk is skipped gracefully (returns False, no crash).
  4. the grasp wires the dock BEFORE the perceive (and resolves dock_pose params).
"""
from __future__ import annotations

import math

import pytest

from vector_os_nano.skills.utils.terminal_dock import (
    _DOCK_POS_DEADBAND_M,
    _DOCK_YAW_DEADBAND_RAD,
    terminal_dock,
)


# ---------------------------------------------------------------------------
# A kinematic base double: walk() integrates the commanded velocity over the
# duration, so a sequence of turn/walk commands moves a simulated (x, y, yaw).
# ---------------------------------------------------------------------------

class _KinematicBase:
    """Integrates walk(vx, vy, vyaw, duration) into a world (x, y, yaw) pose.

    Models the gait under a COMBINED ``walk(vx, vyaw)`` (the steered-step the dock
    uses): the heading and the position both advance over the step, integrated in a
    few substeps so a curved step is followed. A small optional per-step drift can
    be injected to prove the dock's closed loop still converges (it re-reads the live
    pose each step). High enough fidelity to verify CONVERGENCE, not gait realism.
    """

    def __init__(self, *, pose=(10.0, 3.0), heading=0.0, drift=0.0):
        self._x, self._y = float(pose[0]), float(pose[1])
        self._yaw = float(heading)
        self._drift = float(drift)
        self.walks: list[tuple[float, float, float, float]] = []

    def get_position(self):
        return (self._x, self._y, 0.35)

    def get_heading(self):
        return self._yaw

    def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=1.0):
        self.walks.append((float(vx), float(vy), float(vyaw), float(duration)))
        # Integrate a curved step (vx + vyaw applied together) in substeps.
        n = 8
        dt = duration / n
        for _ in range(n):
            self._yaw = math.atan2(
                math.sin(self._yaw + vyaw * dt), math.cos(self._yaw + vyaw * dt))
            self._x += vx * dt * math.cos(self._yaw) - vy * dt * math.sin(self._yaw)
            self._y += vx * dt * math.sin(self._yaw) + vy * dt * math.cos(self._yaw)
        self._x += self._drift
        return True


# ---------------------------------------------------------------------------
# 1. dock REACHES the fixed pose from an arbitrary oblique FAR arrival
# ---------------------------------------------------------------------------

def test_dock_reaches_fixed_pose_from_oblique_far_arrival():
    """From FAR's oblique overshot arrival, the dock converges onto the FIXED
    proven dock pose (within the position + heading deadbands)."""
    # FAR arrival: overshot in +y, ~169 deg off (the probe-observed bad pose).
    base = _KinematicBase(pose=(10.75, 3.67), heading=-2.95)
    dock_x, dock_y, dock_hd = 10.0, 3.0, 0.0  # the proven spawn standoff, facing +X

    ran = terminal_dock(base, (dock_x, dock_y), dock_hd)
    assert ran is True

    px, py, _ = base.get_position()
    assert math.hypot(px - dock_x, py - dock_y) <= _DOCK_POS_DEADBAND_M + 0.05, (
        f"dock did not reach ({dock_x},{dock_y}); ended ({px:.2f},{py:.2f})")
    face_err = math.atan2(
        math.sin(dock_hd - base.get_heading()),
        math.cos(dock_hd - base.get_heading()),
    )
    assert abs(face_err) <= _DOCK_YAW_DEADBAND_RAD + 1e-6, (
        f"dock did not face +X; heading {base.get_heading():.2f}")


def test_dock_reaches_fixed_pose_with_open_loop_drift():
    """With per-step dead-reckoning drift injected, the dock's iteration still
    closes onto the fixed pose (proves the convergence loop, not a single shot)."""
    base = _KinematicBase(pose=(10.9, 2.6), heading=2.0, drift=-0.03)
    dock_x, dock_y, dock_hd = 10.0, 3.0, 0.0

    terminal_dock(base, (dock_x, dock_y), dock_hd)
    px, py, _ = base.get_position()
    assert math.hypot(px - dock_x, py - dock_y) <= _DOCK_POS_DEADBAND_M + 0.10


# ---------------------------------------------------------------------------
# 2. benign near no-op when already at the dock pose (scripted-from-spawn)
# ---------------------------------------------------------------------------

def test_dock_is_benign_when_already_at_pose():
    """When the dog is already at the dock pose (the scripted-from-spawn path),
    the dock issues NO walk at all — so the proven grasp does not regress (the
    drive loop breaks at step 0 with gap<=deadband, and the facing turn is within
    the yaw deadband)."""
    base = _KinematicBase(pose=(10.0, 3.0), heading=0.0)
    terminal_dock(base, (10.0, 3.0), 0.0)

    assert base.walks == [], (
        f"dock issued motion from the already-docked pose: {base.walks}")
    px, py, _ = base.get_position()
    assert math.hypot(px - 10.0, py - 3.0) < 1e-9


def test_dock_benign_within_deadband():
    """A dog just inside both deadbands of the dock pose triggers no walk."""
    base = _KinematicBase(pose=(10.05, 3.03), heading=0.05)
    terminal_dock(base, (10.0, 3.0), 0.0)
    assert base.walks == [], f"dock moved a within-deadband dog: {base.walks}"


# ---------------------------------------------------------------------------
# 3. graceful skip when the base lacks the surface
# ---------------------------------------------------------------------------

def test_dock_skips_base_without_heading():
    """A base lacking get_heading must not crash the dock — it returns False so the
    caller proceeds unchanged (no +X assumption, no regression)."""
    class _NoHeading:
        def __init__(self):
            self.walks = []

        def get_position(self):
            return (10.0, 3.0, 0.35)

        def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=1.0):
            self.walks.append((vx, vy, vyaw, duration))
            return True

    base = _NoHeading()
    assert terminal_dock(base, (10.0, 3.0), 0.0) is False
    assert base.walks == [], "dock issued walks on a base it should have skipped"


def test_dock_skips_none_base():
    """A None base is skipped gracefully (returns False)."""
    assert terminal_dock(None, (10.0, 3.0), 0.0) is False


# ---------------------------------------------------------------------------
# 4. the grasp resolves dock_pose params and wires the dock BEFORE the perceive
# ---------------------------------------------------------------------------

def test_grasp_resolves_dock_pose_param():
    from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill

    # [x, y, heading]
    assert PerceptionGraspSkill._resolve_dock_pose(
        {"dock_pose": [10.0, 3.0, 0.0]}) == (10.0, 3.0, 0.0)
    # [x, y] → heading defaults to 0.0
    assert PerceptionGraspSkill._resolve_dock_pose(
        {"dock_pose": [10.0, 3.0]}) == (10.0, 3.0, 0.0)
    # absent → default (None — no-op, scripted-from-spawn preserved)
    assert PerceptionGraspSkill._resolve_dock_pose({}) is None
    # malformed → default
    assert PerceptionGraspSkill._resolve_dock_pose({"dock_pose": "bad"}) is None


def test_grasp_execute_docks_before_perceiving():
    """The dock must be wired into execute() BEFORE the perceive (R38 perceived from
    the bad pose first; R39 docks to the FIXED pose THEN perceives)."""
    import inspect

    from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill

    src = inspect.getsource(PerceptionGraspSkill.execute)
    assert "terminal_dock(" in src, "the dock is not called from execute()"
    dock_at = src.index("terminal_dock(")
    perceive_at = src.index("_perceive_with_scan")
    assert dock_at < perceive_at, (
        "the terminal dock must run BEFORE _perceive_with_scan (dock first, then perceive)")
