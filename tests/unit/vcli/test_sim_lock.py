# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the global sim lock serializes simulators and fails LOUD (ADR-002 Stage 0).

flock mutual exclusion, the clear-host/RAM preflight, and nuke-after-under-the-lock are pinned here.
No simulator is launched — the lock semantics are exercised directly.
"""
from __future__ import annotations

import fcntl
import os

import pytest

from vector_os_nano.acceptance import sim_lock


def test_flock_mutual_exclusion_then_releases(tmp_path):
    lock = tmp_path / "sim.lock"
    # An independent fd holds the exclusive flock (simulates another live holder).
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
    # Once the other holder releases, the lock is acquirable.
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
    monkeypatch.setattr(sim_lock, "nuke", lambda: calls.append(1))
    with sim_lock.sim_lock(lock_path=str(tmp_path / "l.lock"), require_clear=False, nuke_after=True):
        pass
    assert calls == [1]


def test_nuke_after_runs_even_on_exception(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sim_lock, "nuke", lambda: calls.append(1))
    with pytest.raises(ValueError):
        with sim_lock.sim_lock(lock_path=str(tmp_path / "l.lock"), require_clear=False, nuke_after=True):
            raise ValueError("boom")
    assert calls == [1]  # teardown happens in finally, before the lock releases


def test_nuke_after_skipped_when_never_acquired(tmp_path, monkeypatch):
    """If we never acquire (another holder), nuke must NOT fire (we'd be killing the holder's sim)."""
    calls = []
    monkeypatch.setattr(sim_lock, "nuke", lambda: calls.append(1))
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
    assert calls == []  # never acquired -> never nuked


def test_live_sim_pids_excludes_self():
    assert os.getpid() not in sim_lock.live_sim_pids()
