# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real spatial SESSION MEMORY — PoseLedger + mark/goto place (RED first).

Field trace (CEO directive 2026-07-13 night): the operator said '回到刚才的
位置' and the model had NOTHING to resolve it against — it improvised
coordinates from earlier conversation text and drove to an invented spot.
RViz shows the live pose; the agent must also REMEMBER where it has been.

Pinned here:

* PoseLedger (go2w_real_places.py): DETERMINISTIC session memory riding the
  driver as ``base.pose_ledger`` + ``services['places']`` (the manager-rides-
  driver seam, same as explore/route/viz/course). Three facts:
  (a) ORIGIN 起点 — captured ONCE at the first fresh odometry pose;
  (b) BREADCRUMBS — bounded deque (N=20) of (monotonic_t, x, y, yaw) pushed
      at each motion command START; newest usable = '刚才的位置' (a crumb
      within 0.3 m of the current pose is a duplicate — skip to the older);
  (c) NAMED MARKS — mark(name, pose), auto-named 地点N when unnamed.
  Inv-1 parity: the model can TRIGGER marks but every pose value comes from
  odometry — never an LLM-authored coordinate.
* mark_place skill (记住这里/标记这里): stores the CURRENT odometry pose;
  refuses when odometry never arrived (no (0,0,0) fake marks).
* goto_place skill (回到起点/回到刚才的位置/回去): resolves 起点 -> origin,
  刚才/上一个 -> newest usable breadcrumb, else named mark; RESETS the course
  intent first (free navigation); drives via base.navigate_to; verify_hint
  at(x, y, tol=...) from the RESOLVED target; honest refusals otherwise.
* where enrichment: origin-relative distance+bearing, course+drift when set,
  marked place names — refusal on never-arrived odometry unchanged.
* Wiring/vocab/card: skills registered at the v2 markers; strategies
  mark_place_skill/goto_place_skill; few-shots 回到起点 / 记住这里叫充电桩;
  capability card teaches 全局意识 AND the honest limitation that places die
  on nav-stack restart (重启导航栈后地点失效 — relocalization is roadmap).

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


class _PlacesFakeHW:
    """Fake driver mirroring the real contract + the embodiment's ledger seam.

    ``set_pose`` simulates odometry updating OUTSIDE any command (the robot
    was driven elsewhere); ``age=None`` simulates a driver that KNOWS it never
    received odometry (the (0,0,0) default cache is not a pose).
    """

    def __init__(self, x=0.0, y=0.0, yaw=0.0, age=0.4, latched=False,
                 moves=True):
        from zeno.vcli.worlds.go2w_real_course import CourseTracker
        from zeno.vcli.worlds.go2w_real_places import PoseLedger

        self.estop_latched = latched
        self._pos = [float(x), float(y), 0.0]
        self._yaw = float(yaw)
        self._age = age
        self._moves = moves
        self.nav_calls: list[tuple[float, float]] = []
        self.rotate_calls: list[float] = []
        self.move_anchor_xy = None
        self.rotate_anchor_yaw = None
        self.pose_ledger = PoseLedger()
        self.course_tracker = CourseTracker()

    def get_position(self):
        return list(self._pos)

    def get_heading(self):
        return self._yaw

    def odom_age_s(self):
        return self._age

    def set_pose(self, x, y, yaw=None):
        self._pos = [float(x), float(y), 0.0]
        if yaw is not None:
            self._yaw = float(yaw)

    def navigate_to(self, x, y, timeout=120.0):
        self.nav_calls.append((float(x), float(y)))
        self.move_anchor_xy = (self._pos[0], self._pos[1])
        if self._moves:
            self._pos = [float(x), float(y), 0.0]
        return self._moves

    def rotate(self, delta, yaw_rate=0.5):
        self.rotate_calls.append(float(delta))
        self.rotate_anchor_yaw = self._yaw
        self._yaw = math.atan2(math.sin(self._yaw + delta),
                               math.cos(self._yaw + delta))
        return True

    def estop(self):
        return True

    def nav_cancel(self):
        return True

    def cancel_navigation(self):
        return None


def _ctx(base=None, instruction: str = "", services: dict | None = None):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


def _ledger():
    from zeno.vcli.worlds.go2w_real_places import PoseLedger

    return PoseLedger()


def _mark_skill():
    from zeno.vcli.worlds.go2w_real_places import RealMarkPlaceSkill

    return RealMarkPlaceSkill()


