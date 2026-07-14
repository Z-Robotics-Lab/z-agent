# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WRouteManager — far_planner route mode over nav.sh (v2 route feature).

Pure-unit: the overlay child is a FakeProc behind an injected Popen factory,
the hardware driver is a duck-typed fake, and the ROS message modules are
sys.modules stubs — nothing here touches rclpy, nav.sh, or the real robot
(same fixtures as the explore manager, per the seam contract).

Ground truth is the HONEST ROUTE ORACLE (Inv-1: no /gt on hardware):

* the goal goes to far_planner on ``/goal_point`` (geometry_msgs/PointStamped,
  frame 'map' — source-verified: far_planner.cpp WaypointCallBack subscribes
  '/goal_point' and its world_frame default is 'map'); far_planner plans a
  GLOBAL route and republishes to /way_point itself, so route mode must NOT
  publish /way_point;
* arrival is graded on ``/state_estimation`` odometry proximity to the goal
  (the pose the local planner estimates — the actor cannot forge it), the same
  oracle navigate_to uses; far_planner's OWN ``/far_reach_goal_status`` Bool is
  recorded as the planner's view but never the sole arrival authority;
* the same OverlayLauncher + SIGINT-only teardown + guarded-resume + orphan
  detection as the explore manager (reused, not reimplemented).

State machine: idle -> launching -> active -> stopped, with orphan detection
(child died unexpectedly => stopped + reason) and stop semantics that never
release an operator's E-stop as a side effect.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw_explore import (
    FakeHW,
    _bool_msg,
    _odom_msg,
    _ros_module_stubs,
)
from tests.unit.hardware.test_go2w_hw_overlay import FakePopenFactory, FakeProc


def _route_ros_stubs() -> dict[str, Any]:
    """Explore's ROS module stubs + geometry_msgs (route publishes PointStamped)."""
    stubs = _ros_module_stubs()
    stubs["geometry_msgs"] = MagicMock()
    stubs["geometry_msgs.msg"] = MagicMock()
    return stubs


# ---------------------------------------------------------------------------
# Fixtures — a manager wired to a fake hw + fake child (mirrors _mgr/_started)
# ---------------------------------------------------------------------------


def _rmgr(tmp_path: Path, hw: FakeHW | None = None, proc: FakeProc | None = None):
    """Build a route manager wired to a fake hw + fake child; (mgr, hw, factory)."""
    from zeno.hardware.ros2.go2w_hw_route import Go2WRouteManager, RouteConfig

    nav = tmp_path / "nav.sh"
    nav.write_text("#!/usr/bin/env bash\n")
    factory = FakePopenFactory(proc)
    hw = hw if hw is not None else FakeHW()
    cfg = RouteConfig(nav_sh=str(nav), stop_grace_s=0.01)
    # resident probe pinned False: unit tests must never adopt a REAL
    # far_planner running on this host (map mode keeps one resident).
    mgr = Go2WRouteManager(hw, config=cfg, popen_factory=factory,
                           resident_probe=lambda: False)
    return mgr, hw, factory


def _rstarted(tmp_path: Path, hw: FakeHW | None = None, proc: FakeProc | None = None):
    """A route manager already launched (inside the ROS stubs)."""
    mgr, hw, factory = _rmgr(tmp_path, hw=hw, proc=proc)
    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, msg = mgr.start_route()
    assert ok is True, msg
    return mgr, hw, factory


def _route_sub_callback(hw: FakeHW, topic: str):
    """Extract the subscription callback the manager registered for *topic*."""
    for call in hw._node.create_subscription.call_args_list:
        if call.args[1] == topic:
            return call.args[2]
    raise AssertionError(f"no subscription created for {topic}")


def _last_goal_msg(hw: FakeHW) -> Any:
    """The last message the manager published on its /goal_point publisher."""
    pub = hw._node.create_publisher.return_value
    assert pub.publish.called, "no /goal_point publish happened"
    return pub.publish.call_args[0][0]


# ---------------------------------------------------------------------------
# Import + construction — offline-safe, no ROS env
# ---------------------------------------------------------------------------


def test_module_imports_and_constructs_without_ros() -> None:
    from zeno.hardware.ros2.go2w_hw_route import Go2WRouteManager

    mgr = Go2WRouteManager(None)  # no hardware at all — still constructible
    assert mgr.state() == "idle"
    assert mgr.route_reached() is False


