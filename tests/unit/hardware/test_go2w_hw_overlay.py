# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""OverlayLauncher — nav.sh overlay child-process lifecycle (explore/route v2).

Pure-unit and process-free: the Popen factory is injected, so NO real child is
ever spawned. Ground truth is the PROCESS CONTRACT the launcher must honor:

* an overlay is ``bash <nav.sh> <mode> [args...]`` — nav.sh 'explore'/'route'
  exec into ``ros2 launch``, so the child PID IS the launch process;
* the launcher owns exactly the child it spawned: teardown is SIGINT to that
  PID only (NEVER-KILL-INFRA: no pkill, no process-name matching, no SIGKILL —
  a SIGINT-deaf child is reported honestly, not force-killed);
* one overlay per launcher at a time; relaunch is allowed after exit;
* a missing nav.sh fails loud before any spawn.

This is the shared seam the v2 route-mode agent reuses (see go2w_hw_overlay).
"""

from __future__ import annotations

import signal
import subprocess
from pathlib import Path

import pytest


def _approx(v: float):
    return pytest.approx(v, abs=1e-9)


# ---------------------------------------------------------------------------
# Fakes — a Popen stand-in the launcher drives instead of a real child
# ---------------------------------------------------------------------------


class FakeProc:
    """Duck-typed subprocess.Popen: exits after the Nth SIGINT (None = never)."""

    def __init__(self, pid: int = 4242, exits_on_sigint: int | None = 1) -> None:
        self.pid = pid
        self.signals: list[int] = []
        self._rc: int | None = None
        self._exits_on = exits_on_sigint

    def poll(self) -> int | None:
        return self._rc

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)
        if self._exits_on is not None and len(self.signals) >= self._exits_on:
            self._rc = 130  # SIGINT exit

    def wait(self, timeout: float | None = None):
        if self._rc is None:
            raise subprocess.TimeoutExpired(cmd="nav.sh", timeout=timeout or 0.0)
        return self._rc

    def die(self, rc: int) -> None:
        """Simulate the child exiting on its own (crash / require_stack fail)."""
        self._rc = rc


class FakePopenFactory:
    """Records every spawn request; returns the scripted FakeProc."""

    def __init__(self, proc: FakeProc | None = None) -> None:
        self.calls: list[tuple[list[str], dict]] = []
        self.proc = proc or FakeProc()

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        return self.proc


def _nav_sh(tmp_path: Path) -> str:
    p = tmp_path / "nav.sh"
    p.write_text("#!/usr/bin/env bash\n")
    return str(p)


def _launcher(tmp_path: Path, proc: FakeProc | None = None):
    from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher

    factory = FakePopenFactory(proc)
    lau = OverlayLauncher("explore", nav_sh=_nav_sh(tmp_path), popen_factory=factory)
    return lau, factory


# ---------------------------------------------------------------------------
# Import contract — no rclpy / no ROS env needed at module import
# ---------------------------------------------------------------------------


def test_module_imports_without_ros_env() -> None:
    from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher, TravelTracker

    assert OverlayLauncher is not None
    assert TravelTracker is not None


# ---------------------------------------------------------------------------
# launch — argv shape, child ownership, single-overlay guard
# ---------------------------------------------------------------------------


def test_launch_spawns_navsh_overlay_child(tmp_path: Path) -> None:
    """launch() spawns exactly ``bash <nav.sh> explore <scenario>`` as OUR child,
    detached from our terminal signals (start_new_session) with stdin closed."""
    lau, factory = _launcher(tmp_path)

    ok, msg = lau.launch("indoor_small")

    assert ok is True, msg
    assert len(factory.calls) == 1
    argv, kwargs = factory.calls[0]
    assert argv[0] == "bash"
    assert argv[1].endswith("nav.sh")
    assert argv[2] == "explore"
    assert argv[3] == "indoor_small"
    assert kwargs.get("start_new_session") is True
    assert kwargs.get("stdin") == subprocess.DEVNULL
    assert lau.is_running() is True
    assert lau.pid == factory.proc.pid


def test_launch_refuses_second_overlay_while_running(tmp_path: Path) -> None:
    """One overlay per launcher: a second launch while the child runs is refused
    (no silent double-TARE fighting over /way_point)."""
    lau, factory = _launcher(tmp_path)
    assert lau.launch("indoor_small")[0] is True

    ok, msg = lau.launch("indoor_small")

    assert ok is False
    assert "already" in msg.lower()
    assert len(factory.calls) == 1, "no second child may be spawned"


def test_launch_fails_loud_when_navsh_missing(tmp_path: Path) -> None:
    """A missing nav.sh is a loud pre-spawn error, not a dead child later."""
    from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher

    factory = FakePopenFactory()
    lau = OverlayLauncher(
        "explore", nav_sh=str(tmp_path / "nope.sh"), popen_factory=factory
    )

    ok, msg = lau.launch("indoor_small")

    assert ok is False
    assert "nav.sh" in msg
    assert not factory.calls, "no spawn may happen without the script"


def test_relaunch_allowed_after_child_exit(tmp_path: Path) -> None:
    """After the child exits, the launcher can spawn a fresh overlay."""
    lau, factory = _launcher(tmp_path)
    assert lau.launch("indoor_small")[0] is True
    factory.proc.die(0)
    assert lau.is_running() is False

    factory.proc = FakeProc(pid=5000)
    ok, _ = lau.launch("outdoor")

    assert ok is True
    assert lau.pid == 5000


# ---------------------------------------------------------------------------
# stop — SIGINT-only teardown of OUR child; honest on a SIGINT-deaf child
# ---------------------------------------------------------------------------


def test_stop_sigints_own_child_and_reports_clean(tmp_path: Path) -> None:
    """stop() sends SIGINT to the child we spawned (ros2 launch tears down its
    nodes on SIGINT) and reports a clean exit."""
    lau, factory = _launcher(tmp_path)
    lau.launch("indoor_small")

    clean, rc = lau.stop(grace_s=0.05)

    assert clean is True
    assert rc == 130
    assert factory.proc.signals == [signal.SIGINT]
    assert lau.stop_requested is True
    assert lau.is_running() is False


def test_stop_retries_one_sigint_then_reports_failure(tmp_path: Path) -> None:
    """A SIGINT-deaf child gets exactly ONE more SIGINT, then stop() reports
    failure honestly (never SIGKILL/pkill — NEVER-KILL-INFRA)."""
    proc = FakeProc(exits_on_sigint=None)  # never exits
    lau, factory = _launcher(tmp_path, proc=proc)
    lau.launch("indoor_small")

    clean, rc = lau.stop(grace_s=0.01)

    assert clean is False
    assert rc is None
    assert proc.signals == [signal.SIGINT, signal.SIGINT]
    assert lau.is_running() is True, "an unstopped child must still read as running"


def test_stop_without_child_is_noop(tmp_path: Path) -> None:
    """stop() with nothing launched is a clean no-op (idempotent teardown)."""
    lau, _factory = _launcher(tmp_path)

    clean, rc = lau.stop(grace_s=0.01)

    assert clean is True
    assert rc is None


# ---------------------------------------------------------------------------
# TravelTracker — the odometry-integrated distance oracle (shared with route)
# ---------------------------------------------------------------------------


def test_travel_tracker_integrates_path_length() -> None:
    from zeno.hardware.ros2.go2w_hw_overlay import TravelTracker

    t = TravelTracker()
    t.sample(0.0, 0.0)
    t.sample(1.0, 0.0)
    t.sample(1.0, 1.0)
    assert t.meters == _approx(2.0)


def test_travel_tracker_filters_noise_and_slam_jumps() -> None:
    """Sub-noise-floor steps must not inflate distance while parked; a huge jump
    (SLAM relocalization) must not count as travel. The metric stays monotone."""
    from zeno.hardware.ros2.go2w_hw_overlay import TravelTracker

    t = TravelTracker(min_step_m=0.02, max_step_m=5.0)
    t.sample(0.0, 0.0)
    for _ in range(100):  # 100 x 5 mm odom jitter while standing still
        t.sample(0.005, 0.0)
        t.sample(0.0, 0.0)
    assert t.meters == _approx(0.0)

    t.sample(1.0, 0.0)  # real 1 m step
    before = t.meters
    t.sample(50.0, 50.0)  # relocalization teleport — not travel
    assert t.meters == _approx(before)
    t.sample(50.0, 51.0)  # normal motion continues from the new anchor
    assert t.meters == _approx(before + 1.0)


def test_travel_tracker_reset_zeroes_the_metric() -> None:
    from zeno.hardware.ros2.go2w_hw_overlay import TravelTracker

    t = TravelTracker()
    t.sample(0.0, 0.0)
    t.sample(1.0, 0.0)
    assert t.meters == _approx(1.0)
    t.reset()
    assert t.meters == _approx(0.0)
