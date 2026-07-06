# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R38 — the FAR-arrival -> grasp re-pose seam (unit, fully mocked, no sim).

FAR's nav primitive leaves the dog "roughly near the table at any heading"
(probe: (10.75, 3.67), heading -2.95 rad ~169 deg off, overshot in y, past the
jam in x). The scripted ``_approach_object`` assumes a +X head-on spawn pose and
creeps the WRONG way from there. The fix inserts a deterministic
``perceive -> compute_approach_pose(clearance) -> turn-in-place to the facing yaw
-> short move -> existing jam/seat/nudge`` sandwich, and replaces the
``except: th = 0.0  # assume +x`` heading fallback with the LIVE ``base.get_heading()``.

These tests pin the seam's contract WITHOUT a sim:
  1. ``compute_approach_pose`` faces the can from FAR's arbitrary arrival pose.
  2. the re-pose turns the base toward the facing yaw (a yaw command is issued)
     when the dog arrives mis-headed, and is a NO-OP/benign when already head-on
     (so the scripted-from-spawn grasp D34-D51 does not regress).
  3. the post-approach nudge reads the LIVE heading (the th=0.0 fallback is gone).
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from zeno.skills.perception_grasp import (
    PerceptionGraspSkill,
    _approach_and_seat,
    _grasp_ready_repose,
)
from zeno.skills.utils.approach_pose import compute_approach_pose


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class _RecordingBase:
    """A base double that records walk commands and lets us script its pose.

    ``get_heading`` returns the scripted heading; ``walk`` records (vx, vy, vyaw)
    and (optionally) advances a scripted pose stream so the re-pose loop can
    converge. ``get_position`` returns the current scripted (x, y, z).
    """

    def __init__(self, *, pose=(10.75, 3.67, 0.35), heading=-2.95, poses=None,
                 headings=None):
        self._pose = list(pose)
        self._heading = heading
        self._poses = list(poses or [])
        self._headings = list(headings or [])
        self.walks: list[tuple[float, float, float, float]] = []

    def get_position(self):
        return tuple(self._pose)

    def get_heading(self):
        return self._heading

    def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=1.0):
        self.walks.append((float(vx), float(vy), float(vyaw), float(duration)))
        # Advance scripted streams if provided (so a convergence loop terminates).
        if self._poses:
            self._pose = list(self._poses.pop(0))
        if self._headings:
            self._heading = self._headings.pop(0)
        return True


# ---------------------------------------------------------------------------
# 1. compute_approach_pose faces the can from FAR's arrival pose
# ---------------------------------------------------------------------------

def test_compute_approach_pose_faces_can_from_far_arrival_pose():
    """Given FAR's terminal pose and the red-can GT, the approach pose sits on the
    dog's side at the requested clearance and its yaw points AT the can."""
    can = (10.90, 3.22, 0.32)
    dog = (10.75, 3.67, -2.95)  # FAR arrival: 169 deg off, overshot +y
    ax, ay, ayaw = compute_approach_pose(can, dog, clearance=0.45)

    # Approach point is 0.45 m from the can along the dog-side direction.
    assert math.hypot(ax - can[0], ay - can[1]) == pytest.approx(0.45, abs=1e-6)
    # The approach yaw faces the can.
    bearing = math.atan2(can[1] - ay, can[0] - ax)
    err = math.atan2(math.sin(ayaw - bearing), math.cos(ayaw - bearing))
    assert abs(err) < 1e-6
    # And the facing yaw is materially different from FAR's arrival heading,
    # i.e. a turn-in-place is genuinely required (the bug this seam fixes).
    turn = math.atan2(math.sin(ayaw - dog[2]), math.cos(ayaw - dog[2]))
    assert abs(turn) > math.radians(45)


# ---------------------------------------------------------------------------
# 2. the re-pose turns toward the facing yaw, and is benign head-on
# ---------------------------------------------------------------------------

def test_repose_turns_in_place_when_mis_headed():
    """From FAR's 169-deg-off arrival the re-pose must issue a turn-in-place
    (a walk with |vyaw|>0 and vx==0) toward the can BEFORE any forward creep."""
    can_xy = (10.90, 3.22)
    base = _RecordingBase(pose=(10.75, 3.67, 0.35), heading=-2.95)
    _grasp_ready_repose(base, can_xy, clearance=0.45)

    # At least one pure turn-in-place command (vx==0, vy==0, |vyaw|>0) was issued.
    turns = [w for w in base.walks if w[0] == 0.0 and w[1] == 0.0 and abs(w[2]) > 1e-3]
    assert turns, f"re-pose issued no turn-in-place; walks={base.walks}"


def test_repose_is_benign_when_already_head_on():
    """When the dog is already head-on (+X, facing the can dead ahead) the re-pose
    must NOT command a large turn — the scripted-from-spawn grasp is preserved.

    Spawn-like pose: dog at (10.0, 3.22) heading 0 (facing +X), can dead ahead at
    (10.90, 3.22). The facing yaw equals the current heading, so any turn command
    is below a small deadband (benign)."""
    can_xy = (10.90, 3.22)
    base = _RecordingBase(pose=(10.0, 3.22, 0.35), heading=0.0)
    _grasp_ready_repose(base, can_xy, clearance=0.45)

    big_turns = [w for w in base.walks
                 if w[0] == 0.0 and w[1] == 0.0 and abs(w[2]) > 1e-3
                 and (w[3] * abs(w[2])) > math.radians(20)]
    assert not big_turns, f"re-pose over-turned a head-on dog; walks={base.walks}"


