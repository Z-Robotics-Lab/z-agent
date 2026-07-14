# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Route manager ADOPTS a resident far_planner (RED first).

Pre-built-map mode (2026-07-14): nav.sh start <map> now keeps far_planner
RESIDENT (zdog-route unit) so RViz Goalpoint clicks work out of the box. The
agent's route session must ADOPT that resident instead of launching a
duplicate — and must NEVER SIGINT it on stop (not our child: NEVER-KILL-INFRA;
stopping routing just clears the goal).

Pins: resident probe True -> start_route succeeds WITHOUT spawning a child,
state 'resident' (active for goto gating + the /way_point plumbing flag),
survives refresh (no orphan-death misfire), stop_route fires /nav_cancel but
leaves the resident process untouched. Probe errors degrade to the normal
launch path. Hermetic: FakePopenFactory, ROS stubs, fake probe.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tests.unit.hardware.test_go2w_hw_explore import FakeHW
from tests.unit.hardware.test_go2w_hw_overlay import FakePopenFactory
from tests.unit.hardware.test_go2w_hw_route import _route_ros_stubs
from zeno.hardware.ros2.go2w_hw_route import Go2WRouteManager, RouteConfig


def _nav_sh(tmp_path: Path) -> str:
    p = tmp_path / "nav.sh"
    p.write_text("#!/usr/bin/env bash\n")
    return str(p)


def _resident_mgr(tmp_path: Path, probe=lambda: True):
    factory = FakePopenFactory()
    cfg = RouteConfig(nav_sh=_nav_sh(tmp_path))
    hw = FakeHW()
    mgr = Go2WRouteManager(hw, config=cfg, popen_factory=factory,
                           resident_probe=probe)
    return mgr, hw, factory


def test_resident_start_adopts_without_launching(tmp_path):
    mgr, hw, factory = _resident_mgr(tmp_path)
    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, msg = mgr.start_route()
    assert ok is True, msg
    assert factory.calls == [], "resident far_planner must NOT be duplicated"
    assert mgr.state() == "resident"
    assert mgr.is_active() is True
    assert "常驻" in msg or "resident" in msg.lower()


def test_resident_sets_waypoint_plumbing_flag(tmp_path):
    mgr, hw, _factory = _resident_mgr(tmp_path)
    with patch.dict("sys.modules", _route_ros_stubs()):
        mgr.start_route()
    assert getattr(hw, "route_overlay_active", False) is True


def test_resident_survives_refresh_no_orphan_misfire(tmp_path):
    """No child exists — orphan detection must not declare the session dead."""
    mgr, hw, _factory = _resident_mgr(tmp_path)
    with patch.dict("sys.modules", _route_ros_stubs()):
        mgr.start_route()
        for _ in range(3):
            assert mgr.state() == "resident"
    assert not hw.nav_cancel.called, "no orphan cancel for a resident session"


def test_resident_stop_clears_goal_but_never_kills(tmp_path):
    mgr, hw, factory = _resident_mgr(tmp_path)
    with patch.dict("sys.modules", _route_ros_stubs()):
        mgr.start_route()
        ok, msg = mgr.stop_route()
    assert ok is True
    assert factory.calls == [], "still no child — nothing may be signalled"
    assert hw.nav_cancel.called, "stopping a route session clears the goal"
    assert mgr.state() == "stopped"
    assert getattr(hw, "route_overlay_active", True) is False
    assert "常驻" in msg or "resident" in msg.lower()


def test_probe_error_degrades_to_normal_launch(tmp_path):
    def _boom() -> bool:
        raise RuntimeError("pgrep unavailable")

    mgr, hw, factory = _resident_mgr(tmp_path, probe=_boom)
    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, _msg = mgr.start_route()
    assert ok is True
    assert factory.calls, "probe failure must fall back to launching our own"
    assert mgr.state() == "launching"


def test_probe_false_launches_own_overlay(tmp_path):
    mgr, hw, factory = _resident_mgr(tmp_path, probe=lambda: False)
    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, _msg = mgr.start_route()
    assert ok is True
    assert factory.calls, "no resident -> launch our own overlay as before"
