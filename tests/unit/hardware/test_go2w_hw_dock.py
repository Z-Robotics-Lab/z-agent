# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware.dock_to — manipulation-grade precision servo (RED first).

CEO requirement (2026-07-14): local manipulation needs the base parked at a
station with far better accuracy than the coarse-nav arrival (~0.3-0.4m).
``dock_to(x, y, yaw=None)`` is the fine stage that runs AFTER coarse
navigation: omni body-frame velocity servo on the direct teleop channel,
driven by live map-frame odometry (which the pure-localization prior map
keeps honest), until within DOCK_TOL_M (0.08) and, if requested, the target
heading within DOCK_YAW_TOL_RAD.

Contract pins:
* refuses when the target is farther than DOCK_MAX_RANGE_M (1.0) — docking
  is a last-metre maneuver, coarse nav must come first;
* clears any latched waypoint first (nav_cancel) so the planner cannot
  fight the servo;
* slow: |v| <= 0.15 m/s, |wz| <= 0.4 rad/s; 5 Hz cadence, final zero frame;
* estop fail-fast + _nav_abort cancel seam, exactly like rotate/reverse;
* anchors move_anchor_xy (moved() oracle) AFTER the guards.

ROS-free: mocked node, fake clock, scripted odometry.
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw import _FakeClock, _ros_module_stubs


@pytest.fixture
def dock_hw(monkeypatch: pytest.MonkeyPatch):
    """(mod, hw, frames, clk): frames = (vx, vy, wz) per publish; odometry
    integrates commanded velocity so the servo actually 'moves' the robot."""
    from zeno.hardware.ros2 import go2w_hw as mod

    node = MagicMock()
    node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock()
    pubs: dict[str, MagicMock] = {}

    def _create_publisher(_t: Any, topic: str, *_a: Any, **_k: Any) -> MagicMock:
        p = MagicMock(name=f"pub{topic}")
        pubs[topic] = p
        return p

    def _create_client(_t: Any, name: str, *_a: Any, **_k: Any) -> MagicMock:
        c = MagicMock(name=f"cli{name}")
        c.wait_for_service.return_value = True
        resp = MagicMock(); resp.success = True
        fut = MagicMock(); fut.result.return_value = resp
        c.call_async.return_value = fut
        return c

    node.create_publisher.side_effect = _create_publisher
    node.create_client.side_effect = _create_client
    node.create_subscription = MagicMock()
    monkeypatch.setattr(mod, "get_ros2_runtime", lambda: MagicMock())

    clk = _FakeClock()
    monkeypatch.setattr(mod.time, "monotonic", clk.monotonic)
    monkeypatch.setattr(mod.time, "sleep", clk.sleep)

    with patch.dict("sys.modules", _ros_module_stubs()):
        hw = mod.Go2WHardware()
        hw._install_node_for_test(node)
        frames: list[tuple[float, float, float]] = []

        def _capture(m):
            frames.append((m.linear.x, m.linear.y, m.angular.z))
            # integrate: body->map (yaw) over the 0.2s tick
            yaw = hw._heading
            vx, vy = m.linear.x, m.linear.y
            px, py, pz = hw._position
            hw._position = (px + (vx * math.cos(yaw) - vy * math.sin(yaw)) * 0.2,
                            py + (vx * math.sin(yaw) + vy * math.cos(yaw)) * 0.2, pz)
            hw._heading = math.atan2(math.sin(yaw + m.angular.z * 0.2),
                                     math.cos(yaw + m.angular.z * 0.2))

        pubs["/teleop_cmd_vel"].publish.side_effect = _capture
        yield mod, hw, frames, clk


def _motion(frames):
    return [f for f in frames if any(abs(v) > 1e-9 for v in f)]


# ---------------------------------------------------------------------------
# Convergence — position and heading servo to tolerance
# ---------------------------------------------------------------------------


def test_dock_converges_to_position_tolerance(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.dock_to(0.5, 0.2)
    assert ok is True
    px, py, _ = hw._position
    assert math.hypot(px - 0.5, py - 0.2) <= hw.DOCK_TOL_M + 0.02


def test_dock_servos_heading_when_yaw_given(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0); hw._heading = 0.0
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.dock_to(0.3, 0.0, yaw=0.8)
    assert ok is True
    assert abs(hw._heading - 0.8) <= hw.DOCK_YAW_TOL_RAD + 0.05


def test_dock_uses_omni_lateral_velocity(dock_hw) -> None:
    """A target purely to the LEFT (body frame) servos with vy — the wheeled
    Go2W strafes; docking must not rotate-then-drive."""
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0); hw._heading = 0.0
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.dock_to(0.0, 0.4)
    motion = _motion(frames)
    assert motion, "servo must command motion"
    assert any(abs(vy) > 0.03 for _vx, vy, _wz in motion), "expected lateral (vy) servo"


def test_dock_speed_is_clamped_slow(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.dock_to(0.9, 0.0)
    for vx, vy, wz in _motion(frames):
        assert abs(vx) <= 0.15 + 1e-6 and abs(vy) <= 0.15 + 1e-6
        assert abs(wz) <= 0.4 + 1e-6


def test_dock_final_frame_is_zero(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.dock_to(0.4, 0.0)
    assert frames[-1] == (pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0))


# ---------------------------------------------------------------------------
# Guards — range, estop, cancel, latched waypoint cleared, oracle anchor
# ---------------------------------------------------------------------------


def test_dock_refuses_targets_beyond_max_range(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.dock_to(3.0, 0.0) is False
    assert _motion(frames) == [], "far target must be refused (coarse nav first)"


def test_dock_refuses_when_estop_latched(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._estop_latched = True
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.dock_to(0.3, 0.0) is False
    assert _motion(frames) == []


def test_dock_clears_latched_waypoint_first(dock_hw) -> None:
    """nav_cancel must run before servoing so the planner cannot fight it."""
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    calls = []
    hw.nav_cancel = lambda: calls.append("nav_cancel") or True  # type: ignore
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.dock_to(0.3, 0.0)
    assert calls == ["nav_cancel"]


def test_dock_cancel_navigation_unblocks(dock_hw) -> None:
    mod, hw, frames, clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    n = []

    orig = hw.set_velocity

    def _cancel_after_two(vx, vy, wz):
        n.append(1)
        if len(n) == 2:
            hw._nav_abort.set()
        orig(vx, vy, wz)

    hw.set_velocity = _cancel_after_two  # type: ignore[method-assign]
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.dock_to(0.6, 0.0) is False


def test_dock_anchors_moved_oracle(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    hw._position = (1.0, 2.0, 0.0)
    hw.move_anchor_xy = None
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.dock_to(1.4, 2.0)
    assert hw.move_anchor_xy == (pytest.approx(1.0), pytest.approx(2.0))


def test_dock_rejects_nonfinite(dock_hw) -> None:
    mod, hw, frames, _clk = dock_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        with pytest.raises(ValueError):
            hw.dock_to(float("nan"), 0.0)


def test_dock_timeout_returns_false(dock_hw) -> None:
    """Odometry frozen (fake integration disabled) -> timeout -> False."""
    mod, hw, frames, _clk = dock_hw
    hw._position = (0.0, 0.0, 0.0)
    # re-wire publisher capture WITHOUT integration: robot never moves
    from unittest.mock import MagicMock as MM
    hw._teleop_pub = MM()
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.dock_to(0.5, 0.0, timeout=3.0)
    assert ok is False