def test_goal_topic_is_far_planner_goal_point() -> None:
    """The manager sends goals on the topic far_planner actually subscribes
    (source-verified far_planner.cpp: '/goal_point', geometry_msgs/PointStamped,
    world_frame default 'map'); arrival oracle is /state_estimation odometry;
    far_planner's own status is /far_reach_goal_status."""
    from zeno.hardware.ros2 import go2w_hw_route as mod

    assert mod.Go2WRouteManager.GOAL_TOPIC == "/goal_point"
    assert mod.Go2WRouteManager.GOAL_FRAME == "map"
    assert mod.Go2WRouteManager.ODOM_TOPIC == "/state_estimation"
    assert mod.Go2WRouteManager.REACH_TOPIC == "/far_reach_goal_status"


def test_route_mode_never_publishes_way_point(tmp_path: Path) -> None:
    """far_planner republishes /way_point ITSELF — route mode publishing it too
    would fight the global planner. Behavioural guard: the manager creates its
    goal publisher on /goal_point and NEVER on /way_point (across start + goto)."""
    mgr, hw, _factory = _rstarted(tmp_path)
    on_odom = _route_sub_callback(hw, "/state_estimation")
    on_odom(_odom_msg(0.0, 0.0))
    with patch.dict("sys.modules", _route_ros_stubs()):
        mgr.goto_via_route(1.0, 0.0, timeout=0.0)

    pub_topics = {c.args[1] for c in hw._node.create_publisher.call_args_list}
    assert "/goal_point" in pub_topics
    assert "/way_point" not in pub_topics, "route mode must not publish /way_point"


# ---------------------------------------------------------------------------
# start_route — connected-driver gate, overlay spawn, goal publisher attach
# ---------------------------------------------------------------------------


def test_start_requires_connected_driver_but_tries_to_heal(tmp_path: Path) -> None:
    """A disconnected driver refuses to launch (no goal publisher / blind oracle)
    after one connect() heal attempt; nothing is spawned."""
    hw = FakeHW(connected=False, connect_heals=False)
    mgr, hw, factory = _rmgr(tmp_path, hw=hw)

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, msg = mgr.start_route()

    assert ok is False
    assert hw.connect_calls == 1, "start must attempt a connect() heal first"
    assert not factory.calls, "no overlay may launch without a connected driver"
    assert mgr.state() == "idle"


def test_start_heals_disconnected_driver_then_launches(tmp_path: Path) -> None:
    hw = FakeHW(connected=False, connect_heals=True)
    mgr, hw, factory = _rmgr(tmp_path, hw=hw)

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, _ = mgr.start_route()

    assert ok is True
    assert mgr.state() == "launching"


def test_start_launches_route_overlay_and_attaches(tmp_path: Path) -> None:
    """start_route spawns ``bash nav.sh route`` (far_planner) and wires the
    /goal_point publisher + the odometry/reach oracle subscriptions."""
    mgr, hw, factory = _rstarted(tmp_path)

    argv, _ = factory.calls[0]
    assert argv[2:] == ["route"]
    # goal publisher created on /goal_point
    pub_topics = {c.args[1] for c in hw._node.create_publisher.call_args_list}
    assert "/goal_point" in pub_topics
    # oracle subscriptions: odometry + far_planner's own reach status
    sub_topics = {c.args[1] for c in hw._node.create_subscription.call_args_list}
    assert {"/state_estimation", "/far_reach_goal_status"} <= sub_topics
    st = mgr.status()
    assert st.state == "launching"
    assert st.pid == factory.proc.pid
    assert st.oracle_attached is True


def test_double_start_refused_while_active(tmp_path: Path) -> None:
    mgr, _hw, factory = _rstarted(tmp_path)

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, msg = mgr.start_route()

    assert ok is False
    assert len(factory.calls) == 1


def test_reach_status_false_confirms_active(tmp_path: Path) -> None:
    """far_planner publishes reach=False every cycle while routing: the first one
    is the liveness proof that moves launching -> active."""
    mgr, hw, _factory = _rstarted(tmp_path)
    on_reach = _route_sub_callback(hw, "/far_reach_goal_status")

    on_reach(_bool_msg(False))

    assert mgr.state() == "active"


# ---------------------------------------------------------------------------
# goto_via_route — publish /goal_point (map frame) then odometry-poll arrival
# ---------------------------------------------------------------------------


