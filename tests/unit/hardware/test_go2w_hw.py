# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware — real-robot ROS2 driver seam tests (P5.4, CEO 2026-07-10).

Pure-unit and ROS-free: rclpy and every ROS message/service type are mocked in
``sys.modules`` exactly like the existing nav_client / isaac_sim_proxy seam tests,
so this file runs on a host with no sourced ROS env. Ground truth here is the
WIRE CONTRACT the running nav stack consumes, none of which the actor authors:

* /way_point is a geometry_msgs/PointStamped, frame_id 'map', xy passthrough,
  published ONCE per navigate_to (latched pursuit) — and the finite guard rejects
  a NaN goal before it can reach the topic;
* /teleop_cmd_vel is a geometry_msgs/Twist, clamped to the 0.6 m/s guard, and
  walk() refreshes it at >=4 Hz so the 0.4 s deadman never trips mid-stride;
* the std_srvs/Trigger services (/standup /liedown /estop /estop_release /manual
  /nav_cancel) map one-to-one to the driver's stance/safety helpers;
* navigate_to grades arrival on /state_estimation odometry (the real oracle,
  Inv-1) and cancels the latched waypoint via /nav_cancel on timeout/stall.

The module MUST import with no rclpy installed (lazy-import contract), so the
first test imports it bare.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Lazy-import contract — module loads with no ROS env
# ---------------------------------------------------------------------------


def test_module_imports_without_rclpy() -> None:
    """Importing the driver must not require rclpy (env comes from sourced ROS)."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    assert Go2WHardware is not None


def test_construct_without_connect_is_offline() -> None:
    """A fresh driver (no connect) is not connected and every ROS call no-ops/False."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    hw = Go2WHardware()
    assert hw.name == "go2w_hw"
    assert hw.is_connected is False
    # navigate_to with no node returns False (cannot drive), never raises.
    assert hw.navigate_to(1.0, 2.0) is False
    # stop() must be safe on a disconnected driver.
    hw.stop()
    # Trigger helpers degrade to False (service unavailable), never raise.
    assert hw.standup() is False
    assert hw.estop() is False


# ---------------------------------------------------------------------------
# Fixtures — a fully mocked rclpy node + message/service modules
# ---------------------------------------------------------------------------


def _ros_module_stubs() -> dict[str, Any]:
    """sys.modules stubs for the ROS packages the driver lazily imports."""
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
    """Return a Go2WHardware wired to a MagicMock node via a stubbed connect().

    The shared ROS2 runtime is patched to a no-op so add_node never touches a real
    executor; the node's create_publisher / create_client return fresh mocks the
    tests introspect.
    """
    from zeno.hardware.ros2 import go2w_hw as mod

    node = MagicMock()
    node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock()

    pubs: dict[str, MagicMock] = {}
    clients: dict[str, MagicMock] = {}

    def _create_publisher(_msg_type: Any, topic: str, *_a: Any, **_k: Any) -> MagicMock:
        p = MagicMock(name=f"pub{topic}")
        pubs[topic] = p
        return p

    def _create_client(_srv_type: Any, name: str, *_a: Any, **_k: Any) -> MagicMock:
        c = MagicMock(name=f"cli{name}")
        c.wait_for_service.return_value = True
        # A Trigger response: success True.
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

    # Patch the shared runtime so add_node/remove_node are inert.
    fake_runtime = MagicMock()
    monkeypatch.setattr(mod, "get_ros2_runtime", lambda: fake_runtime)

    # Patch rclpy so connect()'s init path is inert, and spin_until_future is instant.
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw = mod.Go2WHardware()
        # Inject the mock node directly through the seam connect() uses, so we do
        # not depend on the real Node constructor.
        hw._install_node_for_test(node)
        yield mod, hw, node, pubs, clients


# ---------------------------------------------------------------------------
# /way_point message shape — frame 'map', xy passthrough, published ONCE
# ---------------------------------------------------------------------------


def test_navigate_publishes_waypoint_once_with_map_frame(connected_hw) -> None:
    """navigate_to publishes exactly ONE /way_point PointStamped in frame 'map'.

    Latched pursuit: the local planner keeps chasing the single waypoint, so the
    driver sends it once (not a re-publish loop). We make odometry report arrival
    on the first poll so the loop exits immediately.
    """
    mod, hw, node, pubs, _clients = connected_hw

    captured: list[Any] = []

    wp_pub = pubs["/way_point"]
    wp_pub.publish.side_effect = lambda msg: captured.append(msg)

    # Report the robot already at the goal so navigate_to returns on first check.
    hw._on_odom(_odom_msg(2.0, 3.0))

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(2.0, 3.0, timeout=1.0, poll_hz=50.0)

    assert ok is True
    assert len(captured) == 1, "waypoint must be published exactly once (latched pursuit)"
    msg = captured[0]
    assert msg.header.frame_id == "map"
    assert msg.point.x == pytest.approx(2.0)
    assert msg.point.y == pytest.approx(3.0)
    assert msg.point.z == pytest.approx(0.0)


