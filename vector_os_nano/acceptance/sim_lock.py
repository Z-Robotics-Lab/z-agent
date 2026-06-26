# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""sim_lock — the global ONE-simulator-at-a-time discipline (ADR-002 Stage 0; performance.md OOM rule).

The host RAM (64 GB) is SHARED across sessions/loops and the documented #1 OOM cause is leaked /
concurrent simulators (two go2 sims ~= 50 GB). This is the missing IN-CODE serialization point the
repo lacked: an ``fcntl.flock`` on one host-wide lock file + a preflight that WAITS while any other
sim (``mujoco`` / ``vcli``) is live or RAM is low, and a nuke-after teardown. Pure stdlib.

Why flock (not a pidfile): an ``fcntl`` lock is bound to the process/open-file-description, so it
AUTO-RELEASES when the holder dies — no stale-lock cleanup, no "the loop crashed and wedged the lock".

Usage:
    from vector_os_nano.acceptance import sim_lock
    with sim_lock.sim_lock():           # blocks until the host is sim-free, up to wait_timeout
        run_one_sim_turn()              # only OUR sim runs while we hold the lock
    # -> on exit: rosm nuke --yes + pkill -9 -f mujoco, THEN the lock releases (next waiter proceeds)
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import subprocess
import time
from pathlib import Path

_LOCK_DIR = Path(os.path.expanduser("~/.claude/loops"))
_DEFAULT_LOCK = _LOCK_DIR / "vector_sim.lock"
# Bracket patterns so `pgrep -f` never matches its OWN command line (the classic self-match trap).
_SIM_PATTERNS = ("[m]ujoco", "[v]cli.cli", "[l]aunch_explore")


class SimBusy(RuntimeError):
    """The lock or the clear-host preflight could not be satisfied within ``wait_timeout``."""


def live_sim_pids(exclude: set[int] | None = None) -> list[int]:
    """PIDs of live simulator/cli processes (mujoco|vcli|launch_explore), excluding self + ``exclude``.

    Excludes ONLY our own PID (bracket patterns already prevent matching pgrep's/our cmdline). We do
    NOT exclude the parent: a false-positive wait is safe, but masking a real sim that happens to be an
    ancestor (false-negative) is exactly the OOM-unsafe direction this guard exists to prevent.
    """
    skip = set(exclude or ()) | {os.getpid()}
    found: set[int] = set()
    for pat in _SIM_PATTERNS:
        try:
            out = subprocess.run(["pgrep", "-f", pat], capture_output=True, text=True, timeout=5)
        except Exception:  # noqa: BLE001 — pgrep missing/odd -> treat as "none found"
            continue
        for tok in out.stdout.split():
            try:
                pid = int(tok)
            except ValueError:
                continue
            if pid not in skip:
                found.add(pid)
    return sorted(found)


def free_gb() -> float:
    """Available host RAM in GiB (the last column of ``free -g`` Mem:). inf if unknown (don't block)."""
    try:
        out = subprocess.run(["free", "-g"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            if line.lower().startswith("mem:"):
                return float(line.split()[-1])
    except Exception:  # noqa: BLE001
        pass
    return float("inf")


def nuke() -> None:
    """Tear down any simulator this lock-holder left behind (rosm nuke + pkill mujoco). Best-effort.

    Safe ONLY because the caller holds the lock AND the preflight ensured no OTHER sim was live — so
    the only simulator processes are ours. (Full coverage requires every sim launcher, incl. the
    EvolvingLoop, to also acquire this lock; until then, the preflight + a paused loop is the gap.)
    """
    for cmd in (["rosm", "nuke", "--yes"], ["pkill", "-9", "-f", "mujoco"]):
        try:
            subprocess.run(cmd, capture_output=True, timeout=20)
        except Exception:  # noqa: BLE001
            pass


@contextlib.contextmanager
def sim_lock(
    *,
    lock_path: str | os.PathLike | None = None,
    nuke_after: bool = True,
    wait_timeout: float = 600.0,
    poll: float = 2.0,
    require_clear: bool = True,
    min_free_gb: float = 8.0,
):
    """Acquire the global sim lock, WAITING (up to ``wait_timeout``) until the host is sim-free + RAM ok.

    Raises ``SimBusy`` if neither the flock nor a clear host could be obtained in time (fail-loud, never
    silently run a 2nd concurrent sim). On exit: ``nuke_after`` teardown UNDER the lock, then release.
    """
    path = Path(lock_path) if lock_path else _DEFAULT_LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o664)
    deadline = time.monotonic() + wait_timeout
    acquired = False
    try:
        # 1) acquire the flock — NON-blocking poll so a hung holder cannot deadlock us forever.
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise SimBusy(f"sim lock {path} held by another process for > {wait_timeout}s")
                time.sleep(poll)
        # 2) preflight: even holding the flock, refuse to run while a non-lock sim (e.g. the loop) is
        #    live or RAM is low — this is the cross-process guard (the loop does not take our flock).
        if require_clear:
            while True:
                live = live_sim_pids()
                avail = free_gb()
                if not live and avail >= min_free_gb:
                    break
                if time.monotonic() >= deadline:
                    raise SimBusy(
                        f"host not sim-free after {wait_timeout}s (live={live}, free={avail}GB)"
                    )
                time.sleep(poll)
        # record the holder (observability only; flock — not this text — is the lock)
        try:
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()} {int(time.time())}\n".encode())
        except Exception:  # noqa: BLE001
            pass
        yield
    finally:
        if acquired and nuke_after:
            nuke()
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:  # noqa: BLE001
                pass
        os.close(fd)