def _goto_skill():
    from zeno.vcli.worlds.go2w_real_places import RealGotoPlaceSkill

    return RealGotoPlaceSkill()


# ---------------------------------------------------------------------------
# PoseLedger truth table — origin once, breadcrumb order+bound, 刚才 skips
# current-pose duplicates, named marks
# ---------------------------------------------------------------------------


def test_ledger_starts_empty():
    led = _ledger()
    assert led.origin is None
    assert led.breadcrumbs == ()
    assert led.marks == {}


def test_origin_is_captured_once():
    led = _ledger()
    first = led.ensure_origin((1.0, 2.0, 0.3))
    assert first == (1.0, 2.0, 0.3)
    # A later pose must NEVER silently re-capture the origin.
    again = led.ensure_origin((9.0, 9.0, 1.0))
    assert again == (1.0, 2.0, 0.3)
    assert led.origin == (1.0, 2.0, 0.3)


def test_breadcrumbs_are_ordered_and_bounded_at_20():
    led = _ledger()
    for i in range(25):
        led.push_breadcrumb((float(i), 0.0, 0.0))
    crumbs = led.breadcrumbs
    assert len(crumbs) == 20, "breadcrumb deque is bounded at N=20"
    # Oldest 5 dropped; newest last; each entry is (monotonic_t, x, y, yaw).
    assert crumbs[0][1] == pytest.approx(5.0)
    assert crumbs[-1][1] == pytest.approx(24.0)
    ts = [c[0] for c in crumbs]
    assert ts == sorted(ts), "monotonic timestamps, oldest -> newest"


def test_recall_returns_newest_breadcrumb_at_least_0_3m_away():
    led = _ledger()
    led.push_breadcrumb((0.0, 0.0, 0.0))
    led.push_breadcrumb((3.0, 0.0, 0.0))
    got = led.recall((5.0, 0.0))
    assert got is not None
    assert (got[0], got[1]) == (pytest.approx(3.0), pytest.approx(0.0))


def test_recall_skips_current_pose_duplicates():
    """THE field trace: '回到刚才的位置' right after arriving — the newest
    crumb IS (about) the current pose; 刚才 must resolve to the next older."""
    led = _ledger()
    led.push_breadcrumb((0.0, 0.0, 0.0))
    led.push_breadcrumb((5.0, 0.0, 0.0))
    # Robot now sits ~where the newest crumb was pushed (within 0.3 m).
    got = led.recall((5.1, 0.05))
    assert got is not None
    assert (got[0], got[1]) == (pytest.approx(0.0), pytest.approx(0.0))


def test_recall_none_when_no_usable_breadcrumb():
    led = _ledger()
    assert led.recall((0.0, 0.0)) is None
    led.push_breadcrumb((0.1, 0.0, 0.0))
    assert led.recall((0.0, 0.0)) is None, (
        "every crumb within 0.3 m of the current pose = nowhere to go back to")


def test_mark_auto_names_are_sequential():
    led = _ledger()
    assert led.mark("", (1.0, 1.0, 0.0)) == "地点1"
    assert led.mark(None, (2.0, 2.0, 0.0)) == "地点2"
    assert set(led.marks) == {"地点1", "地点2"}


def test_mark_stores_named_pose_and_overwrites():
    led = _ledger()
    assert led.mark("充电桩", (1.0, 2.0, 0.5)) == "充电桩"
    assert led.marks["充电桩"] == (1.0, 2.0, 0.5)
    led.mark("充电桩", (3.0, 4.0, 0.0))
    assert led.marks["充电桩"] == (3.0, 4.0, 0.0), "re-marking updates the pose"


def test_resolve_kinds_origin_recall_mark():
    led = _ledger()
    led.ensure_origin((0.0, 0.0, 0.0))
    led.push_breadcrumb((2.0, 0.0, 0.0))
    led.mark("充电桩", (7.0, 7.0, 0.0))
    kind, pose = led.resolve("起点", (5.0, 5.0))
    assert kind == "origin" and (pose[0], pose[1]) == (0.0, 0.0)
    kind, pose = led.resolve("刚才", (5.0, 5.0))
    assert kind == "breadcrumb" and pose[0] == pytest.approx(2.0)
    kind, pose = led.resolve("充电桩", (5.0, 5.0))
    assert kind == "mark" and pose[0] == pytest.approx(7.0)
    kind, pose = led.resolve("食堂", (5.0, 5.0))
    assert kind is None and pose is None