def test_navigate_rejects_nonfinite_goal_before_publish(connected_hw) -> None:
    """A NaN/inf goal fails loud at the boundary and never reaches /way_point."""
    mod, hw, node, pubs, _clients = connected_hw
    wp_pub = pubs["/way_point"]

    with patch.dict("sys.modules", _ros_module_stubs()):
        with pytest.raises(ValueError, match="non-finite"):
            hw.navigate_to(float("nan"), 3.0)
        with pytest.raises(ValueError, match="non-finite"):
            hw.navigate_to(1.0, float("inf"))

    assert not wp_pub.publish.called, "no waypoint may be published for a bad goal"


def test_navigate_times_out_and_cancels_via_nav_cancel(connected_hw) -> None:
    """When the robot never arrives, navigate_to returns False and cancels the
    latched waypoint through the /nav_cancel Trigger (so it stops chasing)."""
    mod, hw, node, pubs, clients = connected_hw

    # Odometry stuck far from the goal → never arrives.
    hw._on_odom(_odom_msg(0.0, 0.0))

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(9.0, 9.0, timeout=0.15, poll_hz=50.0)

    assert ok is False
    assert clients["/nav_cancel"].call_async.called, (
        "a timed-out navigate must clear the latched waypoint via /nav_cancel"
    )


def test_navigate_stall_detection_aborts(connected_hw) -> None:
    """If odometry stops making progress for the stall window, navigate_to aborts
    early (returns False) rather than burning the full timeout."""
    mod, hw, node, pubs, clients = connected_hw

    hw._on_odom(_odom_msg(1.0, 1.0))  # far, and it will not move

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(
            9.0, 9.0, timeout=30.0, poll_hz=50.0, stall_timeout=0.1
        )

    assert ok is False


# ---------------------------------------------------------------------------
# /teleop_cmd_vel — clamp to the 0.6 m/s guard, cadence >=4 Hz
# ---------------------------------------------------------------------------


def test_set_velocity_publishes_clamped_twist(connected_hw) -> None:
    """set_velocity clamps |vx|,|vy| to the 0.6 m/s guard and publishes a Twist."""
    mod, hw, node, pubs, _clients = connected_hw
    captured: list[Any] = []
    pubs["/teleop_cmd_vel"].publish.side_effect = lambda m: captured.append(m)

    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.set_velocity(5.0, -5.0, 0.2)  # way over the clamp

    assert len(captured) == 1
    twist = captured[0]
    assert twist.linear.x == pytest.approx(mod.Go2WHardware.MAX_LINEAR_MPS)
    assert twist.linear.y == pytest.approx(-mod.Go2WHardware.MAX_LINEAR_MPS)
    assert twist.angular.z == pytest.approx(0.2)


def test_set_velocity_rejects_nonfinite(connected_hw) -> None:
    """A NaN velocity fails loud before any Twist reaches /teleop_cmd_vel."""
    mod, hw, node, pubs, _clients = connected_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        with pytest.raises(ValueError, match="non-finite"):
            hw.set_velocity(float("nan"), 0.0, 0.0)
    assert not pubs["/teleop_cmd_vel"].publish.called


def test_walk_refreshes_at_at_least_4hz(connected_hw) -> None:
    """walk() keeps /teleop_cmd_vel fresh at >=4 Hz for the duration, then stops.

    The deadman is 0.4 s; publishing slower than 2.5 Hz would let the robot stall
    mid-stride. We drive a fake clock so the loop is deterministic and count how
    many commands land inside a 1.0 s walk — it must be >= 4 (>=4 Hz).
    """
    mod, hw, node, pubs, _clients = connected_hw
    # Record the (vx, vyaw) VALUES at publish time — the stubbed Twist() returns
    # the same MagicMock instance each call, so we must snapshot, not keep refs.
    captured: list[tuple[float, float]] = []
    pubs["/teleop_cmd_vel"].publish.side_effect = (
        lambda m: captured.append((m.linear.x, m.angular.z))
    )

    # Deterministic fake clock: time advances only on sleep().
    clk = _FakeClock()
    monkeypatch_time(mod, clk)

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.walk(vx=0.3, vy=0.0, vyaw=0.0, duration=1.0)

    assert ok is True
    # >= 4 refreshes during the 1 s walk (>=4 Hz cadence contract).
    walking_cmds = [vx for (vx, _yaw) in captured if vx == pytest.approx(0.3)]
    assert len(walking_cmds) >= 4, (
        f"walk must refresh >=4 Hz to beat the 0.4s deadman; got {len(walking_cmds)}"
    )
    # Final command is a zero stop (stop == stop publishing motion, last frame 0).
    assert captured[-1] == (pytest.approx(0.0), pytest.approx(0.0))


