# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real heading-INTENT (course) tracking — drift-compensated turns (RED first).

Field bug (CEO, 2026-07-13 evening): a multi-step relative plan ('前进3米,
右转90度,前进2米,右转90度…' — a square path) came out SKEWED. During each
straight leg the local planner slightly changes heading (obstacle avoidance,
path corrections); the next 'turn 90°' then rotated 90° from the DRIFTED
heading, not from the intended course — the error accumulated every leg.

Pinned here:

* CourseTracker (go2w_real_course.py): course_yaw = the map-frame INTENDED
  heading (None = unset). ensure(actual) anchors when unset; apply_turn /
  set_course advance intent; resolve(actual) NEVER re-anchors the heading —
  beyond the 45° REANCHOR_LIMIT_DEG it only raises the loud-report flag (the
  2026-07-13 15:32 field disaster: the old re-anchor adopted a pathFollower
  reverse-flip and drove leg 2 backward); reset() forgets intent.
  Deterministic — no LLM input beyond the operator's requested degrees
  (Inv-1 parity with turned()).
* RealTurnSkill: rotates to the ABSOLUTE target wrap(course + requested);
  the commanded delta wrap(target - actual) is <=180° by construction, so
  'turn right 90' from a +12°-drifted heading commands ≈ -102° and lands ON
  the intended course. Compensation is reported honestly (result_data +
  message; PROMINENTLY past 45°); verify_hint grades the COMMANDED delta. On
  rotate success course := target; on failure course resets (intent state
  unknown — never guess).
* RealMoveRelativeSkill: straight legs run ALONG THE COURSE heading when set
  (live yaw only anchors an unset course; a move is a POSITION chase — the
  live yaw NEVER re-anchors the course) — the square's legs stay parallel
  to intent even after drift displaced the heading. Moves never change course.
  (Position-intent behavior is pinned in test_world_go2w_real_intent_pose.py.)
* Reset seams: navigate / route_via / explore start / stop (estop) / operator
  interrupt all reset the course (free navigation or emergency = intent gone).
* course_locked(tol_deg=10) verify oracle: |wrap(actual - course)| <= tol;
  fail-safe False (unset course / no base / error).

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


class _CourseFakeHW:
    """Fake driver mirroring the real contract + the embodiment's course seam.

    The embodiment rides the tracker on the driver (base.course_tracker) the
    same way it rides explore/route managers — VGG GoalExecutor contexts carry
    no world services, but always wire base. ``set_yaw`` simulates the local
    planner drifting the heading during a straight leg (avoidance/corrections).
    """

    def __init__(self, yaw: float = 0.0, x: float = 0.0, y: float = 0.0,
                 latched: bool = False, turns: bool = True,
                 moves: bool = True) -> None:
        from zeno.vcli.worlds.go2w_real_course import CourseTracker

        self.estop_latched = latched
        self.rotate_anchor_yaw: float | None = None
        self.move_anchor_xy: tuple[float, float] | None = None
        self._yaw = yaw
        self._pos = [x, y, 0.0]
        self._turns = turns
        self._moves = moves
        self.rotate_calls: list[tuple[float, float]] = []
        self.nav_calls: list[tuple[float, float]] = []
        self.cancelled = 0
        self.course_tracker = CourseTracker()

    # -- pose truth ----------------------------------------------------
    def get_heading(self) -> float:
        return self._yaw

    def get_position(self) -> list[float]:
        return list(self._pos)

    def set_yaw(self, yaw: float) -> None:
        """Planner drift injection: heading changed OUTSIDE any turn command."""
        self._yaw = _wrap(yaw)

    # -- motion --------------------------------------------------------
    def rotate(self, delta_yaw_rad: float, yaw_rate: float = 0.5) -> bool:
        self.rotate_calls.append((float(delta_yaw_rad), float(yaw_rate)))
        self.rotate_anchor_yaw = self._yaw
        if self._turns:
            self._yaw = _wrap(self._yaw + float(delta_yaw_rad))
        return self._turns

    def navigate_to(self, x: float, y: float, timeout: float = 120.0) -> bool:
        self.nav_calls.append((float(x), float(y)))
        self.move_anchor_xy = (self._pos[0], self._pos[1])
        if self._moves:
            self._pos = [float(x), float(y), 0.0]
        return self._moves

    # -- safety --------------------------------------------------------
    def estop(self) -> bool:
        return True

    def nav_cancel(self) -> bool:
        return True

    def cancel_navigation(self) -> None:
        self.cancelled += 1


def _ctx(base=None, instruction: str = "", services: dict | None = None):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


def _turn_skill():
    from zeno.vcli.worlds.go2w_real_turn_skills import RealTurnSkill

    return RealTurnSkill()


def _move_skill():
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    return RealMoveRelativeSkill()


# ---------------------------------------------------------------------------
# CourseTracker — deterministic intent state (anchor / advance / cap / reset)
# ---------------------------------------------------------------------------


def test_course_tracker_starts_unset_and_anchors_on_ensure():
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    t = CourseTracker()
    assert t.course_yaw is None
    assert t.ensure(0.3) == pytest.approx(0.3)
    assert t.course_yaw == pytest.approx(0.3)
    # ensure() anchors ONCE — a later drifted yaw never re-anchors silently
    assert t.ensure(0.9) == pytest.approx(0.3)


def test_course_tracker_apply_turn_advances_intent_wrapped():
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    t = CourseTracker()
    t.ensure(math.pi - 0.1)
    t.apply_turn(0.3)  # crosses +pi
    assert t.course_yaw == pytest.approx(-math.pi + 0.2)


def test_course_tracker_reset_clears_intent():
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    t = CourseTracker()
    t.ensure(1.0)
    t.reset()
    assert t.course_yaw is None


def test_course_tracker_resolve_keeps_course_within_cap():
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    t = CourseTracker()
    t.ensure(0.0)
    course, reanchored = t.resolve(math.radians(12.0))  # small drift
    assert course == pytest.approx(0.0)
    assert reanchored is False


def test_course_tracker_resolve_keeps_intent_past_45_degrees():
    """SEMANTICS CHANGED (field disaster 2026-07-13 15:32): a big deviation no
    longer re-anchors the heading intent — resolve() keeps the course and
    raises the loud-report flag instead."""
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    t = CourseTracker()
    t.ensure(0.0)
    actual = math.radians(60.0)  # NOT small drift: detour / manual takeover
    course, deviates = t.resolve(actual)
    assert deviates is True
    assert course == pytest.approx(0.0)
    assert t.course_yaw == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# THE MONEY TEST — turn right 90 from a +12°-drifted heading commands ≈ -102°
# (the drift is folded in; course, not the drifted yaw, defines the turn)
# ---------------------------------------------------------------------------


def test_turn_compensates_drift_to_intended_course():
    hw = _CourseFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)          # course anchored at 0 (leg start)
    hw.set_yaw(math.radians(12.0))         # planner drifted +12° during the leg
    result = _turn_skill().execute({"direction": "right", "degrees": 90},
                                   _ctx(base=hw))
    assert result.success, result.error_message
    delta, _rate = hw.rotate_calls[0]
    assert delta == pytest.approx(math.radians(-102.0)), (
        "command must fold the +12° drift into the -90° request (-102°) so the "
        "robot lands ON the intended course, not 90° from the drifted heading")
    assert hw.course_tracker.course_yaw == pytest.approx(-math.pi / 2)