# ---------------------------------------------------------------------------
# mark_place skill — pose from odometry ONLY; honest refusals
# ---------------------------------------------------------------------------


def test_mark_place_stores_current_odometry_pose():
    hw = _PlacesFakeHW(x=1.5, y=-2.0, yaw=0.7)
    result = _mark_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert result.success, result.error_message
    stored = hw.pose_ledger.marks.get("充电桩")
    assert stored is not None
    assert stored[0] == pytest.approx(1.5)
    assert stored[1] == pytest.approx(-2.0)
    assert stored[2] == pytest.approx(0.7)
    assert "充电桩" in str((result.result_data or {}).get("message", ""))


def test_mark_place_pose_is_odometry_not_params():
    """Inv-1: the model can trigger a mark but can NOT author its coordinates
    — x/y in params are ignored, the odometry pose wins."""
    hw = _PlacesFakeHW(x=1.0, y=1.0)
    result = _mark_skill().execute({"name": "假点", "x": 99.0, "y": 99.0},
                                   _ctx(base=hw))
    assert result.success
    stored = hw.pose_ledger.marks["假点"]
    assert stored[0] == pytest.approx(1.0)
    assert stored[1] == pytest.approx(1.0)


def test_mark_place_auto_names_when_unnamed():
    hw = _PlacesFakeHW(x=2.0, y=3.0)
    result = _mark_skill().execute({}, _ctx(base=hw))
    assert result.success
    assert (result.result_data or {}).get("name") == "地点1"
    assert "地点1" in hw.pose_ledger.marks


def test_mark_place_parses_name_from_instruction():
    hw = _PlacesFakeHW(x=2.0, y=3.0)
    result = _mark_skill().execute(
        {}, _ctx(base=hw, instruction="记住这里叫充电桩"))
    assert result.success
    assert "充电桩" in hw.pose_ledger.marks


def test_mark_place_refuses_when_odometry_never_arrived():
    """No (0,0,0) fake marks: a driver that KNOWS odometry never arrived
    (odom_age_s() is None) must refuse — the pose cache is default zeros."""
    hw = _PlacesFakeHW(age=None)
    result = _mark_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert not result.success
    assert hw.pose_ledger.marks == {}, "no mark may be stored without odometry"


def test_mark_place_without_base_fails_honestly():
    result = _mark_skill().execute({"name": "x"}, _ctx(base=None))
    assert not result.success
    assert result.diagnosis_code == "no_base"


def test_mark_place_without_ledger_fails_honestly():
    """A foreign/older base without pose_ledger: honest refusal, no crash."""
    bare = SimpleNamespace(get_position=lambda: [0.0, 0.0, 0.0],
                           get_heading=lambda: 0.0)
    result = _mark_skill().execute({"name": "x"}, _ctx(base=bare))
    assert not result.success


