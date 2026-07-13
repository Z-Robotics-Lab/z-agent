# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real INTENT POSE — position + heading plan frame (RED first).

FIELD DISASTER (oplog 2026-07-13 15:32-15:34, REAL robot): multi-leg plan
'前进3米,左转90,前进1米,右转90,前进3米'. Leg 1: move_relative forward 3.0
from (0.07,-0.06), course +0.6°. The robot arrived at (2.54,-0.02) — 0.5 m
SHORT (arrival radius + hesitation) — FACING -179.5° (the twoWayDrive
pathFollower flipped into reverse during the chase). Then OUR OWN 45° cap did
'RE-ANCHOR |drift|=179.9deg > 45deg — course := actual -179.5deg' and leg 2
'forward 3m' drove 3 m BACKWARD to (-0.36,-0.09). The operator's plan was
inverted by our own compensation cap. Operator verdict: '避障会影响机器人对
自己全局位置的判断,多个小任务组合执行不行'.

Redesign pinned here:

* INTENT POSE: CourseTracker tracks the intended POSITION as well as the
  heading. move_relative computes its target from the INTENT position +
  d * course_direction (the first relative command anchors intent to the
  actual pose); after commanding, the intent advances the FULL requested d
  along the course REGARDLESS of where the robot stopped — shortfalls and
  avoidance displacement self-correct at the next leg instead of accumulating.
* Position deviation cap: |actual - intent| > 1.5 m at a leg start (big
  detour / manual takeover = stale plan frame) -> the intent position
  re-anchors to the actual pose AND the result says so honestly.
* NO yaw re-anchor on moves: a move is a POSITION chase — the current yaw is
  irrelevant to the target; the course stays the operator's intent, full stop.
* Turns rotate to the ABSOLUTE target wrap(course + signed_delta) — <=180° by
  construction; beyond 45° deviation the compensation is REPORTED prominently
  (注意:检测到大幅航向偏离…), never silently adopted.
* Manual takeover / resume reset the whole intent (heading + position).

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


class _FieldFakeHW:
    """Fake driver replaying FIELD arrivals: navigate_to ends wherever the
    scripted arrival queue says (shortfall / avoidance displacement / the
    pathFollower reverse-flip), not at the commanded target."""

    def __init__(self, x: float = 0.0, y: float = 0.0, yaw: float = 0.0) -> None:
        from zeno.vcli.worlds.go2w_real_course import CourseTracker

        self.estop_latched = False
        self._pos = [float(x), float(y), 0.0]
        self._yaw = float(yaw)
        self.nav_calls: list[tuple[float, float]] = []
        self.rotate_calls: list[float] = []
        #: queue of scripted (x, y, yaw) END poses; empty -> land exactly.
        self.arrivals: list[tuple[float, float, float]] = []
        self.course_tracker = CourseTracker()

    def get_position(self) -> list[float]:
        return list(self._pos)

    def get_heading(self) -> float:
        return self._yaw

    def set_yaw(self, yaw: float) -> None:
        self._yaw = _wrap(yaw)

    def navigate_to(self, x: float, y: float, timeout: float = 120.0) -> bool:
        self.nav_calls.append((float(x), float(y)))
        if self.arrivals:
            ex, ey, eyaw = self.arrivals.pop(0)
            self._pos = [float(ex), float(ey), 0.0]
            self._yaw = _wrap(float(eyaw))
        else:
            self._pos = [float(x), float(y), 0.0]
        return True

    def rotate(self, delta: float, yaw_rate: float = 0.5) -> bool:
        self.rotate_calls.append(float(delta))
        self._yaw = _wrap(self._yaw + float(delta))
        return True

    def estop(self) -> bool:
        return True

    def estop_release(self) -> bool:
        return True

    def manual(self) -> bool:
        return True

    def nav_cancel(self) -> bool:
        return True


def _ctx(base=None, instruction: str = ""):
    return SimpleNamespace(base=base, services={}, instruction=instruction)


