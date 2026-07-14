# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real — operator RViz-goal HONEST YIELD (CEO field ask 2026-07-14, RED).

'我有时候打开cli但还是想rviz手动标记goal point…手动给goal point之后cli那边
也可以显示,并且不会冲突.'

When the operator clicks a goal in RViz mid-navigate, the driver yields to it
(base.nav_overridden=True, external_goal_info() populated). This suite pins the
VCLI-side honest behavior:

* navigate / move_relative / goto_place: on a drive that returns False AND
  base.nav_overridden, the result message says the operator took over (让位 +
  the operator's coords), diagnosis_code='operator_override', and does NOT
  append the stall/latch failure hints (this is not a failure to diagnose).
* live_status_line: a FRESH external goal (age < 180 s) appends the manual-goal
  note so the model sees it every call; a stale/absent one does not.
* absent-attribute bases (older/foreign driver) are unchanged — no crash, no
  spurious override, no status note.

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _OverrideFakeHW:
    """Fake driver exposing the operator-override seam + the navigate contract."""

    def __init__(self, age=0.4, latched=False, overridden=False,
                 ext=None, with_seam=True):
        from zeno.vcli.worlds.go2w_real_course import CourseTracker
        from zeno.vcli.worlds.go2w_real_places import PoseLedger

        self.estop_latched = latched
        self._pos = [0.0, 0.0, 0.0]
        self._yaw = 0.0
        self._age = age
        self.pose_ledger = PoseLedger()
        self.course_tracker = CourseTracker()
        self.nav_calls: list[tuple[float, float]] = []
        if with_seam:
            self.nav_overridden = overridden
            self._ext = ext  # (x, y, age_s) | None

    def get_position(self):
        return list(self._pos)

    def get_heading(self):
        return self._yaw

    def odom_age_s(self):
        return self._age

    def navigate_to(self, x, y, timeout=120.0):
        self.nav_calls.append((float(x), float(y)))
        # The drive "fails" (robot went to the operator's goal instead).
        return False

    def nav_cancel(self):
        return True

    # -- operator-override seam --
    def external_goal_info(self):
        return self._ext


def _ctx(base=None, instruction: str = "", services: dict | None = None):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


# ---------------------------------------------------------------------------
# navigate — honest yield
# ---------------------------------------------------------------------------


def _navigate_skill():
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    return RealNavigateSkill()


def test_navigate_reports_operator_override(monkeypatch, tmp_path):
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "agent.log"))
    try:
        base = _OverrideFakeHW(overridden=True, ext=(5.0, 6.0, 0.5))
        res = _navigate_skill().execute({"x": 1.0, "y": 2.0}, _ctx(base))
        assert res.success is False
        assert res.diagnosis_code == "operator_override"
        msg = res.error_message or ""
        assert "让位" in msg
        assert "5.0" in msg and "6.0" in msg, "operator coords must appear"
        # NOT a failure to diagnose — no stall/latch hint.
        assert "resume_skill" not in msg
        assert "guard" not in msg.lower()
    finally:
        d.set_oplog_path(old)


def test_navigate_normal_failure_still_gets_stall_hint(monkeypatch, tmp_path):
    """A plain non-arrival (no override) keeps the existing stall diagnosis."""
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "agent.log"))
    try:
        base = _OverrideFakeHW(overridden=False, ext=None)
        res = _navigate_skill().execute({"x": 1.0, "y": 2.0}, _ctx(base))
        assert res.success is False
        assert res.diagnosis_code != "operator_override"
        assert "did not arrive" in (res.error_message or "")
    finally:
        d.set_oplog_path(old)


def test_navigate_absent_seam_base_unchanged(monkeypatch, tmp_path):
    """An older driver without the override seam must not crash or fabricate one."""
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "agent.log"))
    try:
        base = _OverrideFakeHW(with_seam=False)
        res = _navigate_skill().execute({"x": 1.0, "y": 2.0}, _ctx(base))
        assert res.success is False
        assert res.diagnosis_code != "operator_override"
    finally:
        d.set_oplog_path(old)


# ---------------------------------------------------------------------------
# move_relative — honest yield
# ---------------------------------------------------------------------------


def _move_relative_skill():
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    return RealMoveRelativeSkill()


def test_move_relative_reports_operator_override(monkeypatch, tmp_path):
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "agent.log"))
    try:
        base = _OverrideFakeHW(overridden=True, ext=(8.0, -2.0, 0.3))
        res = _move_relative_skill().execute(
            {"distance": 2.0, "direction": "forward"}, _ctx(base))
        assert res.success is False
        assert res.diagnosis_code == "operator_override"
        msg = res.error_message or ""
        assert "让位" in msg
        assert "8.0" in msg
        assert "did not reach" not in msg
    finally:
        d.set_oplog_path(old)


# ---------------------------------------------------------------------------
# goto_place — honest yield
# ---------------------------------------------------------------------------


def _goto_place_skill():
    from zeno.vcli.worlds.go2w_real_places import RealGotoPlaceSkill

    return RealGotoPlaceSkill()


def test_goto_place_reports_operator_override(monkeypatch, tmp_path):
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "agent.log"))
    try:
        base = _OverrideFakeHW(overridden=True, ext=(3.0, 4.0, 0.2))
        base.pose_ledger.mark("充电桩", (1.0, 1.0, 0.0))
        res = _goto_place_skill().execute({"name": "充电桩"}, _ctx(base))
        assert res.success is False
        assert res.diagnosis_code == "operator_override"
        msg = res.error_message or ""
        assert "让位" in msg
        assert "3.0" in msg and "4.0" in msg
    finally:
        d.set_oplog_path(old)


# ---------------------------------------------------------------------------
# live_status_line — the manual-goal note
# ---------------------------------------------------------------------------


def _world():
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    return Go2WRealWorld()


def test_status_line_shows_fresh_manual_goal():
    base = _OverrideFakeHW(ext=(7.0, 8.0, 12.0))
    agent = SimpleNamespace(_base=base)
    line = _world().live_status_line(agent)
    assert "RViz" in line and "手动目标" in line
    assert "7.0" in line and "8.0" in line
    assert "12" in line  # age


def test_status_line_omits_stale_manual_goal():
    base = _OverrideFakeHW(ext=(7.0, 8.0, 500.0))  # older than 180 s
    agent = SimpleNamespace(_base=base)
    line = _world().live_status_line(agent)
    assert "手动目标" not in line


def test_status_line_no_manual_goal_when_none():
    base = _OverrideFakeHW(ext=None)
    agent = SimpleNamespace(_base=base)
    line = _world().live_status_line(agent)
    assert "手动目标" not in line


def test_status_line_absent_seam_base_unchanged():
    """A driver without external_goal_info() gets the plain pose line, no crash."""
    base = _OverrideFakeHW(with_seam=False)
    agent = SimpleNamespace(_base=base)
    line = _world().live_status_line(agent)
    assert "手动目标" not in line
    assert "pose x=" in line


# ---------------------------------------------------------------------------
# Capability card teaches operator priority
# ---------------------------------------------------------------------------


def test_capability_card_mentions_operator_rviz_priority():
    from pathlib import Path

    from zeno.vcli.worlds import go2w_real as mod

    text = Path(mod._CAPABILITIES_MD).read_text(encoding="utf-8")
    assert "让位" in text
    assert "at(" in text  # verify the operator's goal arrived
