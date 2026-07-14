# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware — operator RViz-goal detection seam (CEO field ask 2026-07-14).

The operator sometimes clicks a goal in RViz while the agent is mid-navigate.
That click publishes a NEW /way_point that OVERWRITES the agent's latched goal,
so the robot obeys the operator while the agent blindly polls its own
(abandoned) goal — timing out / stalling instead of yielding.

This seam makes the driver LISTEN to its own /way_point topic and classify each
frame it sees:

* OWN ECHO — the driver's own _publish_waypoint round-trips back; matched within
  1 s + ~1e-4 coords => ignored (not an external goal).
* ROUTE PLUMBING — far_planner streams /way_point continuously toward its route
  while the route overlay is active (driver.route_overlay_active) => ignored.
* EXTERNAL — anything else is an operator RViz click: stored as external_goal,
  exposed via external_goal_info() (x, y, age_s) and cleared by
  clear_external_goal().

And navigate_to yields honestly: an external goal arriving AFTER the navigate
started STOPS the poll early WITHOUT /nav_cancel (the operator's latched goal
must keep driving the robot) and sets nav_overridden=True.

Hermetic: rclpy + all ROS msg/srv modules are mocked in sys.modules, no ROS env.
"""

from __future__ import annotations

import time as _time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _ros_module_stubs() -> dict[str, Any]:
    return {
        "rclpy": MagicMock(),
        "geometry_msgs": MagicMock(),
        "geometry_msgs.msg": MagicMock(),
        "nav_msgs": MagicMock(),
        "nav_msgs.msg": MagicMock(),
        "std_srvs": MagicMock(),
        "std_srvs.srv": MagicMock(),
    }


@pytest.fixture
def connected_hw(monkeypatch: pytest.MonkeyPatch):
    """A Go2WHardware wired to a MagicMock node (mirrors test_go2w_hw.py)."""
    from zeno.hardware.ros2 import go2w_hw as mod

    node = MagicMock()
    node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock()

    pubs: dict[str, MagicMock] = {}
    clients: dict[str, MagicMock] = {}

    def _create_publisher(_msg_type: Any, topic: str, *_a: Any, **_k: Any):
        p = MagicMock(name=f"pub{topic}")
        pubs[topic] = p
        return p

    def _create_client(_srv_type: Any, name: str, *_a: Any, **_k: Any):
        c = MagicMock(name=f"cli{name}")
        c.wait_for_service.return_value = True
        resp = MagicMock()
        resp.success = True
        resp.message = "ok"
        future = MagicMock()
        future.result.return_value = resp
        c.call_async.return_value = future
        clients[name] = c
        return c

    node.create_publisher.side_effect = _create_publisher
    node.create_client.side_effect = _create_client
    node.create_subscription = MagicMock()

    fake_runtime = MagicMock()
    monkeypatch.setattr(mod, "get_ros2_runtime", lambda: fake_runtime)

    with patch.dict("sys.modules", _ros_module_stubs()):
        hw = mod.Go2WHardware()
        hw._install_node_for_test(node)
        yield mod, hw, node, pubs, clients


def _odom_msg(x: float, y: float) -> Any:
    msg = MagicMock()
    msg.pose.pose.position.x = x
    msg.pose.pose.position.y = y
    msg.pose.pose.position.z = 0.0
    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = 0.0
    msg.pose.pose.orientation.w = 1.0
    msg.twist.twist.linear.x = 0.0
    msg.twist.twist.linear.y = 0.0
    msg.twist.twist.linear.z = 0.0
    msg.twist.twist.angular.z = 0.0
    return msg


def _wp_msg(x: float, y: float) -> Any:
    """A geometry_msgs/PointStamped stand-in the driver's _on_waypoint reads."""
    msg = MagicMock()
    msg.point.x = float(x)
    msg.point.y = float(y)
    msg.point.z = 0.0
    return msg


# ---------------------------------------------------------------------------
# connect() subscribes /way_point
# ---------------------------------------------------------------------------


def test_connect_subscribes_to_waypoint(connected_hw) -> None:
    """The driver must subscribe its own /way_point to see operator clicks."""
    mod, hw, node, _pubs, _clients = connected_hw
    subscribed = [c.args[1] for c in node.create_subscription.call_args_list]
    assert hw.WAYPOINT_TOPIC in subscribed, (
        "connect()/_install_node_for_test must subscribe /way_point")


# ---------------------------------------------------------------------------
# Own-echo suppression
# ---------------------------------------------------------------------------


def test_own_published_waypoint_is_not_external(connected_hw) -> None:
    """The driver's own /way_point round-tripping back is NOT an operator goal."""
    mod, hw, _node, _pubs, _clients = connected_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw._publish_waypoint(2.0, 3.0)
    # The echo arrives immediately with matching coords.
    hw._on_waypoint(_wp_msg(2.0, 3.0))
    assert hw.external_goal_info() is None, "own echo must not register as external"


