# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WExploreManager stop semantics + driver estop latch (split from
test_go2w_hw_explore.py — repo rule: files under 400 lines).

Covers: stop_explore = SIGINT our child -> wait -> /nav_cancel -> resume
GUARDED by the estop latch; honest SIGINT-timeout reporting; the finished
verdict surviving teardown; and the TriggerServiceMixin estop_latched flag
the guard reads. Same pure-unit fixtures as the sibling file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from tests.unit.hardware.test_go2w_hw_explore import (
    FakeHW,
    _bool_msg,
    _mgr,
    _started,
    _sub_callback,
)
from tests.unit.hardware.test_go2w_hw_overlay import FakeProc

# ---------------------------------------------------------------------------
# stop semantics — SIGINT own child -> wait -> /nav_cancel -> GUARDED resume
# ---------------------------------------------------------------------------


def test_stop_explore_sigint_then_nav_cancel(tmp_path: Path) -> None:
    mgr, hw, factory = _started(tmp_path)

    ok, msg = mgr.stop_explore()

    assert ok is True
    import signal as _sig

    assert factory.proc.signals == [_sig.SIGINT]
    assert hw.nav_cancel.called, "stop must clear the waypoint TARE left latched"
    assert mgr.state() == "stopped"
    assert "request" in mgr.status().reason.lower()
    # Default stop does NOT touch the estop/manual latches.
    assert not hw.estop_release.called


def test_stop_explore_resume_is_guarded_by_estop_latch(tmp_path: Path) -> None:
    """resume=True must NOT release the latches when an E-stop is latched — an
    operator's E-stop may never be un-done as a side effect of stopping TARE."""
    hw = FakeHW()
    hw.estop_latched = True
    mgr, hw, _factory = _started(tmp_path, hw=hw)

    ok, msg = mgr.stop_explore(resume=True)

    assert ok is True
    assert not hw.estop_release.called
    assert "estop" in msg.lower() or "e-stop" in msg.lower()


def test_stop_explore_resume_when_not_estopped(tmp_path: Path) -> None:
    mgr, hw, _factory = _started(tmp_path)

    ok, _msg = mgr.stop_explore(resume=True)

    assert ok is True
    assert hw.estop_release.called


def test_stop_when_idle_is_clean_noop(tmp_path: Path) -> None:
    mgr, hw, _factory = _mgr(tmp_path)

    ok, msg = mgr.stop_explore()

    assert ok is True
    assert not hw.nav_cancel.called


def test_stop_sigint_timeout_reports_honest_failure(tmp_path: Path) -> None:
    """A SIGINT-deaf child: stop reports failure, still fires /nav_cancel (clear
    the latched goal even if TARE lingers), and the state does NOT lie 'stopped'
    while the child is alive."""
    proc = FakeProc(exits_on_sigint=None)
    mgr, hw, _factory = _started(tmp_path, proc=proc)

    ok, msg = mgr.stop_explore()

    assert ok is False
    assert "still running" in msg.lower() or "pid" in msg.lower()
    assert hw.nav_cancel.called
    assert mgr.state() != "stopped"
    assert mgr.is_active is True


def test_finished_verdict_survives_stop(tmp_path: Path) -> None:
    """finish=True then stop: the session DID finish; verify after teardown must
    still read True (and the travel metric stays frozen alongside it)."""
    mgr, hw, _factory = _started(tmp_path)
    _sub_callback(hw, "/exploration_finish")(_bool_msg(True))

    mgr.stop_explore()

    assert mgr.state() == "stopped"
    assert mgr.explore_finished() is True


# ---------------------------------------------------------------------------
# Driver estop latch — the flag the resume guard reads (TriggerServiceMixin)
# ---------------------------------------------------------------------------


def _hw_with_mock_node(trigger_success: bool = True):
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    node = MagicMock()
    resp = MagicMock()
    resp.success = trigger_success
    future = MagicMock()
    future.result.return_value = resp

    def _client(_srv: Any, name: str, *_a: Any, **_k: Any) -> MagicMock:
        c = MagicMock(name=f"cli{name}")
        c.wait_for_service.return_value = True
        c.call_async.return_value = future
        return c

    node.create_client.side_effect = _client
    node.create_publisher.return_value = MagicMock()
    node.create_subscription = MagicMock()
    hw = Go2WHardware()
    hw._install_node_for_test(node)
    return hw


def test_estop_latch_set_on_success_and_cleared_on_release() -> None:
    with patch.dict("sys.modules", {"std_srvs": MagicMock(), "std_srvs.srv": MagicMock()}):
        hw = _hw_with_mock_node(trigger_success=True)
        assert hw.estop_latched is False
        assert hw.estop() is True
        assert hw.estop_latched is True
        assert hw.estop_release() is True
        assert hw.estop_latched is False


def test_estop_latch_not_set_when_trigger_fails() -> None:
    with patch.dict("sys.modules", {"std_srvs": MagicMock(), "std_srvs.srv": MagicMock()}):
        hw = _hw_with_mock_node(trigger_success=False)
        assert hw.estop() is False
        assert hw.estop_latched is False

# ---------------------------------------------------------------------------
# orphan death safety — a dead TARE leaves /way_point latched; clear it
# ---------------------------------------------------------------------------


def _wait_called(mock: Any, timeout_s: float = 2.0) -> bool:
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if mock.called:
            return True
        time.sleep(0.01)
    return bool(mock.called)


def test_orphan_death_fires_background_nav_cancel(tmp_path: Path) -> None:
    """When the overlay dies unexpectedly, the robot would keep chasing TARE's
    last latched waypoint — orphan detection fires ONE background /nav_cancel
    (a daemon thread: detection may run on the rclpy executor thread, where a
    synchronous service call cannot complete)."""
    mgr, hw, factory = _started(tmp_path)

    factory.proc.die(1)
    assert mgr.state() == "stopped"

    assert _wait_called(hw.nav_cancel), (
        "orphan death must clear the latched waypoint via /nav_cancel"
    )


def test_stop_after_orphan_death_retries_nav_cancel_sync(tmp_path: Path) -> None:
    """stop_explore after an orphan death is a no-op for the process, but gives
    the safety /nav_cancel a reliable synchronous second shot."""
    mgr, hw, factory = _started(tmp_path)
    factory.proc.die(1)
    assert mgr.state() == "stopped"
    _wait_called(hw.nav_cancel)
    hw.nav_cancel.reset_mock()

    ok, msg = mgr.stop_explore()

    assert ok is True
    assert "no explore session" in msg
    assert hw.nav_cancel.called
