# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real bringup FAST STATUS — driver-known liveness beats nav.sh (v2, RED).

Field trace 2026-07-10 evening: bringup(action=status) blocks ~30 s (nav.sh
status probes 6 topics x 8 s each) even when the driver ALREADY knows the stack
is alive (fresh /state_estimation odometry). Pinned here:

* TOOL fast path: go2w_real_bringup(action='status') with fresh odometry
  (odom_age_s() < 3) answers in <1 s from driver-known facts — connected,
  odometry age, estop latch — WITHOUT ever running nav.sh.
* Fallback preserved: no base / stale odometry still runs the slow nav.sh
  status probe (cold/unknown stack — the driver knows nothing useful).
* SKILL probe fast path: RealBringupSkill's already-up probe answers True
  immediately on fresh odometry (no 8 s settle sleep, no poller).

Hermetic: fake driver, subprocess.run monkeypatched, no ROS env.
"""

from __future__ import annotations

import threading
import time as _time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


class _LiveFakeHW:
    """Driver stand-in exposing the liveness facts the fast path reads."""

    def __init__(self, connected: bool = True, age: float | None = 0.4,
                 latched: bool = False) -> None:
        self.is_connected = connected
        self.estop_latched = latched
        self._age = age

    def odom_age_s(self) -> float | None:
        return self._age


def _tool_ctx(base: Any | None):
    from zeno.vcli.tools.base import ToolContext

    agent = SimpleNamespace(_base=base) if base is not None else None
    return ToolContext(agent=agent, cwd=Path("/tmp"), session=None,
                       permissions=None, abort=threading.Event())


def _bringup_tool():
    from zeno.vcli.worlds.go2w_real_tools import Go2WRealBringupTool

    return Go2WRealBringupTool()


# ---------------------------------------------------------------------------
# TOOL fast path — <1 s, no nav.sh, driver facts in the content
# ---------------------------------------------------------------------------


@pytest.fixture
def forbid_navsh(monkeypatch: pytest.MonkeyPatch):
    """Any nav.sh subprocess on the fast path is a test failure."""
    import subprocess as _sp

    def _boom(*a: Any, **k: Any):
        raise AssertionError("fast path must NOT shell out to nav.sh")

    monkeypatch.setattr(_sp, "run", _boom)


def test_status_fast_path_answers_under_1s_without_nav_sh(forbid_navsh):
    tool = _bringup_tool()
    t0 = _time.perf_counter()
    res = tool.execute({"action": "status"}, _tool_ctx(_LiveFakeHW()))
    elapsed = _time.perf_counter() - t0
    assert not res.is_error, res.content
    assert elapsed < 1.0, f"fast status took {elapsed:.2f}s (must be <1s)"
    low = res.content.lower()
    assert "ready" in low
    assert "odometry" in low or "odom" in low


def test_status_fast_path_reports_estop_latch(forbid_navsh):
    res = _bringup_tool().execute(
        {"action": "status"}, _tool_ctx(_LiveFakeHW(latched=True)))
    assert not res.is_error
    assert "estop" in res.content.lower() or "e-stop" in res.content.lower()
    assert "true" in res.content.lower() or "latched" in res.content.lower()


# ---------------------------------------------------------------------------
# Fallback — stale/absent driver facts still run the honest nav.sh probe
# ---------------------------------------------------------------------------


@pytest.fixture
def record_navsh(monkeypatch: pytest.MonkeyPatch):
    from zeno.vcli.worlds import go2w_real_tools as mod

    calls: list[list[str]] = []

    def _run(cmd: Any, *a: Any, **k: Any):
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="units up, topics flowing",
                               stderr="")

    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", _run)
    monkeypatch.setattr(mod.os.path, "isfile", lambda _p: True)
    return calls


def test_status_falls_back_to_nav_sh_when_odom_stale(record_navsh):
    res = _bringup_tool().execute(
        {"action": "status"}, _tool_ctx(_LiveFakeHW(age=99.0)))
    assert not res.is_error
    assert record_navsh, "stale odometry must fall back to the nav.sh probe"
    assert record_navsh[-1][-1] == "status"


def test_status_falls_back_when_odom_never_arrived(record_navsh):
    res = _bringup_tool().execute(
        {"action": "status"}, _tool_ctx(_LiveFakeHW(age=None)))
    assert not res.is_error
    assert record_navsh


def test_status_falls_back_when_driver_disconnected(record_navsh):
    res = _bringup_tool().execute(
        {"action": "status"}, _tool_ctx(_LiveFakeHW(connected=False)))
    assert not res.is_error
    assert record_navsh


def test_status_falls_back_when_no_base(record_navsh):
    res = _bringup_tool().execute({"action": "status"}, _tool_ctx(None))
    assert not res.is_error
    assert record_navsh


def test_start_action_never_takes_the_fast_path(record_navsh):
    """Only STATUS gets the fast answer — lifecycle actions still go to nav.sh
    (start stays idempotent at the SKILL layer, not silently skipped here)."""
    res = _bringup_tool().execute(
        {"action": "start"}, _tool_ctx(_LiveFakeHW()))
    assert not res.is_error
    assert record_navsh and record_navsh[-1][-1] == "start"


# ---------------------------------------------------------------------------
# SKILL probe fast path — fresh odometry answers True with NO sleeping
# ---------------------------------------------------------------------------


def _forbid_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    from zeno.vcli.worlds import go2w_real_lifecycle as mod

    def _boom(_s: float) -> None:
        raise AssertionError("fast probe must not sleep")

    monkeypatch.setattr(mod.time, "sleep", _boom)


def test_ready_probe_is_instant_on_fresh_odometry(monkeypatch):
    from zeno.vcli.worlds.go2w_real_lifecycle import _default_ready_probe

    _forbid_sleep(monkeypatch)
    assert _default_ready_probe(_LiveFakeHW()) is True


def test_ready_probe_falls_back_to_poller_when_stale(monkeypatch):
    from zeno.vcli.worlds import go2w_real_lifecycle as mod

    polled: list[Any] = []
    monkeypatch.setattr(
        mod, "_default_ready_poller",
        lambda hw, timeout_s: polled.append(hw) or False)
    assert mod._default_ready_probe(_LiveFakeHW(age=99.0)) is False
    assert polled, "stale odometry must fall back to the slow poller"


def test_bringup_skill_start_is_instantly_idempotent_on_fresh_odometry(
    monkeypatch, tmp_path,
):
    """End-to-end at the skill layer: with the DEFAULT probe and a live driver,
    bringup(start) reports already-running without nav.sh and without sleeping."""
    from zeno.vcli.worlds import go2w_real_diag as d
    from zeno.vcli.worlds.go2w_real_lifecycle import RealBringupSkill

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "agent.log"))
    try:
        _forbid_sleep(monkeypatch)
        calls: list[list[str]] = []

        def runner(argv: Any, timeout: float):  # noqa: ARG001
            calls.append(list(argv))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        skill = RealBringupSkill(runner=runner)  # default probe + poller
        ctx = SimpleNamespace(base=_LiveFakeHW(), services={})
        result = skill.execute({"action": "start"}, ctx)
        assert result.success
        assert calls == [], "live stack must not be touched (idempotent start)"
        assert "already" in str(result.result_data or {}).lower()
    finally:
        d.set_oplog_path(old)
