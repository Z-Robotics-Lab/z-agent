# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real global-pose awareness hooks (RED first).

CEO directive 2026-07-13 night: the agent must ALWAYS know its live global
coordinates + orientation. This world implements the two OPTIONAL kernel
hooks (plug-and-play, supports_pose_reset pattern):

* ``world_context_ttl() -> 0.0``: the pose the plan-time world context reads
  is a CACHED driver attribute (the /state_estimation subscription already
  paid for it) — zero cost, so the kernel's 5 s expensive-query cache only
  makes it stale (up to 3 m at 0.6 m/s).
* ``live_status_line(agent)``: ONE short line — pose x/y (2 decimals), yaw in
  BOTH deg and rad, course intent + drift when a relative plan is running,
  odometry age — refreshed by the native loop before EVERY model call. When
  ``odom_age_s()`` is None the line is the honest
  '(no odometry — stack down?)' fallback, never a fabricated zero pose.

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


def _world():
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    return Go2WRealWorld()


class _FakeHW:
    """Fake driver: cached pose attributes + the odom-age liveness oracle."""

    def __init__(self, x=0.0, y=0.0, yaw=0.0, age=0.2, course=None):
        self._pos = [x, y, 0.0]
        self._yaw = yaw
        self._age = age
        if course is not None:
            from zeno.vcli.worlds.go2w_real_course import CourseTracker

            tracker = CourseTracker()
            tracker.set_course(course)
            self.course_tracker = tracker

    def get_position(self):
        return list(self._pos)

    def get_heading(self):
        return self._yaw

    def odom_age_s(self):
        return self._age


def _agent(base) -> SimpleNamespace:
    return SimpleNamespace(_base=base)


# ---------------------------------------------------------------------------
# Hook A — world_context_ttl
# ---------------------------------------------------------------------------


def test_world_context_ttl_is_zero() -> None:
    """Pose read is a cached driver attribute — plan-time context must be fresh."""
    assert _world().world_context_ttl() == 0.0


# ---------------------------------------------------------------------------
# Hook B — live_status_line
# ---------------------------------------------------------------------------


def test_live_status_line_pose_deg_rad_and_age() -> None:
    base = _FakeHW(x=1.234, y=-2.567, yaw=0.5, age=0.31)
    line = _world().live_status_line(_agent(base))

    assert "\n" not in line, "must be ONE short line"
    assert "x=1.23" in line and "y=-2.57" in line, "pose to 2 decimals"
    # Yaw in BOTH units: degrees AND radians.
    assert f"{math.degrees(0.5):.1f}deg" in line.replace("+", "")
    assert "0.500rad" in line.replace("+", "")
    assert "0.3s" in line, "odometry age is part of the honest state"
    assert "course" not in line, "no course intent set -> no course segment"


def test_live_status_line_course_intent_and_drift() -> None:
    """When a relative plan anchored a course, report it + the live drift."""
    base = _FakeHW(yaw=math.radians(80.0), course=math.radians(90.0))
    line = _world().live_status_line(_agent(base))

    assert "course" in line
    assert "90.0deg" in line.replace("+", ""), "course intent in degrees"
    assert "drift" in line
    assert "10.0deg" in line.replace("+", ""), "drift = wrap(course - yaw)"


def test_live_status_line_no_odometry_is_honest() -> None:
    """odom_age_s() None (stack down / never connected) -> the honest fallback,
    never a fabricated (0, 0) pose."""
    base = _FakeHW()
    base._age = None
    line = _world().live_status_line(_agent(base))
    assert line == "(no odometry — stack down?)"

    # A missing base (driver never constructed) degrades the same way.
    assert _world().live_status_line(SimpleNamespace(_base=None)) == (
        "(no odometry — stack down?)"
    )
    assert _world().live_status_line(None) == "(no odometry — stack down?)"


def test_live_status_line_never_raises_on_a_broken_driver() -> None:
    """A driver whose pose read explodes degrades to the honest fallback."""

    class _Broken:
        def odom_age_s(self):
            return 0.1

        def get_position(self):
            raise RuntimeError("boom")

        def get_heading(self):
            return 0.0

    line = _world().live_status_line(_agent(_Broken()))
    assert line == "(no odometry — stack down?)"
