# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware.rotate — in-place rotation over /teleop_cmd_vel (v2, RED first).

Field trace 2026-07-10 evening: '左转90度' — no rotation capability existed
anywhere in the go2w_real world. ``rotate(delta_yaw_rad, yaw_rate=0.5)`` follows
the walk() cadence template on the SAME wire contract the running nav stack
enforces (none of which the actor authors):

* angular-only Twist on /teleop_cmd_vel, refreshed at 5 Hz — strictly beating
  the robot-side 0.4 s deadman; "stop" is to stop publishing (one final zero);
* duration = |delta| / yaw_rate, with EARLY stop the moment get_heading()
  odometry says the turn is done (wrap-around handled across ±pi);
* the _nav_abort cancel seam: cancel_navigation() unblocks a rotation exactly
  like it unblocks navigate_to (stop skill / Ctrl+C twin);
* estop-latched fail-fast: a driver that knows its own latch is set refuses
  to command motion the guard would silently eat.

ROS-free like test_go2w_hw.py: mocked node via _install_node_for_test, stubbed
ROS modules, deterministic fake clock (no real sleeps).
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw import _FakeClock, _ros_module_stubs


# ---------------------------------------------------------------------------
# Fixture — a mock-wired driver + captured /teleop_cmd_vel frames + fake clock
# ---------------------------------------------------------------------------


@pytest.fixture
def rot_hw(monkeypatch: pytest.MonkeyPatch):
    """(mod, hw, frames, clk): frames snapshot (vx, vy, wz) per publish."""
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
        resp = MagicMock()
        resp.success = True
        future = MagicMock()
        future.result.return_value = resp
        c.call_async.return_value = future
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
        pubs["/teleop_cmd_vel"].publish.side_effect = lambda m: frames.append(
            (m.linear.x, m.linear.y, m.angular.z)
        )
        yield mod, hw, frames, clk


def _motion_frames(frames: list[tuple[float, float, float]]):
    return [f for f in frames if f[2] != pytest.approx(0.0)]


# ---------------------------------------------------------------------------
# Cadence + shape — angular-only, 5 Hz, final zero
# ---------------------------------------------------------------------------


def test_rotate_publishes_angular_only_twists_at_5hz_then_zero(rot_hw) -> None:
    """90° left @0.5 rad/s = pi/2/0.5 s of frames every 0.2 s, all angular-only
    (linear strictly zero — IN-PLACE), positive wz (left = CCW = +yaw), and the
    last frame is a zero stop (then silence — the deadman is the real stop)."""
    mod, hw, frames, _clk = rot_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.rotate(math.pi / 2, yaw_rate=0.5)
    assert ok is True
    motion = _motion_frames(frames)
    # duration ≈ 3.14 s at 5 Hz → ~15 motion frames (>=4 Hz cadence floor).
    assert len(motion) >= 12, f"expected >=12 refreshes (5 Hz), got {len(motion)}"
    for vx, vy, wz in motion:
        assert vx == pytest.approx(0.0), "rotation must be IN PLACE (no vx)"
        assert vy == pytest.approx(0.0), "rotation must be IN PLACE (no vy)"
        assert wz == pytest.approx(0.5), "left turn commands +yaw at the given rate"
    assert frames[-1] == (pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0))


def test_rotate_right_commands_negative_yaw(rot_hw) -> None:
    """A negative delta (right/CW) publishes negative wz at the same |rate|."""
    mod, hw, frames, _clk = rot_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.rotate(-math.pi / 4, yaw_rate=0.5) is True
    motion = _motion_frames(frames)
    assert motion, "right turn must command motion frames"
    for _vx, _vy, wz in motion:
        assert wz == pytest.approx(-0.5)


def test_rotate_duration_is_delta_over_rate(rot_hw) -> None:
    """Open loop (odometry frozen): the command window is |delta|/rate seconds."""
    mod, hw, frames, clk = rot_hw
    t0 = clk.monotonic()
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.rotate(1.0, yaw_rate=0.5)  # 2.0 s
    elapsed = clk.monotonic() - t0
    assert 1.8 <= elapsed <= 2.6, f"command window should be ~2.0s, got {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Odometry tracking — early stop on arrival, wrap-around across ±pi