def test_mark_place_captures_origin():
    """A fresh odometry pose seen by ANY place skill captures the origin."""
    hw = _PlacesFakeHW(x=1.0, y=2.0, yaw=0.1)
    _mark_skill().execute({"name": "a"}, _ctx(base=hw))
    assert hw.pose_ledger.origin is not None
    assert hw.pose_ledger.origin[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# goto_place skill — resolve 起点/刚才/named, reset course, drive, verify hint
# ---------------------------------------------------------------------------


def test_goto_place_origin_drives_to_captured_origin():
    hw = _PlacesFakeHW(x=0.0, y=0.0, yaw=0.3)
    hw.pose_ledger.ensure_origin((0.0, 0.0, 0.3))
    hw.set_pose(5.0, 5.0)
    result = _goto_skill().execute({"name": "起点"}, _ctx(base=hw))
    assert result.success, result.error_message
    assert hw.nav_calls[-1] == (pytest.approx(0.0), pytest.approx(0.0))


def test_goto_place_verify_hint_names_the_resolved_target():
    hw = _PlacesFakeHW()
    hw.pose_ledger.ensure_origin((1.25, -2.5, 0.0))
    hw.set_pose(5.0, 5.0)
    result = _goto_skill().execute({"name": "起点"}, _ctx(base=hw))
    hint = str((result.result_data or {}).get("verify_hint", ""))
    assert hint.startswith("at(1.25, -2.50"), hint
    assert "tol=" in hint


def test_goto_place_last_resolves_newest_usable_breadcrumb():
    """回到刚才的位置 right after arriving: the newest crumb is the current
    pose — goto must fall through to the next older crumb (>= 0.3 m away)."""
    hw = _PlacesFakeHW(x=5.0, y=0.0)
    hw.pose_ledger.push_breadcrumb((0.0, 0.0, 0.0))
    hw.pose_ledger.push_breadcrumb((5.0, 0.0, 0.0))  # ~current pose
    result = _goto_skill().execute({"name": "刚才"}, _ctx(base=hw))
    assert result.success, result.error_message
    assert hw.nav_calls[-1] == (pytest.approx(0.0), pytest.approx(0.0))


def test_goto_place_default_is_the_last_breadcrumb():
    hw = _PlacesFakeHW(x=5.0, y=0.0)
    hw.pose_ledger.push_breadcrumb((2.0, 1.0, 0.0))
    result = _goto_skill().execute({}, _ctx(base=hw, instruction="回去"))
    assert result.success, result.error_message
    assert hw.nav_calls[-1] == (pytest.approx(2.0), pytest.approx(1.0))


def test_goto_place_named_mark():
    hw = _PlacesFakeHW(x=0.0, y=0.0)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert result.success
    assert hw.nav_calls[-1] == (pytest.approx(7.0), pytest.approx(-1.0))


def test_goto_place_resolves_mark_from_instruction_text():
    hw = _PlacesFakeHW(x=0.0, y=0.0)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({}, _ctx(base=hw, instruction="回到充电桩"))
    assert result.success, result.error_message
    assert hw.nav_calls[-1] == (pytest.approx(7.0), pytest.approx(-1.0))


def test_goto_place_unknown_name_refuses_and_lists_places():
    hw = _PlacesFakeHW()
    hw.pose_ledger.ensure_origin((0.0, 0.0, 0.0))
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "食堂"}, _ctx(base=hw))
    assert not result.success
    assert hw.nav_calls == [], "an unresolvable place must never drive"
    assert "充电桩" in str(result.error_message), (
        "the refusal must list the places it DOES know")


def test_goto_place_origin_refusal_when_never_captured():
    """No odometry ever seen -> no origin. 回到起点 must refuse honestly,
    never improvise (0, 0) — that is exactly the field-trace failure."""
    hw = _PlacesFakeHW(x=3.0, y=3.0)  # ledger fresh: origin None
    result = _goto_skill().execute({"name": "起点"}, _ctx(base=hw))
    assert not result.success
    assert hw.nav_calls == []


def test_goto_place_recall_refusal_when_no_breadcrumbs():
    hw = _PlacesFakeHW()
    result = _goto_skill().execute({"name": "刚才"}, _ctx(base=hw))
    assert not result.success
    assert hw.nav_calls == []


def test_goto_place_refuses_without_odometry():
    hw = _PlacesFakeHW(age=None)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert not result.success
    assert hw.nav_calls == []


def test_goto_place_estop_latched_fails_fast():
    hw = _PlacesFakeHW(latched=True)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert not result.success
    assert result.diagnosis_code == "estop_latched"
    assert hw.nav_calls == []


def test_goto_place_resets_course_intent_first():
    """goto_place is FREE navigation — the relative-plan course is over."""
    hw = _PlacesFakeHW(x=0.0, y=0.0)
    hw.course_tracker.ensure(0.7)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert result.success
    assert hw.course_tracker.course_yaw is None


def test_goto_place_pushes_departure_breadcrumb():
    """Leaving for a place is itself a motion command start — the CURRENT
    pose becomes a crumb, so '回去' after a goto returns where you left."""
    hw = _PlacesFakeHW(x=5.0, y=5.0)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert result.success
    crumbs = hw.pose_ledger.breadcrumbs
    assert crumbs, "goto must record the departure pose"
    assert crumbs[-1][1] == pytest.approx(5.0)
    assert crumbs[-1][2] == pytest.approx(5.0)


def test_goto_place_honest_failure_when_navigation_fails():
    hw = _PlacesFakeHW(moves=False)
    hw.pose_ledger.mark("充电桩", (7.0, -1.0, 0.0))
    result = _goto_skill().execute({"name": "充电桩"}, _ctx(base=hw))
    assert not result.success
    assert "充电桩" in str(result.error_message) or "7.0" in str(
        result.error_message)


# ---------------------------------------------------------------------------
# Motion skills record departures — origin + breadcrumbs at command start
# ---------------------------------------------------------------------------