def test_goto_publishes_goal_point_in_map_frame(tmp_path: Path) -> None:
    """goto_via_route publishes ONE PointStamped on /goal_point in the map frame
    with the requested coordinates — the far_planner goal contract."""
    mgr, hw, _factory = _rstarted(tmp_path)
    on_odom = _route_sub_callback(hw, "/state_estimation")
    on_odom(_odom_msg(0.0, 0.0))  # robot at origin; goal (5, 0) is far away

    # timeout 0 so the poll loop returns immediately (did-not-arrive) — we only
    # assert the goal was published with the right shape here.
    with patch.dict("sys.modules", _route_ros_stubs()):
        mgr.goto_via_route(5.0, 0.0, timeout=0.0)

    goal = _last_goal_msg(hw)
    assert goal.header.frame_id == "map"
    assert goal.point.x == pytest.approx(5.0)
    assert goal.point.y == pytest.approx(0.0)


def test_goto_returns_true_on_odometry_arrival(tmp_path: Path) -> None:
    """Arrival is graded on /state_estimation proximity to the goal (the honest
    oracle), NOT on anything the actor authored."""
    mgr, hw, _factory = _rstarted(tmp_path)
    on_odom = _route_sub_callback(hw, "/state_estimation")
    on_odom(_odom_msg(2.0, 3.0))  # already within tol of the goal

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok = mgr.goto_via_route(2.0, 3.0, timeout=5.0)

    assert ok is True
    assert mgr.route_reached() is True


def test_goto_returns_false_on_timeout_and_cancels(tmp_path: Path) -> None:
    """If the robot never reaches the goal within the timeout, goto reports
    did-not-arrive and clears the latch (/nav_cancel) so far_planner's
    republished waypoint does not keep driving to an abandoned goal."""
    mgr, hw, _factory = _rstarted(tmp_path)
    on_odom = _route_sub_callback(hw, "/state_estimation")
    on_odom(_odom_msg(0.0, 0.0))  # far from the goal, never moves

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok = mgr.goto_via_route(9.0, 9.0, timeout=0.05)

    assert ok is False
    assert hw.nav_cancel.called, "a timed-out route goal must be cancelled"
    assert mgr.route_reached() is False


def test_goto_refused_when_not_active(tmp_path: Path) -> None:
    """goto_via_route without a running route overlay fails loud (no far_planner
    to plan the route) and publishes no goal."""
    mgr, hw, _factory = _rmgr(tmp_path)

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok = mgr.goto_via_route(1.0, 1.0, timeout=1.0)

    assert ok is False
    assert not hw._node.create_publisher.return_value.publish.called


def test_goto_rejects_non_finite_goal(tmp_path: Path) -> None:
    """A NaN/inf goal is rejected at the boundary (E190 defense-in-depth) and
    never reaches far_planner."""
    mgr, hw, _factory = _rstarted(tmp_path)

    with patch.dict("sys.modules", _route_ros_stubs()):
        ok = mgr.goto_via_route(float("nan"), 0.0, timeout=1.0)

    assert ok is False


# ---------------------------------------------------------------------------
# cancel_route — clear the current goal without tearing down the overlay
# ---------------------------------------------------------------------------


def test_cancel_route_clears_goal_but_keeps_overlay(tmp_path: Path) -> None:
    """cancel_route fires /nav_cancel (clears far_planner's republished waypoint)
    and unblocks a pending goto, but leaves the far_planner overlay running so a
    new goal can be sent without a relaunch."""
    mgr, hw, factory = _rstarted(tmp_path)
    on_reach = _route_sub_callback(hw, "/far_reach_goal_status")
    on_reach(_bool_msg(False))  # -> active

    ok, _msg = mgr.cancel_route()

    assert ok is True
    assert hw.nav_cancel.called
    assert mgr.state() == "active", "overlay must stay up after a goal cancel"
    assert factory.proc.signals == [], "cancel must NOT SIGINT the overlay"


# ---------------------------------------------------------------------------
# stop_route — SIGINT our child -> wait -> /nav_cancel -> GUARDED resume
# ---------------------------------------------------------------------------


def test_stop_route_sigint_then_nav_cancel(tmp_path: Path) -> None:
    mgr, hw, factory = _rstarted(tmp_path)

    ok, msg = mgr.stop_route()

    import signal as _sig

    assert ok is True
    assert factory.proc.signals == [_sig.SIGINT]
    assert hw.nav_cancel.called, "stop must clear the waypoint far_planner latched"
    assert mgr.state() == "stopped"
    assert "request" in mgr.status().reason.lower()
    assert not hw.estop_release.called, "default stop must not touch the E-stop latch"


