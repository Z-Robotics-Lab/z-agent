# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware.reverse_blind — the ESCAPE-ONLY straight reverse (RED first).

CEO safety ruling (2026-07-13 evening): the Mid-360 is front-mounted and
pitched 20° down-forward — driving backward is BLIND (no rear obstacle
perception). Reverse is therefore banned as a normal driving mode (the nav
stack goes forward-only) and survives ONLY as a short, slow, operator-visible
escape maneuver on the direct teleop channel:

* linear-only Twist on /teleop_cmd_vel (vx < 0, vy == wz == 0) at 5 Hz —
  strictly beating the 0.4 s deadman; one final zero then silence;
* SLOW: default 0.25 m/s, hard-clamped to <= 0.3 m/s (blind = crawl);
* odometry-tracked EARLY stop the moment displacement covers the request,
  with an open-loop deadline cap (distance/speed * 1.6) if odometry freezes;
* the _nav_abort cancel seam (stop skill / Ctrl+C twin) and estop-latched
  fail-fast, exactly like rotate();
* anchors move_anchor_xy so the moved() oracle grades the escape honestly.

ROS-free like test_go2w_hw_rotate.py: mocked node, stubbed ROS modules,
deterministic fake clock.
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw import _FakeClock, _ros_module_stubs


@pytest.fixture
def rev_hw(monkeypatch: pytest.MonkeyPatch):
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


def _motion(frames: list[tuple[float, float, float]]):
    return [f for f in frames if f != (pytest.approx(0.0),) * 3 and f[0] != 0.0]


# ---------------------------------------------------------------------------
# Cadence + shape — linear-only, negative, slow, final zero
# ---------------------------------------------------------------------------


def test_reverse_blind_publishes_negative_vx_only_at_5hz_then_zero(rev_hw) -> None:
    """1 m @0.25 m/s = ~4 s of frames every 0.2 s, all straight-reverse
    (vy and wz strictly zero), vx == -0.25, and a final zero stop frame."""
    mod, hw, frames, _clk = rev_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.reverse_blind(1.0)
    assert ok is True
    motion = _motion(frames)
    assert len(motion) >= 12, f"expected >=12 refreshes (5 Hz), got {len(motion)}"
    for vx, vy, wz in motion:
        assert vx == pytest.approx(-0.25), "blind reverse crawls at -0.25 m/s"
        assert vy == pytest.approx(0.0), "escape is STRAIGHT back (no strafe)"
        assert wz == pytest.approx(0.0), "escape is STRAIGHT back (no yaw)"
    assert frames[-1] == (pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0))


def test_reverse_blind_speed_is_clamped_to_0_3(rev_hw) -> None:
    """Blind means crawl: even an explicit fast request is clamped to 0.3."""
    mod, hw, frames, _clk = rev_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.reverse_blind(0.5, speed=0.6)
    motion = _motion(frames)
    assert motion, "reverse must command motion frames"
    for vx, _vy, _wz in motion:
        assert vx == pytest.approx(-0.3), "blind reverse speed cap is 0.3 m/s"


def test_reverse_blind_stops_early_on_odometry_arrival(rev_hw) -> None:
    """Odometry says we covered the distance -> stop NOW, not at the deadline."""
    mod, hw, frames, clk = rev_hw
    published = []

    real_set = hw.set_velocity

    def _tracking_set(vx: float, vy: float, vyaw: float) -> None:
        published.append(vx)
        # After 3 motion frames, teleport odometry a full metre back.
        if len([v for v in published if v != 0.0]) == 3:
            hw._position = (-1.05, 0.0, 0.0)
        real_set(vx, vy, vyaw)

    hw.set_velocity = _tracking_set  # type: ignore[method-assign]
    t0 = clk.monotonic()
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.reverse_blind(1.0)
    assert ok is True
    elapsed = clk.monotonic() - t0
    assert elapsed < 2.0, f"odometry-confirmed arrival must stop early ({elapsed:.1f}s)"


def test_reverse_blind_open_loop_deadline_caps_the_window(rev_hw) -> None:
    """Frozen odometry: the window is bounded ~ distance/speed * 1.6."""
    mod, hw, frames, clk = rev_hw
    t0 = clk.monotonic()
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.reverse_blind(1.0)  # 4 s nominal -> <= ~6.4 s cap
    elapsed = clk.monotonic() - t0
    assert elapsed <= 7.5, f"open-loop window must be capped, got {elapsed:.1f}s"


# ---------------------------------------------------------------------------
# Safety — estop fail-fast, cancel seam, validation, oracle anchor
# ---------------------------------------------------------------------------


def test_reverse_blind_refuses_when_estop_latched(rev_hw) -> None:
    mod, hw, frames, _clk = rev_hw
    hw._estop_latched = True
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.reverse_blind(1.0) is False
    assert _motion(frames) == [], "a latched driver must not command motion"


def test_reverse_blind_cancel_navigation_unblocks(rev_hw) -> None:
    """cancel_navigation() (stop skill / Ctrl+C) aborts the reverse -> False."""
    mod, hw, frames, clk = rev_hw
    calls = []

    real_set = hw.set_velocity

    def _cancel_after_two(vx: float, vy: float, vyaw: float) -> None:
        calls.append(vx)
        if len([v for v in calls if v != 0.0]) == 2:
            hw._nav_abort.set()
        real_set(vx, vy, vyaw)

    hw.set_velocity = _cancel_after_two  # type: ignore[method-assign]
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.reverse_blind(1.0)
    assert ok is False, "a cancelled escape reports False (honest)"
    assert frames[-1] == (pytest.approx(0.0), pytest.approx(0.0), pytest.approx(0.0))


def test_reverse_blind_rejects_nonfinite_and_noops_zero(rev_hw) -> None:
    mod, hw, frames, _clk = rev_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        with pytest.raises(ValueError):
            hw.reverse_blind(float("nan"))
        assert hw.reverse_blind(0.0) is True
    assert _motion(frames) == []


def test_reverse_blind_anchors_the_moved_oracle(rev_hw) -> None:
    """move_anchor_xy is sampled at command start (Inv-1: driver-authored)."""
    mod, hw, frames, _clk = rev_hw
    hw._position = (2.5, -1.0, 0.0)
    hw.move_anchor_xy = None
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.reverse_blind(0.4)
    assert hw.move_anchor_xy == (pytest.approx(2.5), pytest.approx(-1.0))


def test_reverse_blind_disconnected_returns_false() -> None:
    from zeno.hardware.ros2 import go2w_hw as mod

    with patch.dict("sys.modules", _ros_module_stubs()):
        hw = mod.Go2WHardware()
        assert hw.reverse_blind(1.0) is False
