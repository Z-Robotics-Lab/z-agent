# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the global sim lock serializes simulators, fails LOUD, and never collateral-kills (ADR-002 Stage 0).

flock mutual exclusion, the clear-host/RAM preflight, teardown-only-if-we-ran, and targeted nuke are
pinned here. No simulator is launched — the lock semantics are exercised directly. The regression
tests encode the adversarial-review findings (CRITICAL: no nuke on preflight refusal; #2: idle REPL
must not register as a sim).
"""
from __future__ import annotations

import fcntl
import os

import pytest

from zeno.acceptance import sim_lock


def test_flock_mutual_exclusion_then_releases(tmp_path):
    lock = tmp_path / "sim.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(sim_lock.SimBusy):
            with sim_lock.sim_lock(
                lock_path=str(lock), require_clear=False, nuke_after=False, wait_timeout=0.3, poll=0.05
            ):
                pass
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    entered = []
    with sim_lock.sim_lock(lock_path=str(lock), require_clear=False, nuke_after=False, wait_timeout=2.0):
        entered.append(1)
    assert entered == [1]


def test_preflight_refuses_while_a_sim_is_live(tmp_path, monkeypatch):
    monkeypatch.setattr(sim_lock, "live_sim_pids", lambda *a, **k: [99999])
    monkeypatch.setattr(sim_lock, "free_gb", lambda: 50.0)
    with pytest.raises(sim_lock.SimBusy):
        with sim_lock.sim_lock(
            lock_path=str(tmp_path / "l.lock"), require_clear=True, nuke_after=False,
            wait_timeout=0.3, poll=0.05,
        ):
            pass


def test_preflight_refuses_low_ram(tmp_path, monkeypatch):
    monkeypatch.setattr(sim_lock, "live_sim_pids", lambda *a, **k: [])
    monkeypatch.setattr(sim_lock, "free_gb", lambda: 2.0)
    with pytest.raises(sim_lock.SimBusy):
        with sim_lock.sim_lock(
            lock_path=str(tmp_path / "l.lock"), require_clear=True, nuke_after=False,
            min_free_gb=8.0, wait_timeout=0.3, poll=0.05,
        ):
            pass


def test_preflight_passes_when_host_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(sim_lock, "live_sim_pids", lambda *a, **k: [])
    monkeypatch.setattr(sim_lock, "free_gb", lambda: 50.0)
    entered = []
    with sim_lock.sim_lock(lock_path=str(tmp_path / "l.lock"), require_clear=True, nuke_after=False):
        entered.append(1)
    assert entered == [1]


def test_nuke_after_runs_on_normal_exit(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sim_lock, "nuke", lambda *a, **k: calls.append(1))
    with sim_lock.sim_lock(lock_path=str(tmp_path / "l.lock"), require_clear=False, nuke_after=True):
        pass
    assert calls == [1]


def test_nuke_after_runs_even_on_exception(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sim_lock, "nuke", lambda *a, **k: calls.append(1))
    with pytest.raises(ValueError):
        with sim_lock.sim_lock(lock_path=str(tmp_path / "l.lock"), require_clear=False, nuke_after=True):
            raise ValueError("boom")
    assert calls == [1]  # teardown happens in finally, before the lock releases


def test_nuke_skipped_when_never_acquired(tmp_path, monkeypatch):
    """Another holder -> we never acquire -> never nuke (we'd be killing the holder's sim)."""
    calls = []
    monkeypatch.setattr(sim_lock, "nuke", lambda *a, **k: calls.append(1))
    lock = tmp_path / "l.lock"
    fd = os.open(str(lock), os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(sim_lock.SimBusy):
            with sim_lock.sim_lock(
                lock_path=str(lock), require_clear=False, nuke_after=True, wait_timeout=0.2, poll=0.05
            ):
                pass
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
    assert calls == []


def test_nuke_NOT_called_on_preflight_refusal(tmp_path, monkeypatch):
    """CRITICAL regression (adversarial review): we acquired the flock but the clear-host preflight
    REFUSED (another sim live) — teardown must NOT fire, else we'd pkill the sim we yielded to."""
    calls = []
    monkeypatch.setattr(sim_lock, "live_sim_pids", lambda *a, **k: [99999])  # a sim is live
    monkeypatch.setattr(sim_lock, "free_gb", lambda: 50.0)
    monkeypatch.setattr(sim_lock, "nuke", lambda *a, **k: calls.append(1))
    with pytest.raises(sim_lock.SimBusy):
        with sim_lock.sim_lock(
            lock_path=str(tmp_path / "l.lock"), require_clear=True, nuke_after=True,
            wait_timeout=0.3, poll=0.05,
        ):
            pass
    assert calls == []  # acquired the flock, but never RAN a sim -> never nuked


def test_nuke_spares_preexisting_sims(monkeypatch):
    """Targeted teardown (#3): a sim that was already live at acquire (protected) is NOT killed."""
    killed = []
    monkeypatch.setattr(sim_lock, "live_sim_pids", lambda *a, **k: [4242])
    monkeypatch.setattr(sim_lock.os, "kill", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(sim_lock.subprocess, "run", lambda *a, **k: None)
    sim_lock.nuke(protect={4242})
    assert killed == []  # the pre-existing PID is spared


def test_sim_patterns_target_sims_not_idle_repl():
    """#2: detection matches actual sims (mujoco / a --sim-flagged cli / explore) but NOT an idle
    zeno REPL, exercised as regexes against representative command lines."""
    import re

    def matches(cmdline: str) -> bool:
        return any(re.search(p, cmdline) for p in sim_lock._SIM_PATTERNS)

    assert matches("python -m zeno.vcli.cli -p x --sim-go2 --headless")  # loop sim
    assert matches("/opt/mujoco/bin/mujoco_viewer")                                # mujoco proc
    assert matches("bash scripts/launch_explore.sh")                               # explore
    assert not matches("python -m zeno.vcli.cli")                        # idle REPL (no sim)
    assert not matches("zeno")                                                    # idle REPL


def test_default_lock_path_is_home_independent(monkeypatch, tmp_path):
    """Regression: the global lock must NOT move when HOME changes — pty_cli/sandbox harnesses
    override HOME, and a ~-relative lock would split per sandbox and stop serializing."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("HOME", "/some/sandbox/home")
    monkeypatch.delenv("VECTOR_SIM_LOCK_PATH", raising=False)
    p = str(sim_lock._default_lock_path())
    assert "/some/sandbox/home" not in p and str(tmp_path) in p
    # explicit override is honored
    monkeypatch.setenv("VECTOR_SIM_LOCK_PATH", "/tmp/explicit_sim.lock")
    assert str(sim_lock._default_lock_path()) == "/tmp/explicit_sim.lock"


def test_live_sim_pids_excludes_self():
    assert os.getpid() not in sim_lock.live_sim_pids()