def test_stop_route_resume_is_guarded_by_estop_latch(tmp_path: Path) -> None:
    """resume=True must NOT release the latches when an E-stop is latched — an
    operator's E-stop may never be undone as a side effect of stopping routing."""
    hw = FakeHW()
    hw.estop_latched = True
    mgr, hw, _factory = _rstarted(tmp_path, hw=hw)

    ok, msg = mgr.stop_route(resume=True)

    assert ok is True
    assert not hw.estop_release.called
    assert "estop" in msg.lower() or "e-stop" in msg.lower()


def test_stop_route_resume_when_not_estopped(tmp_path: Path) -> None:
    mgr, hw, _factory = _rstarted(tmp_path)

    ok, _msg = mgr.stop_route(resume=True)

    assert ok is True
    assert hw.estop_release.called


def test_stop_when_idle_is_clean_noop(tmp_path: Path) -> None:
    mgr, hw, _factory = _rmgr(tmp_path)

    ok, _msg = mgr.stop_route()

    assert ok is True
    assert not hw.nav_cancel.called


def test_stop_sigint_timeout_reports_honest_failure(tmp_path: Path) -> None:
    """A SIGINT-deaf child: stop reports failure, still fires /nav_cancel, and the
    state does NOT lie 'stopped' while the child is alive (NEVER-KILL-INFRA)."""
    proc = FakeProc(exits_on_sigint=None)
    mgr, hw, _factory = _rstarted(tmp_path, proc=proc)

    ok, msg = mgr.stop_route()

    assert ok is False
    assert "still running" in msg.lower() or "pid" in msg.lower()
    assert hw.nav_cancel.called
    assert mgr.state() != "stopped"
    assert mgr.is_active is True


# ---------------------------------------------------------------------------
# Orphan detection — the child dying is a state transition, not a mystery
# ---------------------------------------------------------------------------


def test_child_unexpected_death_flags_stopped_with_reason(tmp_path: Path) -> None:
    mgr, _hw, factory = _rstarted(tmp_path)

    factory.proc.die(1)  # e.g. nav.sh require_stack failed inside the overlay

    assert mgr.state() == "stopped"
    st = mgr.status()
    assert "unexpected" in st.reason.lower()
    assert "1" in st.reason


def test_orphan_death_fires_background_nav_cancel(tmp_path: Path) -> None:
    """A dead far_planner leaves its last republished /way_point latched — orphan
    detection fires ONE background /nav_cancel (daemon thread: detection may run
    on the rclpy executor thread where a sync service call cannot complete)."""
    import time

    mgr, hw, factory = _rstarted(tmp_path)

    factory.proc.die(1)
    assert mgr.state() == "stopped"

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and not hw.nav_cancel.called:
        time.sleep(0.01)
    assert hw.nav_cancel.called, "orphan death must clear the latched waypoint"


def test_orphan_death_allows_restart(tmp_path: Path) -> None:
    mgr, _hw, factory = _rstarted(tmp_path)
    factory.proc.die(1)
    assert mgr.state() == "stopped"

    factory.proc = FakeProc(pid=5002)
    with patch.dict("sys.modules", _route_ros_stubs()):
        ok, _ = mgr.start_route()

    assert ok is True
    assert mgr.state() == "launching"
    assert mgr.status().reason == ""


# ---------------------------------------------------------------------------
# route_reached predicate — fail-safe, goal-relative odometry proximity
# ---------------------------------------------------------------------------


def test_route_reached_is_false_before_any_goal(tmp_path: Path) -> None:
    mgr, _hw, _factory = _rstarted(tmp_path)
    assert mgr.route_reached() is False


def test_route_reached_latches_after_arrival(tmp_path: Path) -> None:
    """Once a goto arrives, route_reached() stays True for that goal until a new
    goal is issued (verify reads it after the blocking call returns)."""
    mgr, hw, _factory = _rstarted(tmp_path)
    on_odom = _route_sub_callback(hw, "/state_estimation")
    on_odom(_odom_msg(1.0, 1.0))

    with patch.dict("sys.modules", _route_ros_stubs()):
        mgr.goto_via_route(1.0, 1.0, timeout=5.0)

    assert mgr.route_reached() is True