def test_navigate_records_origin_and_departure_breadcrumb():
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    hw = _PlacesFakeHW(x=1.0, y=2.0, yaw=0.1)
    r = RealNavigateSkill().execute({"x": 5.0, "y": 5.0}, _ctx(base=hw))
    assert r.success
    assert hw.pose_ledger.origin is not None
    assert hw.pose_ledger.origin[0] == pytest.approx(1.0)
    crumbs = hw.pose_ledger.breadcrumbs
    assert crumbs and crumbs[-1][1] == pytest.approx(1.0)
    assert crumbs[-1][2] == pytest.approx(2.0)


def test_move_relative_records_departure_breadcrumb():
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    hw = _PlacesFakeHW(x=3.0, y=0.0, yaw=0.0)
    r = RealMoveRelativeSkill().execute(
        {"direction": "forward", "distance": 2.0}, _ctx(base=hw))
    assert r.success
    crumbs = hw.pose_ledger.breadcrumbs
    assert crumbs and crumbs[-1][1] == pytest.approx(3.0)


def test_turn_records_departure_breadcrumb():
    from zeno.vcli.worlds.go2w_real_turn_skills import RealTurnSkill

    hw = _PlacesFakeHW(x=2.0, y=2.0, yaw=0.0)
    r = RealTurnSkill().execute({"direction": "left", "degrees": 90},
                                _ctx(base=hw))
    assert r.success
    crumbs = hw.pose_ledger.breadcrumbs
    assert crumbs and crumbs[-1][1] == pytest.approx(2.0)


def test_no_breadcrumb_when_guard_latched():
    """A latched guard eats the command before motion starts — no crumb."""
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    hw = _PlacesFakeHW(latched=True)
    RealNavigateSkill().execute({"x": 5.0, "y": 5.0}, _ctx(base=hw))
    assert hw.pose_ledger.breadcrumbs == ()


def test_no_origin_or_breadcrumb_without_odometry():
    """Odometry never arrived: the (0,0,0) default is NOT a pose — neither
    origin nor breadcrumbs may be fabricated from it."""
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    hw = _PlacesFakeHW(age=None)
    RealNavigateSkill().execute({"x": 5.0, "y": 5.0}, _ctx(base=hw))
    assert hw.pose_ledger.origin is None
    assert hw.pose_ledger.breadcrumbs == ()


def test_motion_skills_without_ledger_keep_todays_behavior():
    """Foreign/older base without pose_ledger: byte-identical motion, no crash
    (additive, backward-compatible — same doctrine as the course seam)."""
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    class _Bare:
        estop_latched = False

        def __init__(self):
            self.nav_calls = []

        def get_position(self):
            return [0.0, 0.0, 0.0]

        def get_heading(self):
            return 0.0

        def navigate_to(self, x, y, timeout=120.0):
            self.nav_calls.append((x, y))
            return True

    hw = _Bare()
    assert RealNavigateSkill().execute({"x": 1.0, "y": 1.0},
                                       _ctx(base=hw)).success
    assert hw.nav_calls == [(1.0, 1.0)]


# ---------------------------------------------------------------------------
# where enrichment — origin distance+bearing, course+drift, marked names
# ---------------------------------------------------------------------------


def _where_skill():
    from zeno.vcli.worlds.go2w_real_ops_skills import RealWhereSkill

    return RealWhereSkill()


def test_where_reports_origin_distance_and_bearing():
    hw = _PlacesFakeHW(x=3.0, y=4.0, yaw=0.0)
    hw.pose_ledger.ensure_origin((0.0, 0.0, 0.0))
    result = _where_skill().execute({}, _ctx(base=hw))
    assert result.success
    data = result.result_data or {}
    assert data.get("origin_distance_m") == pytest.approx(5.0, abs=0.01)
    assert data.get("origin_bearing_deg") == pytest.approx(
        math.degrees(math.atan2(4.0, 3.0)), abs=0.2)


def test_where_captures_origin_on_first_fresh_pose():
    hw = _PlacesFakeHW(x=1.0, y=2.0, yaw=0.3)
    result = _where_skill().execute({}, _ctx(base=hw))
    assert result.success
    assert hw.pose_ledger.origin is not None
    assert hw.pose_ledger.origin[0] == pytest.approx(1.0)


def test_where_reports_course_and_drift_when_set():
    hw = _PlacesFakeHW(x=0.0, y=0.0, yaw=math.radians(10.0))
    hw.course_tracker.ensure(0.0)
    result = _where_skill().execute({}, _ctx(base=hw))
    data = result.result_data or {}
    assert data.get("course_deg") == pytest.approx(0.0, abs=0.1)
    assert data.get("course_drift_deg") == pytest.approx(10.0, abs=0.2)