def test_cadence_faster_than_deadman() -> None:
    """The refresh period must be strictly shorter than the deadman (static guard)."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    assert Go2WHardware.TELEOP_PERIOD_S < Go2WHardware.DEADMAN_S
    assert Go2WHardware.TELEOP_PERIOD_S <= 0.25  # >= 4 Hz


# ---------------------------------------------------------------------------
# Trigger service mapping — one helper per std_srvs/Trigger service
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, service",
    [
        ("standup", "/standup"),
        ("liedown", "/liedown"),
        ("estop", "/estop"),
        ("estop_release", "/estop_release"),
        ("manual", "/manual"),
        ("nav_cancel", "/nav_cancel"),
    ],
)
def test_trigger_helper_calls_its_service(connected_hw, method: str, service: str) -> None:
    """Each stance/safety helper calls exactly its std_srvs/Trigger service."""
    mod, hw, node, _pubs, clients = connected_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        result = getattr(hw, method)()
    assert result is True, f"{method}() should report the Trigger success"
    assert clients[service].call_async.called, f"{method}() must call {service}"


def test_resume_is_estop_release_alias(connected_hw) -> None:
    """resume() releases both latches — it maps onto /estop_release."""
    mod, hw, node, _pubs, clients = connected_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.resume() is True
    assert clients["/estop_release"].call_async.called


def test_trigger_reports_false_on_service_failure(connected_hw) -> None:
    """A Trigger response with success=False propagates as False (fail honest)."""
    mod, hw, node, _pubs, clients = connected_hw
    resp = MagicMock()
    resp.success = False
    resp.message = "not ready"
    clients["/standup"].call_async.return_value.result.return_value = resp
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.standup() is False


# ---------------------------------------------------------------------------
# State readback — /state_estimation odometry is the pose truth
# ---------------------------------------------------------------------------


def test_odom_callback_updates_position_and_heading(connected_hw) -> None:
    """/state_estimation odometry updates get_position()/get_heading()."""
    mod, hw, _node, _pubs, _clients = connected_hw
    # yaw = pi/2 quaternion (z=sin(pi/4), w=cos(pi/4)).
    import math

    hw._on_odom(_odom_msg(1.5, -2.5, qz=math.sin(math.pi / 4), qw=math.cos(math.pi / 4)))
    px, py, _pz = hw.get_position()
    assert px == pytest.approx(1.5)
    assert py == pytest.approx(-2.5)
    assert hw.get_heading() == pytest.approx(math.pi / 2, abs=1e-6)


def test_get_odometry_returns_typed_snapshot(connected_hw) -> None:
    """get_odometry() returns a zeno.core.types.Odometry dataclass from the cache."""
    from zeno.core.types import Odometry

    mod, hw, _node, _pubs, _clients = connected_hw
    hw._on_odom(_odom_msg(4.0, 5.0))
    odom = hw.get_odometry()
    assert isinstance(odom, Odometry)
    assert odom.x == pytest.approx(4.0)
    assert odom.y == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Test helpers — fake odom message + fake clock
# ---------------------------------------------------------------------------


def _odom_msg(x: float, y: float, qz: float = 0.0, qw: float = 1.0) -> Any:
    """Build a duck-typed nav_msgs/Odometry stand-in the driver's _on_odom reads."""
    msg = MagicMock()
    msg.pose.pose.position.x = x
    msg.pose.pose.position.y = y
    msg.pose.pose.position.z = 0.0
    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = qz
    msg.pose.pose.orientation.w = qw
    msg.twist.twist.linear.x = 0.0
    msg.twist.twist.linear.y = 0.0
    msg.twist.twist.linear.z = 0.0
    msg.twist.twist.angular.z = 0.0
    return msg


class _FakeClock:
    """Deterministic monotonic clock: advances only when sleep() is called."""

    def __init__(self) -> None:
        self._t = 1000.0

    def monotonic(self) -> float:
        return self._t

    def time(self) -> float:
        return self._t

    def sleep(self, dt: float) -> None:
        self._t += float(dt)


def monkeypatch_time(mod: Any, clk: _FakeClock) -> None:
    """Point the driver module's time hooks at the fake clock (no real sleeps)."""
    import pytest as _pt

    mp = _pt.MonkeyPatch()
    mp.setattr(mod.time, "monotonic", clk.monotonic)
    mp.setattr(mod.time, "sleep", clk.sleep)
    mp.setattr(mod.time, "time", clk.time)
