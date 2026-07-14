# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""goto_place precise docking — skill wiring over driver.dock_to.

CEO 2026-07-14: manipulation stations need coarse-nav + fine-servo arrival.
Pins: precise=True (or 精准/进站 in the utterance) runs base.dock_to(x, y,
yaw=<the place's RECORDED heading>) after coarse arrival; verify tightens to
at(..., tol=0.15); dock failure is an honest partial; bases without dock_to
keep coarse behavior byte-identical. Hermetic: fake driver, no ROS.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _DockFakeHW:
    def __init__(self, docks: bool = True) -> None:
        from zeno.vcli.worlds.go2w_real_course import CourseTracker

        self.estop_latched = False
        self._pos = [0.0, 0.0, 0.0]
        self._yaw = 0.0
        self._docks = docks
        self.nav_calls: list[tuple[float, float]] = []
        self.dock_calls: list[tuple[float, float, object]] = []
        self.course_tracker = CourseTracker()

    def get_position(self):
        return list(self._pos)

    def get_heading(self):
        return self._yaw

    def odom_age_s(self):
        return 0.2

    def navigate_to(self, x, y, timeout=120.0):
        self.nav_calls.append((x, y))
        self._pos = [x + 0.25, y - 0.2, 0.0]  # coarse arrival: ~0.3m off
        return True

    def dock_to(self, x, y, yaw=None, timeout=30.0):
        self.dock_calls.append((x, y, yaw))
        if self._docks:
            self._pos = [x, y, 0.0]
            if yaw is not None:
                self._yaw = yaw
        return self._docks


class _NoDockFakeHW(_DockFakeHW):
    dock_to = property()  # attribute exists but is not callable


def _ctx(base, services=None, instruction=""):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


def _goto():
    from zeno.vcli.worlds.go2w_real_places import RealGotoPlaceSkill

    return RealGotoPlaceSkill()


def _mark(base, name, x, y, yaw):
    base.pose_ledger = None  # replaced below
    from zeno.vcli.worlds.go2w_real_places import PoseLedger

    ledger = PoseLedger()
    ledger.ensure_origin((0.0, 0.0, 0.0))
    ledger.mark(name, (x, y, yaw))
    base.pose_ledger = ledger
    return ledger


def test_precise_goto_docks_with_recorded_heading():
    hw = _DockFakeHW()
    _mark(hw, "抓取台", 2.0, 1.0, 0.7)
    result = _goto().execute({"name": "抓取台", "precise": True}, _ctx(hw))
    assert result.success, result.error_message
    assert hw.dock_calls == [(2.0, 1.0, pytest.approx(0.7))]
    assert "tol=0.15" in str(result.result_data)


def test_precise_parsed_from_utterance():
    hw = _DockFakeHW()
    _mark(hw, "抓取台", 2.0, 1.0, 0.7)
    result = _goto().execute({"name": "抓取台"},
                             _ctx(hw, instruction="精准进站到抓取台"))
    assert result.success
    assert hw.dock_calls, "精准/进站 in the utterance must trigger docking"


def test_default_goto_stays_coarse():
    hw = _DockFakeHW()
    _mark(hw, "抓取台", 2.0, 1.0, 0.7)
    result = _goto().execute({"name": "抓取台"}, _ctx(hw))
    assert result.success
    assert hw.dock_calls == [], "no precise flag -> coarse only"
    assert "tol=1.0" in str(result.result_data)


def test_dock_failure_is_honest_partial():
    hw = _DockFakeHW(docks=False)
    _mark(hw, "抓取台", 2.0, 1.0, 0.7)
    result = _goto().execute({"name": "抓取台", "precise": True}, _ctx(hw))
    assert not result.success
    assert "精准进站失败" in (result.error_message or "")


def test_base_without_dock_keeps_coarse_behavior():
    hw = _NoDockFakeHW()
    _mark(hw, "抓取台", 2.0, 1.0, 0.7)
    result = _goto().execute({"name": "抓取台", "precise": True}, _ctx(hw))
    assert result.success, "missing dock seam must not break coarse goto"
    assert hw.nav_calls