def test_where_omits_course_when_unset():
    hw = _PlacesFakeHW()
    data = _where_skill().execute({}, _ctx(base=hw)).result_data or {}
    assert "course_deg" not in data


def test_where_lists_marked_place_names():
    hw = _PlacesFakeHW()
    hw.pose_ledger.mark("充电桩", (1.0, 1.0, 0.0))
    hw.pose_ledger.mark("门口", (2.0, 2.0, 0.0))
    data = _where_skill().execute({}, _ctx(base=hw)).result_data or {}
    assert set(data.get("marked_places") or []) == {"充电桩", "门口"}


def test_where_still_refuses_without_odometry():
    """The honest no-odometry refusal is UNCHANGED by the enrichment — and no
    origin may be captured from the default-zeros cache."""
    hw = _PlacesFakeHW(age=None)
    result = _where_skill().execute({}, _ctx(base=hw))
    assert not result.success
    assert hw.pose_ledger.origin is None


def test_where_without_ledger_keeps_todays_shape():
    class _Pose:
        def get_position(self):
            return (1.5, -2.0, 0.0)

        def get_heading(self):
            return 0.7

        def odom_age_s(self):
            return 0.4

    result = _where_skill().execute({}, _ctx(base=_Pose()))
    assert result.success
    data = result.result_data or {}
    assert data.get("x") == pytest.approx(1.5)
    assert "origin_distance_m" not in data


# ---------------------------------------------------------------------------
# Wiring — embodiment seam, skills registered, vocab, few-shots, card
# ---------------------------------------------------------------------------


def _world():
    from zeno.vcli.worlds import resolve_world_named

    return resolve_world_named("go2w_real")


def test_embodiment_rides_pose_ledger_on_driver_and_services():
    from zeno.vcli.worlds.go2w_real_places import PoseLedger

    emb = _world().build_embodiment()
    ledger = getattr(emb._base, "pose_ledger", None)
    assert isinstance(ledger, PoseLedger)
    assert emb._build_context().services.get("places") is ledger, (
        "ONE ledger object on both seams — services and the driver ride")
    assert ledger.origin is None and ledger.breadcrumbs == ()


def test_place_skills_registered_in_embodiment():
    emb = _world().build_embodiment()
    skills = set(emb._skill_registry.list_skills())
    assert "mark_place" in skills
    assert "goto_place" in skills


def test_vocab_teaches_place_strategies():
    vocab = _world().decompose_vocab()
    assert "mark_place_skill" in vocab.strategies
    assert "goto_place_skill" in vocab.strategies
    assert "mark_place_skill" in vocab.strategy_params_help
    assert "goto_place_skill" in vocab.strategy_params_help
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)


def _task_segment(text: str, marker: str) -> str:
    assert marker in text, f"few-shot {marker!r} missing from the vocab"
    after = text.split(marker, 1)[1]
    nxt = after.find("Task:")
    return after[: nxt if nxt >= 0 else len(after)]


def test_vocab_fewshot_goto_origin_is_single_goto_place_step():
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES as ex

    seg = _task_segment(ex, 'Task: "回到起点"')
    assert "goto_place_skill" in seg
    assert seg.count('"strategy"') == 1, "回到起点 is ONE goto_place step"
    assert '"name": "起点"' in seg
    assert "bringup_skill" not in seg


def test_vocab_fewshot_mark_place_carries_the_name():
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES as ex

    seg = _task_segment(ex, 'Task: "记住这里叫充电桩"')
    assert "mark_place_skill" in seg
    assert seg.count('"strategy"') == 1
    assert '"name": "充电桩"' in seg


def test_examples_budget_holds():
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES as ex

    assert len(ex) <= 6000, "REAL_DECOMPOSE_EXAMPLES over the ~6000 budget"


def test_capability_md_documents_global_awareness_and_the_limit():
    from pathlib import Path

    import zeno.vcli.worlds.go2w_real as w

    text = Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")
    assert "全局意识" in text
    assert "起点" in text
    assert "刚才" in text
    assert "mark_place" in text and "goto_place" in text
    # The HONEST limitation: places live in the CURRENT SLAM map frame.
    assert "重启导航栈后地点失效" in text, (
        "the card must say places DIE on nav-stack restart (relocalization "
        "is a roadmap item, not a shipped capability)")