def _move():
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    return RealMoveRelativeSkill()


def _turn():
    from zeno.vcli.worlds.go2w_real_turn_skills import RealTurnSkill

    return RealTurnSkill()


# ---------------------------------------------------------------------------
# THE MONEY TEST — the exact 15:32 field log, replayed
# ---------------------------------------------------------------------------


def test_field_replay_leg2_forward_targets_intent_frame_never_reverse():
    """Leg 1 forward 3 m from (0.07,-0.06) course +0.6°; the robot stops 0.5 m
    short at (2.54,-0.02) facing -179.5° (pathFollower reverse-flip). Leg 2
    'forward 3 m' MUST target ≈(6.07, 0.00) in the INTENT frame — intent
    (3.07,-0.03) + 3 m along +0.6° — and the course MUST still be +0.6°.
    The old 45° yaw re-anchor drove this leg 3 m BACKWARD to (-0.36,-0.09)."""
    course0 = math.radians(0.6)
    hw = _FieldFakeHW(x=0.07, y=-0.06, yaw=course0)
    hw.arrivals.append((2.54, -0.02, math.radians(-179.5)))
    move = _move()

    r1 = move.execute({"direction": "forward", "distance": 3.0}, _ctx(base=hw))
    assert r1.success, r1.error_message
    t1x, t1y = hw.nav_calls[0]
    assert t1x == pytest.approx(0.07 + 3.0 * math.cos(course0), abs=1e-6)
    assert t1y == pytest.approx(-0.06 + 3.0 * math.sin(course0), abs=1e-6)

    r2 = move.execute({"direction": "forward", "distance": 3.0}, _ctx(base=hw))
    assert r2.success, r2.error_message
    t2x, t2y = hw.nav_calls[1]
    assert t2x == pytest.approx(6.07, abs=0.02), (
        "leg 2 must aim at the INTENDED trajectory (intent + 3 m along the "
        "course), NOT 3 m backward from the flipped -179.5° yaw")
    assert t2y == pytest.approx(0.0, abs=0.05)
    assert t2x > t1x, "forward means FORWARD along the plan — never reversed"
    assert hw.course_tracker.course_yaw == pytest.approx(course0), (
        "the course is the OPERATOR'S intent — a stray yaw (even 179.9° off) "
        "must never re-anchor it")