def test_stale_own_publish_no_longer_shields_echo(connected_hw, monkeypatch) -> None:
    """A frame matching coords but > 1 s after our publish is a fresh EXTERNAL
    click (the operator re-clicked the same spot), not our stale echo."""
    mod, hw, _node, _pubs, _clients = connected_hw
    clk = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "monotonic", lambda: clk["t"])
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw._publish_waypoint(2.0, 3.0)
    clk["t"] += 5.0  # well past the 1 s echo window
    hw._on_waypoint(_wp_msg(2.0, 3.0))
    info = hw.external_goal_info()
    assert info is not None and info[0] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# External detection + info/clear
# ---------------------------------------------------------------------------


def test_external_waypoint_detected_and_reported(connected_hw, monkeypatch) -> None:
    """An unmatched /way_point is an operator RViz goal — stored + aged + clearable."""
    mod, hw, _node, _pubs, _clients = connected_hw
    clk = {"t": 500.0}
    monkeypatch.setattr(mod.time, "monotonic", lambda: clk["t"])

    hw._on_waypoint(_wp_msg(7.0, -1.5))
    clk["t"] += 4.0
    info = hw.external_goal_info()
    assert info is not None
    x, y, age = info
    assert x == pytest.approx(7.0)
    assert y == pytest.approx(-1.5)
    assert age == pytest.approx(4.0, abs=1e-6)

    hw.clear_external_goal()
    assert hw.external_goal_info() is None


def test_external_goal_info_none_before_any_waypoint(connected_hw) -> None:
    mod, hw, _node, _pubs, _clients = connected_hw
    assert hw.external_goal_info() is None


# ---------------------------------------------------------------------------
# Route-plumbing suppression
# ---------------------------------------------------------------------------


def test_route_active_waypoints_are_suppressed(connected_hw) -> None:
    """While the route overlay is active far_planner streams /way_point — those
    are plumbing, never an operator click."""
    mod, hw, _node, _pubs, _clients = connected_hw
    hw.route_overlay_active = True
    hw._on_waypoint(_wp_msg(9.0, 9.0))
    assert hw.external_goal_info() is None, "route plumbing must be suppressed"
    # Once the overlay is down, a click is external again.
    hw.route_overlay_active = False
    hw._on_waypoint(_wp_msg(9.0, 9.0))
    assert hw.external_goal_info() is not None


# ---------------------------------------------------------------------------
# navigate_to yields to a mid-navigate external goal WITHOUT nav_cancel
# ---------------------------------------------------------------------------


def test_navigate_yields_to_external_goal_without_cancel(connected_hw) -> None:
    """An external goal arriving AFTER navigate started stops the poll early,
    returns False, sets nav_overridden — and must NOT /nav_cancel (the
    operator's latched goal must keep driving the robot)."""
    mod, hw, _node, _pubs, clients = connected_hw
    hw._on_odom(_odom_msg(0.0, 0.0))  # far from goal — would never arrive on its own

    def _inject(msg: Any) -> None:
        # The operator clicks mid-navigate on the first teleop-free poll tick.
        hw._on_waypoint(_wp_msg(5.0, 5.0))

    # Fire the operator click on the first sleep of the poll loop.
    original_sleep = mod.time.sleep
    fired = {"done": False}

    def _sleep(dt: float) -> None:
        if not fired["done"]:
            fired["done"] = True
            hw._on_waypoint(_wp_msg(5.0, 5.0))
        original_sleep(dt)

    with patch.dict("sys.modules", _ros_module_stubs()):
        with patch.object(mod.time, "sleep", _sleep):
            ok = hw.navigate_to(9.0, 9.0, timeout=5.0, poll_hz=50.0)

    assert ok is False
    assert hw.nav_overridden is True, "override flag must be set"
    assert not clients["/nav_cancel"].call_async.called, (
        "must NOT nav_cancel — the operator's latched goal keeps driving")
    info = hw.external_goal_info()
    assert info is not None and info[0] == pytest.approx(5.0)


def test_nav_overridden_reset_at_navigate_start(connected_hw) -> None:
    """nav_overridden clears at each navigate start (it describes THIS drive)."""
    mod, hw, _node, _pubs, _clients = connected_hw
    hw.nav_overridden = True
    hw._on_odom(_odom_msg(2.0, 3.0))  # already at goal -> returns True immediately
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(2.0, 3.0, timeout=1.0, poll_hz=50.0)
    assert ok is True
    assert hw.nav_overridden is False


def test_own_goal_echo_during_navigate_does_not_override(connected_hw) -> None:
    """The waypoint navigate_to itself publishes must not be seen as an operator
    override (own-echo suppression protects the poll loop)."""
    mod, hw, _node, _pubs, _clients = connected_hw
    hw._on_odom(_odom_msg(0.0, 0.0))

    def _sleep(dt: float) -> None:
        # Echo of our OWN goal (2,3) arrives — must be ignored.
        hw._on_waypoint(_wp_msg(2.0, 3.0))
        # Force arrival so the loop can exit if it does not override.
        hw._on_odom(_odom_msg(2.0, 3.0))

    with patch.dict("sys.modules", _ros_module_stubs()):
        with patch.object(mod.time, "sleep", _sleep):
            ok = hw.navigate_to(2.0, 3.0, timeout=5.0, poll_hz=50.0)

    assert ok is True
    assert hw.nav_overridden is False
