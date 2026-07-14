# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Forward-only reverse policy — backward moves become BLIND ESCAPES (RED).

CEO safety ruling (2026-07-13 evening): the Mid-360 is front-mounted, pitched
20° down-forward — the robot is BLIND behind. Reverse driving therefore stops
being a normal navigation mode (the nav stack goes forward-only in the same
change set) and survives only as a short escape maneuver:

* move_relative backward <= 1.5 m -> driver.reverse_blind() on the DIRECT
  teleop channel (slow, straight, odometry-tracked) — never the planner;
* backward > 1.5 m -> honest refusal steering to 掉头+前进 (turn around and
  drive forward, with obstacle avoidance);
* the escape is OFF-PLAN: intent position re-anchors to wherever the robot
  actually ends (course heading untouched);
* a base without reverse_blind (foreign/back-compat) keeps the old planner
  path byte-identically.

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


class _EscapeFakeHW:
    """Fake driver with the blind-escape seam + waypoint fallback recording."""

    def __init__(self, x: float = 0.0, y: float = 0.0, yaw: float = 0.0,
                 latched: bool = False, escape_moves: bool = True) -> None:
        from zeno.vcli.worlds.go2w_real_course import CourseTracker

        self.estop_latched = latched
        self._pos = [float(x), float(y), 0.0]
        self._yaw = float(yaw)
        self._escape_moves = escape_moves
        self.nav_calls: list[tuple[float, float]] = []
        self.reverse_calls: list[float] = []
        self.course_tracker = CourseTracker()

    def get_position(self) -> list[float]:
        return list(self._pos)

    def get_heading(self) -> float:
        return self._yaw

    def odom_age_s(self) -> float:
        return 0.2

    def navigate_to(self, x: float, y: float, timeout: float = 120.0) -> bool:
        self.nav_calls.append((float(x), float(y)))
        self._pos = [float(x), float(y), 0.0]
        return True

    def reverse_blind(self, distance_m: float, speed: float = 0.25) -> bool:
        self.reverse_calls.append(float(distance_m))
        if self._escape_moves:
            self._pos[0] -= distance_m * math.cos(self._yaw)
            self._pos[1] -= distance_m * math.sin(self._yaw)
        return self._escape_moves


class _NoEscapeFakeHW:
    """Foreign/older base WITHOUT the escape seam (back-compat pin)."""

    def __init__(self, x: float = 0.0, y: float = 0.0, yaw: float = 0.0) -> None:
        from zeno.vcli.worlds.go2w_real_course import CourseTracker

        self.estop_latched = False
        self._pos = [float(x), float(y), 0.0]
        self._yaw = float(yaw)
        self.nav_calls: list[tuple[float, float]] = []
        self.course_tracker = CourseTracker()

    def get_position(self) -> list[float]:
        return list(self._pos)

    def get_heading(self) -> float:
        return self._yaw

    def odom_age_s(self) -> float:
        return 0.2

    def navigate_to(self, x: float, y: float, timeout: float = 120.0) -> bool:
        self.nav_calls.append((float(x), float(y)))
        self._pos = [float(x), float(y), 0.0]
        return True


def _ctx(base=None, instruction: str = ""):
    return SimpleNamespace(base=base, services={}, instruction=instruction)


def _move():
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    return RealMoveRelativeSkill()


# ---------------------------------------------------------------------------
# Routing — short backward = blind escape, long backward = refusal
# ---------------------------------------------------------------------------


def test_backward_short_routes_to_reverse_blind_not_planner():
    hw = _EscapeFakeHW(yaw=0.0)
    result = _move().execute({"direction": "backward", "distance": 1.0}, _ctx(hw))
    assert result.success, result.error_message
    assert hw.reverse_calls == [pytest.approx(1.0)]
    assert hw.nav_calls == [], "backward must NEVER go through the planner"


def test_backward_escape_message_warns_blind_zone():
    hw = _EscapeFakeHW()
    result = _move().execute({"direction": "backward", "distance": 0.5}, _ctx(hw))
    text = str(result.result_data or {})
    assert "盲" in text, "the escape reply must warn the rear is a sensor blind zone"


def test_backward_escape_verifies_with_moved():
    hw = _EscapeFakeHW()
    result = _move().execute({"direction": "backward", "distance": 1.0}, _ctx(hw))
    assert "moved(" in str(result.result_data or {})


def test_backward_beyond_cap_is_refused_with_turnaround_hint():
    hw = _EscapeFakeHW()
    result = _move().execute({"direction": "backward", "distance": 3.0}, _ctx(hw))
    assert not result.success
    assert hw.reverse_calls == [] and hw.nav_calls == []
    msg = (result.error_message or "")
    assert "掉头" in msg, "long reverse must steer to turn-around-and-forward"


def test_forward_still_goes_through_the_planner():
    hw = _EscapeFakeHW()
    result = _move().execute({"direction": "forward", "distance": 2.0}, _ctx(hw))
    assert result.success
    assert hw.nav_calls and hw.reverse_calls == []


def test_backward_estop_latched_fails_fast():
    hw = _EscapeFakeHW(latched=True)
    result = _move().execute({"direction": "backward", "distance": 1.0}, _ctx(hw))
    assert not result.success
    assert result.diagnosis_code == "estop_latched"
    assert hw.reverse_calls == []


# ---------------------------------------------------------------------------
# Intent frame — an escape is OFF-PLAN: position re-anchors to reality
# ---------------------------------------------------------------------------


def test_backward_escape_reanchors_intent_position_to_actual():
    """After the blind escape the plan frame follows the REAL pose (recovery
    maneuver, not a plan leg): a following forward leg starts from reality."""
    hw = _EscapeFakeHW(x=2.0, y=0.0, yaw=0.0)
    move = _move()
    assert move.execute({"direction": "backward", "distance": 1.0}, _ctx(hw)).success
    # escape landed at x=1.0; intent must say so
    intent = hw.course_tracker.intent_xy
    assert intent is not None
    assert intent[0] == pytest.approx(1.0, abs=0.05)
    assert intent[1] == pytest.approx(0.0, abs=0.05)


def test_backward_escape_keeps_course_heading():
    hw = _EscapeFakeHW(yaw=0.3)
    hw.course_tracker.ensure(0.3)
    _move().execute({"direction": "backward", "distance": 0.5}, _ctx(hw))
    assert hw.course_tracker.course_yaw == pytest.approx(0.3, abs=1e-6)


def test_backward_escape_zero_displacement_is_honest_failure():
    hw = _EscapeFakeHW(escape_moves=False)
    result = _move().execute({"direction": "backward", "distance": 1.0}, _ctx(hw))
    assert not result.success, "no displacement must not report success"


# ---------------------------------------------------------------------------
# Back-compat — a base without the escape seam keeps the planner path
# ---------------------------------------------------------------------------


def test_backward_without_escape_seam_falls_back_to_planner():
    hw = _NoEscapeFakeHW(yaw=0.0)
    assert not hasattr(hw, "reverse_blind")
    result = _move().execute({"direction": "backward", "distance": 1.0}, _ctx(hw))
    assert result.success
    assert hw.nav_calls, "foreign base keeps the old waypoint path"


# ---------------------------------------------------------------------------
# Self-knowledge — the capability card teaches the new policy
# ---------------------------------------------------------------------------


def test_capability_md_documents_forward_only_policy():
    from pathlib import Path

    import zeno.vcli.worlds.go2w_real as w

    text = Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")
    assert "盲" in text and "脱困" in text, (
        "capability card must teach: rear is blind, reverse is escape-only")