def test_move_never_reanchors_course_from_stray_yaw():
    """The 179.9° case, minimal: course 0, yaw flipped to 180 — a forward move
    still drives ALONG the course (+x), and the course stays 0."""
    hw = _FieldFakeHW(x=0.0, y=0.0, yaw=0.0)
    hw.course_tracker.ensure(0.0)
    hw.course_tracker.ensure_position((0.0, 0.0))
    hw.set_yaw(math.radians(-179.5))
    r = _move().execute({"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r.success, r.error_message
    tx, ty = hw.nav_calls[0]
    assert tx == pytest.approx(2.0, abs=1e-6)
    assert ty == pytest.approx(0.0, abs=1e-6)
    assert hw.course_tracker.course_yaw == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Shortfall self-correction — arrival-radius stops must not accumulate
# ---------------------------------------------------------------------------


def test_arrival_shortfall_self_corrects_across_two_legs():
    """Each leg stops 0.5 m short (arrival radius). Leg 2 targets the INTENDED
    trajectory: after 'forward 2 + forward 2' the commanded target is (4, 0),
    not (3.5, 0) — the shortfall does not accumulate."""
    hw = _FieldFakeHW(x=0.0, y=0.0, yaw=0.0)
    hw.arrivals.append((1.5, 0.0, 0.0))   # leg 1 ends 0.5 short
    move = _move()
    r1 = move.execute({"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r1.success
    assert hw.nav_calls[0] == (pytest.approx(2.0), pytest.approx(0.0))
    r2 = move.execute({"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r2.success
    assert hw.nav_calls[1] == (pytest.approx(4.0), pytest.approx(0.0)), (
        "leg 2 must start from the INTENT position (2,0), not the short (1.5,0)")


# ---------------------------------------------------------------------------
# Position deviation cap — >1.5 m = stale plan frame: re-anchor AND say so
# ---------------------------------------------------------------------------


def test_position_reanchors_beyond_1p5m_with_honest_message():
    hw = _FieldFakeHW(x=0.0, y=0.0, yaw=0.0)
    # Leg 1 commanded to (2,0) but a big avoidance detour ends at (0.1, 2.0):
    # 2.75 m off the intended trajectory — the plan frame is stale.
    hw.arrivals.append((0.1, 2.0, 0.0))
    move = _move()
    assert move.execute({"direction": "forward", "distance": 2.0},
                        _ctx(base=hw)).success
    r2 = move.execute({"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r2.success, r2.error_message
    tx, ty = hw.nav_calls[1]
    assert tx == pytest.approx(2.1, abs=1e-6), (
        "past the 1.5 m cap the intent position re-anchors to the ACTUAL pose")
    assert ty == pytest.approx(2.0, abs=1e-6)
    data = r2.result_data or {}
    assert data.get("position_reanchored") is True
    assert float(data.get("deviation_m", 0.0)) > 1.5
    msg = str(data.get("message", ""))
    assert ("锚" in msg or "anchor" in msg.lower()) and "偏离" in msg, (
        "a re-anchored plan frame must be reported honestly, never silent")


def test_position_within_cap_keeps_intent_and_stays_silent():
    hw = _FieldFakeHW(x=0.0, y=0.0, yaw=0.0)
    hw.arrivals.append((1.5, 0.3, 0.0))   # 0.58 m off intent (2,0): keep frame
    move = _move()
    assert move.execute({"direction": "forward", "distance": 2.0},
                        _ctx(base=hw)).success
    r2 = move.execute({"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r2.success
    assert hw.nav_calls[1] == (pytest.approx(4.0), pytest.approx(0.0))
    data = r2.result_data or {}
    assert data.get("position_reanchored") is not True
    assert "锚" not in str(data.get("message", ""))


# ---------------------------------------------------------------------------
# CourseTracker position API — deterministic intent state
# ---------------------------------------------------------------------------


def test_tracker_position_intent_anchor_advance_reset():
    from zeno.vcli.worlds.go2w_real_course import POSITION_REANCHOR_M, CourseTracker

    t = CourseTracker()
    assert t.intent_xy is None
    assert t.ensure_position((1.0, 2.0)) == (pytest.approx(1.0), pytest.approx(2.0))
    # anchored ONCE — a later pose never silently re-anchors
    assert t.ensure_position((9.0, 9.0)) == (pytest.approx(1.0), pytest.approx(2.0))
    xy, reanchored, dev = t.resolve_position((1.4, 2.0))   # 0.4 m: keep intent
    assert xy == (pytest.approx(1.0), pytest.approx(2.0))
    assert reanchored is False and dev == pytest.approx(0.4)
    far = (1.0 + POSITION_REANCHOR_M + 0.2, 2.0)
    xy, reanchored, dev = t.resolve_position(far)          # 1.7 m: stale frame
    assert reanchored is True and dev == pytest.approx(1.7)
    assert xy == (pytest.approx(far[0]), pytest.approx(far[1]))
    t.set_position(5.0, -1.0)
    assert t.intent_xy == (pytest.approx(5.0), pytest.approx(-1.0))
    t.reset()
    assert t.intent_xy is None and t.course_yaw is None


def test_tracker_resolve_never_reanchors_heading():
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    t = CourseTracker()
    t.ensure(0.0)
    course, deviates = t.resolve(math.radians(179.9))
    assert course == pytest.approx(0.0), (
        "heading intent is NEVER re-anchored from a stray yaw (the 179.9° "
        "field disaster) — only the loud-report flag is raised")
    assert deviates is True
    assert t.course_yaw == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Turns go to ABSOLUTE targets — big deviation is reported LOUDLY, not adopted
# ---------------------------------------------------------------------------


def test_turn_beyond_45_honors_intent_and_reports_loudly():
    hw = _FieldFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(-179.5))     # the field reverse-flip
    r = _turn().execute({"direction": "left", "degrees": 90}, _ctx(base=hw))
    assert r.success, r.error_message
    # target = wrap(course 0 + 90) = +90; command = wrap(90 - (-179.5)) = -90.5
    assert hw.rotate_calls[0] == pytest.approx(math.radians(-90.5), abs=1e-6), (
        "the turn chases the ABSOLUTE intended heading — wrapped <=180° by "
        "construction, never a re-anchor to the stray yaw")
    assert hw.course_tracker.course_yaw == pytest.approx(math.pi / 2)
    data = r.result_data or {}
    assert data.get("course_deviation_large") is True
    msg = str(data.get("message", ""))
    assert "注意" in msg and "航向偏离" in msg and "补偿" in msg, (
        "beyond 45° the compensation must be reported PROMINENTLY "
        "(注意:检测到大幅航向偏离X°,已按计划航向补偿)")


def test_turn_command_is_at_most_180_by_construction():
    hw = _FieldFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(120.0))
    r = _turn().execute({"direction": "left", "degrees": 90}, _ctx(base=hw))
    assert r.success
    assert abs(hw.rotate_calls[0]) <= math.pi + 1e-9
    # target = wrap(0 + 90) = 90; command = wrap(90 - 120) = -30
    assert hw.rotate_calls[0] == pytest.approx(math.radians(-30.0), abs=1e-6)


# ---------------------------------------------------------------------------
# Manual takeover / resume — the plan frame resets on the takeover seams
# ---------------------------------------------------------------------------


def _anchored_hw() -> _FieldFakeHW:
    hw = _FieldFakeHW()
    hw.course_tracker.ensure(0.7)
    hw.course_tracker.ensure_position((1.0, 1.0))
    return hw


def test_manual_takeover_tool_resets_intent():
    from zeno.vcli.worlds.go2w_real_tools import Go2WRealManualTool

    hw = _anchored_hw()
    ctx = SimpleNamespace(agent=SimpleNamespace(_base=hw))
    res = Go2WRealManualTool().execute({}, ctx)
    assert not res.is_error
    assert hw.course_tracker.course_yaw is None
    assert hw.course_tracker.intent_xy is None


def test_resume_tool_resets_intent():
    from zeno.vcli.worlds.go2w_real_tools import Go2WRealResumeTool

    hw = _anchored_hw()
    ctx = SimpleNamespace(agent=SimpleNamespace(_base=hw))
    res = Go2WRealResumeTool().execute({}, ctx)
    assert not res.is_error
    assert hw.course_tracker.course_yaw is None
    assert hw.course_tracker.intent_xy is None


def test_resume_skill_resets_intent():
    from zeno.vcli.worlds.go2w_real_lifecycle import RealResumeSkill

    hw = _anchored_hw()
    r = RealResumeSkill().execute({}, _ctx(base=hw))
    assert r.success
    assert hw.course_tracker.course_yaw is None
    assert hw.course_tracker.intent_xy is None


def test_stop_skill_resets_position_intent_too():
    from zeno.vcli.worlds.go2w_real_skills import RealStopSkill

    hw = _anchored_hw()
    RealStopSkill().execute({}, _ctx(base=hw))
    assert hw.course_tracker.intent_xy is None


# ---------------------------------------------------------------------------
# Capability card — the course bullet teaches position + heading intent
# ---------------------------------------------------------------------------


def test_capability_md_documents_position_intent():
    import zeno.vcli.worlds.go2w_real as w

    text = Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")
    assert "1.5" in text, "the 1.5 m position re-anchor cap must be on the card"
    assert "计划位置" in text or "position intent" in text.lower()
    assert "轨迹" in text or "trajectory" in text.lower(), (
        "the card must say moves aim at the INTENDED trajectory")