def test_turn_reports_compensation_honestly():
    hw = _CourseFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(12.0))
    result = _turn_skill().execute({"direction": "right", "degrees": 90},
                                   _ctx(base=hw))
    data = result.result_data or {}
    assert data.get("compensation_deg") == pytest.approx(-12.0, abs=0.1)
    assert data.get("command_deg") == pytest.approx(-102.0, abs=0.1)
    msg = str(data.get("message", ""))
    assert "补偿" in msg or "compensat" in msg.lower(), (
        "the operator must SEE that 102° was commanded for a 90° ask")


def test_turn_verify_hint_grades_the_commanded_delta():
    hw = _CourseFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(12.0))
    result = _turn_skill().execute({"direction": "right", "degrees": 90},
                                   _ctx(base=hw))
    # 0.6 * |commanded 102°| = 61.2 -> round 61 (NOT 54 — the robot must
    # actually rotate the compensated amount for the turn to be real)
    assert (result.result_data or {}).get("verify_hint") == "turned(61)"


def test_turn_without_drift_commands_the_plain_delta():
    hw = _CourseFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)
    result = _turn_skill().execute({"direction": "left", "degrees": 90},
                                   _ctx(base=hw))
    assert result.success
    assert hw.rotate_calls[0][0] == pytest.approx(math.pi / 2)
    assert (result.result_data or {}).get("compensation_deg") == pytest.approx(0.0)