# ---------------------------------------------------------------------------


def test_rotate_stops_early_on_odometry_arrival_across_pi_wrap(rot_hw) -> None:
    """Start near +pi and turn left through the wrap: heading jumps from ~+pi to
    ~-pi mid-turn. With correct wrap handling the tracked rotation accumulates
    monotonically and rotate() stops EARLY when odometry says 1.0 rad is done —
    here the robot turns 2x faster than commanded (0.2 rad per 5 Hz frame), so
    only ~5 motion frames may be sent instead of the open-loop 10."""
    mod, hw, frames, _clk = rot_hw
    hw._heading = 3.0  # near +pi

    real_publish = frames.append

    def _spin_robot(m: Any) -> None:
        real_publish((m.linear.x, m.linear.y, m.angular.z))
        if m.angular.z != 0.0:  # each motion frame: robot actually turns 0.2 rad
            h = hw._heading + 0.2
            hw._heading = math.atan2(math.sin(h), math.cos(h))

    # rewire the capture to also advance the fake odometry heading
    hw._teleop_pub.publish.side_effect = _spin_robot
    frames.clear()

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.rotate(1.0, yaw_rate=0.5)
    assert ok is True
    motion = _motion_frames(frames)
    assert len(motion) <= 7, (
        f"odometry says the turn finished after ~5 frames; rotate must stop early "
        f"(wrap-aware tracking), got {len(motion)} motion frames"
    )
    assert frames[-1] == (pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0))


# ---------------------------------------------------------------------------
# Cancel seam + safety fail-fast
# ---------------------------------------------------------------------------


def test_cancel_navigation_unblocks_rotation(rot_hw) -> None:
    """cancel_navigation() (stop skill / Ctrl+C twin) aborts a running rotation:
    rotate returns False and stops commanding after the cancel lands."""
    mod, hw, frames, _clk = rot_hw

    real_publish = frames.append

    def _cancel_after_two(m: Any) -> None:
        real_publish((m.linear.x, m.linear.y, m.angular.z))
        if len(_motion_frames(frames)) == 2:
            hw.cancel_navigation()

    hw._teleop_pub.publish.side_effect = _cancel_after_two
    frames.clear()

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.rotate(math.pi, yaw_rate=0.5)  # would be ~6.3 s open loop
    assert ok is False, "a cancelled rotation must report False (not fake success)"
    motion = _motion_frames(frames)
    assert len(motion) <= 3, f"must stop commanding promptly on cancel, got {len(motion)}"


def test_rotate_fails_fast_when_estop_latched(rot_hw) -> None:
    """A driver-known E-stop latch refuses rotation BEFORE any Twist goes out
    (the guard would silently eat the commands — field trace 2026-07-10)."""
    mod, hw, frames, _clk = rot_hw
    hw._estop_latched = True
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.rotate(math.pi / 2) is False
    assert frames == [], "no /teleop_cmd_vel frame may be published while latched"


def test_rotate_offline_returns_false() -> None:
    """A disconnected driver refuses rotation honestly (False, never raises)."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    hw = Go2WHardware()
    assert hw.rotate(math.pi / 2) is False


def test_rotate_rejects_nonfinite(rot_hw) -> None:
    """NaN/inf delta or rate fails loud at the boundary — no Twist reaches the
    topic (ensure_finite guard family)."""
    mod, hw, frames, _clk = rot_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        with pytest.raises(ValueError):
            hw.rotate(float("nan"))
        with pytest.raises(ValueError):
            hw.rotate(1.0, yaw_rate=float("inf"))
        with pytest.raises(ValueError):
            hw.rotate(1.0, yaw_rate=0.0)  # unbounded duration
    assert frames == []


def test_rotate_default_yaw_rate_is_0_5() -> None:
    """Task contract: rotate(delta_yaw_rad, yaw_rate=0.5)."""
    import inspect

    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    sig = inspect.signature(Go2WHardware.rotate)
    assert sig.parameters["yaw_rate"].default == pytest.approx(0.5)