def test_repose_no_op_without_base_heading():
    """A base lacking get_heading must not crash the re-pose (graceful skip)."""
    class _NoHeading:
        def __init__(self):
            self.walks = []

        def get_position(self):
            return (10.0, 3.0, 0.35)

        def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=1.0):
            self.walks.append((vx, vy, vyaw, duration))
            return True

    base = _NoHeading()
    # Must return without raising.
    _grasp_ready_repose(base, (10.9, 3.22), clearance=0.45)


# ---------------------------------------------------------------------------
# 3. the post-approach nudge reads the LIVE heading (th=0.0 fallback is gone)
# ---------------------------------------------------------------------------

def test_perception_grasp_source_has_no_plus_x_heading_fallback():
    """The ``except: th = 0.0  # assume facing +x`` fallback must be DELETED.

    The fallback silently assumes a +X head-on pose, which mis-fires from FAR's
    arrival heading. The seam uses the live ``base.get_heading()`` everywhere; a
    base without heading is handled by skipping the heading-dependent step, not by
    pretending +X."""
    import inspect

    src = inspect.getsource(PerceptionGraspSkill.execute)
    assert "assume facing +x" not in src.lower(), (
        "the +X heading fallback is still present in PerceptionGraspSkill.execute"
    )
    # And the seat-approach (which runs the re-pose seam + stall-seat creep) is
    # wired into execute() as the out-of-reach final hop (D95).
    assert "_approach_and_seat" in src, "seat-approach not called from execute()"
    # The re-pose seam itself lives in the unified seat-approach helper.
    seat_src = inspect.getsource(_approach_and_seat)
    assert "_grasp_ready_repose" in seat_src, "re-pose seam not in the seat-approach"


# ---------------------------------------------------------------------------
# 4. final-hop seat-approach (D95) — the flaky vgraph nav-approach for the last
#    hop is RETIRED. The scripted re-pose + stall-seating creep is now the primary
#    (and only) final-hop mechanism for every base: it must creep forward (vx>0)
#    and must NOT route through the planner (navigate_to), whose intermittent
#    bail-to-far / seat-short was the remaining grasp failure mode.
# ---------------------------------------------------------------------------

class _SeatBase:
    """Base double recording walks; advances forward each vx>0 walk so the creep can
    stall-seat. Exposes ``navigate_to`` (counted) to PROVE the seat-approach no longer
    routes through the planner. ``walk`` integrates vx along the (fixed) +X heading."""

    def __init__(self, *, start_pos=(10.0, 3.0), heading=0.0, table_x=10.46):
        self._pos = list(start_pos)
        self._heading = heading
        self._table_x = table_x  # the dog body jams here (table edge)
        self.walks: list[tuple[float, float, float, float]] = []
        self.nav_calls: list[tuple[float, float, float]] = []

    def get_position(self):
        return tuple(self._pos)

    def get_heading(self):
        return self._heading

    def navigate_to(self, x, y, tol=0.1):
        self.nav_calls.append((x, y, tol))
        return True

    def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=1.0):
        self.walks.append((float(vx), float(vy), float(vyaw), float(duration)))
        # Integrate forward motion along +X, jamming at the table edge (stall).
        if vx > 0.0:
            self._pos[0] = min(self._table_x, self._pos[0] + vx * duration)
        self._pos[1] += vy * duration
        return True


def test_seat_approach_creeps_forward_and_does_not_call_navigate_to():
    """From the head-on perceive standoff the seat-approach must creep forward (a vx>0
    walk) and must NOT hand the final hop to the planner (navigate_to), whose flaky
    bail-to-far was the failure mode D95 retires."""
    from zeno.skills.perception_grasp import _approach_and_seat

    obj = (10.86, 3.00)
    base = _SeatBase(start_pos=(9.90, 3.00), heading=0.0)  # ~0.96 m head-on
    _approach_and_seat(base, obj)

    assert any(vx > 0.0 for (vx, _vy, _vyaw, _d) in base.walks), (
        "the scripted forward seat-creep did not run"
    )
    assert not base.nav_calls, (
        f"the final hop still routed through navigate_to (calls={base.nav_calls})"
    )


def test_seat_approach_seats_against_the_table_edge():
    """The creep must drive the dog forward to the table-edge jam (its repeatable,
    IK-reachable standoff), not stop short at the far perceive pose."""
    from zeno.skills.perception_grasp import _approach_and_seat

    obj = (10.86, 3.00)
    base = _SeatBase(start_pos=(9.90, 3.00), heading=0.0, table_x=10.46)
    _approach_and_seat(base, obj)

    # The dog advanced from 9.90 toward the table edge (proven standoff ~10.46),
    # closing most of the gap rather than stalling at the far perceive distance.
    assert base.get_position()[0] > 10.30, (
        f"the dog did not seat near the table edge (ended x={base.get_position()[0]:.2f})"
    )