def test_turn_anchors_unset_course_then_turns_plain():
    """First-ever command of a session: course unset -> anchor to actual yaw,
    execute exactly the requested delta, end course = anchored + requested."""
    hw = _CourseFakeHW(yaw=0.5)
    result = _turn_skill().execute({"direction": "left", "degrees": 90},
                                   _ctx(base=hw))
    assert result.success
    assert hw.rotate_calls[0][0] == pytest.approx(math.pi / 2)
    assert hw.course_tracker.course_yaw == pytest.approx(0.5 + math.pi / 2)


# ---------------------------------------------------------------------------
# Square-path integration — 2 legs + 2 turns, drift injected each leg; every
# turn compensates and the final course is -180° from the start
# ---------------------------------------------------------------------------


def test_square_path_two_legs_compensate_each_turn():
    hw = _CourseFakeHW(yaw=0.0, x=0.0, y=0.0)
    move, turn = _move_skill(), _turn_skill()

    # Leg 1: 前进3米 — anchors course at 0, drives along it.
    r = move.execute({"direction": "forward", "distance": 3.0}, _ctx(base=hw))
    assert r.success, r.error_message
    assert hw.nav_calls[0] == (pytest.approx(3.0), pytest.approx(0.0))
    assert hw.course_tracker.course_yaw == pytest.approx(0.0)

    # Planner drifted +12° during the leg; 右转90 must command -102°.
    hw.set_yaw(math.radians(12.0))
    r = turn.execute({"direction": "right", "degrees": 90}, _ctx(base=hw))
    assert r.success, r.error_message
    assert hw.rotate_calls[0][0] == pytest.approx(math.radians(-102.0))
    assert hw.course_tracker.course_yaw == pytest.approx(-math.pi / 2)

    # Leg 2: 前进2米 ALONG THE COURSE (-90°), even though yaw sits at -90°+drift.
    hw.set_yaw(math.radians(-80.0))  # drifted +10° off the -90° course
    r = move.execute({"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r.success, r.error_message
    tx, ty = hw.nav_calls[1]
    assert tx == pytest.approx(3.0, abs=1e-6)
    assert ty == pytest.approx(-2.0, abs=1e-6), (
        "leg 2 must run parallel to the INTENDED course (-90°), not the "
        "drifted -80° heading")
    assert hw.course_tracker.course_yaw == pytest.approx(-math.pi / 2), (
        "moves never change the course")

    # Second drifted turn compensates again; course ends at -180°.
    r = turn.execute({"direction": "right", "degrees": 90}, _ctx(base=hw))
    assert r.success, r.error_message
    assert hw.rotate_calls[1][0] == pytest.approx(math.radians(-100.0))
    assert abs(hw.course_tracker.course_yaw) == pytest.approx(math.pi)


# ---------------------------------------------------------------------------
# 45° threshold — SEMANTICS CHANGED (field disaster 2026-07-13 15:32): a big
# deviation NEVER re-anchors the intent. Turns still chase the ABSOLUTE
# intended heading (wrapped <=180° by construction) and REPORT the deviation
# prominently; moves keep driving along the course, full stop.
# ---------------------------------------------------------------------------


def test_turn_beyond_45_compensates_to_intent_and_reports_loudly():
    hw = _CourseFakeHW(yaw=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(60.0))  # way past the 45° small-drift threshold
    result = _turn_skill().execute({"direction": "right", "degrees": 90},
                                   _ctx(base=hw))
    assert result.success, result.error_message
    # target = wrap(course 0 - 90) = -90; command = wrap(-90 - 60) = -150
    assert hw.rotate_calls[0][0] == pytest.approx(math.radians(-150.0)), (
        "the intent is ALWAYS honored: the turn chases the absolute intended "
        "heading — the old plain-delta re-anchor inverted the operator's plan")
    data = result.result_data or {}
    assert data.get("course_deviation_large") is True
    assert data.get("compensation_deg") == pytest.approx(-60.0, abs=0.1)
    msg = str(data.get("message", ""))
    assert "注意" in msg and "航向偏离" in msg and "补偿" in msg, (
        "a >45° deviation must be reported PROMINENTLY, never silently adopted")
    # course = intended target: 0° + (-90°) = -90°
    assert hw.course_tracker.course_yaw == pytest.approx(-math.pi / 2)


def test_move_relative_beyond_45_still_follows_the_course():
    hw = _CourseFakeHW(yaw=0.0, x=0.0, y=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(60.0))
    r = _move_skill().execute({"direction": "forward", "distance": 2.0},
                              _ctx(base=hw))
    assert r.success
    tx, ty = hw.nav_calls[0]
    assert tx == pytest.approx(2.0, abs=1e-6), (
        "a move is a POSITION chase — the stray yaw is irrelevant; the leg "
        "runs along the operator's course")
    assert ty == pytest.approx(0.0, abs=1e-6)
    assert hw.course_tracker.course_yaw == pytest.approx(0.0), (
        "the course stays the operator's intent — never re-anchored by a move")


# ---------------------------------------------------------------------------
# Failure / cancel — intent state unknown: reset, never guess
# ---------------------------------------------------------------------------


def test_turn_failure_resets_course():
    hw = _CourseFakeHW(yaw=0.0, turns=False)  # rotate commanded but fails
    hw.course_tracker.ensure(0.0)
    result = _turn_skill().execute({"direction": "left", "degrees": 90},
                                   _ctx(base=hw))
    assert not result.success
    assert hw.course_tracker.course_yaw is None, (
        "a failed/cancelled rotation leaves the intent unknown — reset")


def test_turn_estop_fail_fast_keeps_course():
    """Nothing was commanded (fail-fast before motion) — intent unchanged."""
    hw = _CourseFakeHW(yaw=0.0, latched=True)
    hw.course_tracker.ensure(0.3)
    result = _turn_skill().execute({"direction": "left"}, _ctx(base=hw))
    assert not result.success
    assert hw.rotate_calls == []
    assert hw.course_tracker.course_yaw == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Straight legs follow the course, not the live yaw
# ---------------------------------------------------------------------------


def test_move_relative_follows_course_not_live_yaw():
    hw = _CourseFakeHW(yaw=0.0, x=0.0, y=0.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(20.0))  # drift within the cap
    r = _move_skill().execute({"direction": "forward", "distance": 2.0},
                              _ctx(base=hw))
    assert r.success, r.error_message
    tx, ty = hw.nav_calls[0]
    assert tx == pytest.approx(2.0, abs=1e-6)
    assert ty == pytest.approx(0.0, abs=1e-6)
    assert hw.course_tracker.course_yaw == pytest.approx(0.0)


def test_move_relative_left_is_90_off_the_course():
    hw = _CourseFakeHW(yaw=0.0, x=1.0, y=1.0)
    hw.course_tracker.ensure(0.0)
    hw.set_yaw(math.radians(-15.0))
    r = _move_skill().execute({"direction": "left", "distance": 1.0},
                              _ctx(base=hw))
    assert r.success
    tx, ty = hw.nav_calls[0]
    assert tx == pytest.approx(1.0, abs=1e-6)
    assert ty == pytest.approx(2.0, abs=1e-6)


def test_move_relative_anchors_unset_course_to_live_yaw():
    hw = _CourseFakeHW(yaw=math.radians(30.0), x=0.0, y=0.0)
    r = _move_skill().execute({"direction": "forward", "distance": 1.0},
                              _ctx(base=hw))
    assert r.success
    tx, ty = hw.nav_calls[0]
    assert tx == pytest.approx(math.cos(math.radians(30.0)))
    assert ty == pytest.approx(math.sin(math.radians(30.0)))
    assert hw.course_tracker.course_yaw == pytest.approx(math.radians(30.0))


def test_skills_without_tracker_keep_todays_behavior():
    """Foreign/older base without course_tracker: live-yaw math, plain deltas —
    byte-identical to the pre-course world (additive, backward-compatible)."""
    class _Bare:
        estop_latched = False
        rotate_anchor_yaw = None
        move_anchor_xy = None

        def __init__(self):
            self._yaw = math.radians(20.0)
            self.rotate_calls, self.nav_calls = [], []

        def get_heading(self):
            return self._yaw

        def get_position(self):
            return [0.0, 0.0, 0.0]

        def rotate(self, d, yaw_rate=0.5):
            self.rotate_calls.append(d)
            return True

        def navigate_to(self, x, y, timeout=120.0):
            self.nav_calls.append((x, y))
            return True

    hw = _Bare()
    assert _turn_skill().execute({"direction": "right", "degrees": 90},
                                 _ctx(base=hw)).success
    assert hw.rotate_calls[0] == pytest.approx(-math.pi / 2)
    assert _move_skill().execute({"direction": "forward", "distance": 2.0},
                                 _ctx(base=hw)).success
    assert hw.nav_calls[0][0] == pytest.approx(2.0 * math.cos(hw._yaw))


# ---------------------------------------------------------------------------
# Reset seams — free navigation / estop / interrupt forget the intent
# ---------------------------------------------------------------------------


def test_navigate_skill_resets_course():
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    hw = _CourseFakeHW()
    hw.course_tracker.ensure(0.7)
    r = RealNavigateSkill().execute({"x": 2.0, "y": 3.0}, _ctx(base=hw))
    assert r.success
    assert hw.course_tracker.course_yaw is None, (
        "free navigation = the relative-course intent is over; reset")


def test_stop_skill_resets_course():
    from zeno.vcli.worlds.go2w_real_skills import RealStopSkill

    hw = _CourseFakeHW()
    hw.course_tracker.ensure(0.7)
    RealStopSkill().execute({}, _ctx(base=hw))
    assert hw.course_tracker.course_yaw is None


def test_route_via_skill_resets_course():
    from zeno.vcli.worlds.go2w_real_route_skills import RealRouteViaSkill

    hw = _CourseFakeHW()
    hw.course_tracker.ensure(0.7)
    mgr = SimpleNamespace(start_route=lambda: (True, "ok"),
                          goto_via_route=lambda x, y, timeout: True)
    r = RealRouteViaSkill().execute({"x": 9.0, "y": 9.0},
                                    _ctx(base=hw, services={"route": mgr}))
    assert r.success
    assert hw.course_tracker.course_yaw is None


def test_explore_skill_resets_course():
    from zeno.vcli.worlds.go2w_real_skills import RealExploreSkill

    hw = _CourseFakeHW()
    hw.course_tracker.ensure(0.7)
    mgr = SimpleNamespace(start_explore=lambda scenario: (True, "ok"))
    r = RealExploreSkill().execute({}, _ctx(base=hw, services={"explore": mgr}))
    assert r.success
    assert hw.course_tracker.course_yaw is None


def test_operator_interrupt_resets_course():
    from zeno.vcli.worlds import resolve_world_named

    hw = _CourseFakeHW()
    hw.course_tracker.ensure(0.7)
    world = resolve_world_named("go2w_real")
    world.on_operator_interrupt(SimpleNamespace(_base=hw))
    assert hw.cancelled >= 1
    assert hw.course_tracker.course_yaw is None


# ---------------------------------------------------------------------------
# course_locked() oracle — truth table + fail-safe (Inv-1 sandbox rules)
# ---------------------------------------------------------------------------


def _course_locked(hw):
    from zeno.vcli.worlds.go2w_real_verify import make_course_locked

    return make_course_locked(SimpleNamespace(_base=hw))


def test_course_locked_true_within_default_tolerance():
    hw = _CourseFakeHW(yaw=math.radians(5.0))
    hw.course_tracker.ensure(0.0)
    assert _course_locked(hw)() is True


def test_course_locked_false_beyond_default_tolerance():
    hw = _CourseFakeHW(yaw=math.radians(15.0))
    hw.course_tracker.ensure(0.0)
    assert _course_locked(hw)() is False


def test_course_locked_honors_tol_deg_param():
    hw = _CourseFakeHW(yaw=math.radians(15.0))
    hw.course_tracker.ensure(0.0)
    assert _course_locked(hw)(tol_deg=20.0) is True
    assert _course_locked(hw)(tol_deg=5.0) is False


def test_course_locked_wraps_across_pi():
    hw = _CourseFakeHW(yaw=-math.pi + 0.05)
    hw.course_tracker.ensure(math.pi - 0.05)  # 0.1 rad apart across the seam
    assert _course_locked(hw)() is True


def test_course_locked_false_when_course_unset():
    hw = _CourseFakeHW(yaw=0.0)  # tracker present but never anchored
    assert _course_locked(hw)() is False


def test_course_locked_fail_safe():
    from zeno.vcli.worlds.go2w_real_verify import make_course_locked

    assert make_course_locked(None)() is False
    assert make_course_locked(SimpleNamespace(_base=None))() is False
    # A base without the tracker attribute (foreign/older driver) -> False.
    assert make_course_locked(SimpleNamespace(_base=object()))() is False

    class _Boom:
        course_tracker = property(lambda self: (_ for _ in ()).throw(RuntimeError))

    assert make_course_locked(SimpleNamespace(_base=_Boom()))() is False


def test_course_locked_is_marked_predicate_oracle():
    from zeno.vcli.cognitive.evidence_classifier import PREDICATE_ORACLE_ATTR
    from zeno.vcli.worlds.go2w_real_verify import make_course_locked

    fn = make_course_locked(SimpleNamespace(_base=None))
    assert getattr(fn, PREDICATE_ORACLE_ATTR, False) is True


# ---------------------------------------------------------------------------
# Wiring — embodiment seam, verify namespace, vocab, capability card
# ---------------------------------------------------------------------------


def _world():
    from zeno.vcli.worlds import resolve_world_named

    return resolve_world_named("go2w_real")


def test_embodiment_rides_course_tracker_on_driver_and_services():
    from zeno.vcli.worlds.go2w_real_course import CourseTracker

    emb = _world().build_embodiment()
    tracker = getattr(emb._base, "course_tracker", None)
    assert isinstance(tracker, CourseTracker)
    assert emb._build_context().services.get("course") is tracker, (
        "ONE tracker object on both seams — services and the driver ride")
    assert tracker.course_yaw is None, "session start = course unset"


def test_verify_namespace_serves_course_locked():
    ns = _world().build_verify_namespace(SimpleNamespace(_base=_CourseFakeHW()))
    assert callable(ns.get("course_locked"))


def test_vocab_teaches_course_locked():
    vocab = _world().decompose_vocab()
    assert "course_locked" in vocab.verify_functions
    assert "course_locked" in vocab.verify_fn_signatures
    assert "tol_deg" in vocab.verify_fn_signatures["course_locked"]


def test_vocab_square_path_fewshot_teaches_compensated_legs():
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES as ex

    marker = 'Task: "前进2米,右转90度"'
    assert marker in ex, "multi-leg relative-plan few-shot missing"
    seg = ex.split(marker, 1)[1]
    nxt = seg.find("Task:")
    seg = seg[: nxt if nxt >= 0 else len(seg)]
    assert "move_relative_skill" in seg and "turn_skill" in seg
    assert seg.count('"strategy"') == 2
    assert "course_locked()" in seg
    assert "bringup_skill" not in seg
    assert len(ex) <= 6000, "REAL_DECOMPOSE_EXAMPLES over the ~6000 budget"


def test_capability_md_documents_course_compensation():
    from pathlib import Path

    import zeno.vcli.worlds.go2w_real as w

    text = Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")
    assert "course_locked(" in text
    assert "45" in text, "the 45° re-anchor rule must be on the capability card"
    assert "航向" in text or "course" in text.lower()
