# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""sim_lock — the global ONE-simulator-at-a-time discipline (ADR-002 Stage 0; performance.md OOM rule).

The host RAM (64 GB) is SHARED across sessions/loops and the documented #1 OOM cause is leaked /
concurrent simulators (two go2 sims ~= 50 GB). This is the missing IN-CODE serialization point the
repo lacked: an ``fcntl.flock`` on one host-wide lock file + a preflight that WAITS while any other
sim is live or RAM is low, and a TARGETED teardown.

Why flock (not a pidfile): a flock is bound to the open file description (OFD), so it releases when
the last fd for that OFD closes — which the OS does on process death. The lock fd is opened
``O_CLOEXEC`` and ``subprocess`` defaults ``close_fds=True``, so a spawned sim child never inherits
it; thus "the lock releases when the holder dies" holds (no stale-lock cleanup, no pidfile).

Usage:
    from vector_os_nano.acceptance import sim_lock
    with sim_lock.sim_lock():            # blocks until the host is sim-free, up to wait_timeout
        run_one_sim_turn()               # only OUR sim runs while we hold the lock
    # -> on exit: teardown of the sims WE started (targeted, not host-wide), then the lock releases.

Safety invariants (see the adversarial review, ADR-002 Stage 0):
  - Teardown fires ONLY if we actually RAN a sim (reached the ``yield``) — NEVER on a preflight
    refusal, so refusing to run beside a live sim can never kill that sim.
  - Teardown is TARGETED: it kills only sim processes that appeared AFTER we acquired (sparing any
    pre-existing ``protected`` sim), not a host-wide ``pkill``.
  - The mid-hold gap (a non-lock launcher, e.g. the EvolvingLoop, starting a sim WHILE we hold) is
    closed only by that launcher ALSO taking this lock — the remaining adoption follow-up.
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import signal
import subprocess
import time
from pathlib import Path

def _default_lock_path() -> Path:
    """Host-global, HOME-INDEPENDENT lock path. It MUST NOT live under ``~``: test/sandbox harnesses
    (e.g. ``tests.harness.pty_cli``) override ``HOME``, so a ``~``-relative lock would split per
    sandbox and STOP serializing the harness against real-HOME sims (the loop). Uses the per-user
    runtime dir (tmpfs, always present on a logged-in host); override with ``VECTOR_SIM_LOCK_PATH``.
    """
    override = os.environ.get("VECTOR_SIM_LOCK_PATH")
    if override:
        return Path(override)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and os.path.isdir(runtime):
        return Path(runtime) / "vector_sim.lock"
    return Path(f"/tmp/vector_sim_{os.getuid()}.lock")
# A live SIMULATOR (not an idle vector-cli REPL): an actual mujoco/explore process, or a cli launched
# WITH a sim flag (`--sim` / `--sim-go2`). Bracket patterns so `pgrep -f` never matches its own (or
# our) command line. NB: an in-process sim launched by NL inside a REPL (no `--sim` in argv) is not
# detected by cmdline alone — that interactive case relies on the human pausing automated loops.
_SIM_PATTERNS = ("[m]ujoco", "[-]-sim", "[l]aunch_explore")


class SimBusy(RuntimeError):
    """The lock or the clear-host preflight could not be satisfied within ``wait_timeout``."""


def live_sim_pids(exclude: set[int] | None = None) -> list[int]:
    """PIDs of live simulator processes, excluding self.

    Excludes ONLY our own PID (bracket patterns already prevent matching pgrep's/our cmdline). We do
    NOT exclude the parent: a false-positive wait is safe, but masking a real sim that happens to be
    an ancestor (false-negative) is exactly the OOM-unsafe direction this guard exists to prevent.
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


def nuke(protect: set[int] | None = None) -> None:
    """Tear down simulator processes that appeared AFTER acquire (i.e. NOT in ``protect``), then
    rosm-nuke ROS state. TARGETED (per-PID ``os.kill``, never a host-wide ``pkill``) so a sim some
    other process started is not collateral-killed. Best-effort; never raises.
    """
    protect = protect or set()
    for pid in live_sim_pids():
        if pid in protect:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:  # noqa: BLE001 — already gone / not ours to signal
            pass
    try:
        subprocess.run(["rosm", "nuke", "--yes"], capture_output=True, timeout=20)
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

    Raises ``SimBusy`` if neither the flock nor a clear host could be obtained in time (fail-loud,
    never silently run a 2nd concurrent sim). Teardown fires ONLY if we actually ran a sim.
    """
    path = Path(lock_path) if lock_path else _default_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o664)
    acquired = False
    ran = False
    protected: set[int] = set()
    try:
        # 1) acquire the flock — NON-blocking poll so a hung holder cannot deadlock us forever.
        deadline = time.monotonic() + wait_timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise SimBusy(f"sim lock {path} held by another process for > {wait_timeout}s")
                time.sleep(poll)
        # 2) preflight (its OWN budget, so a long flock-wait can't starve it): refuse to run while a
        #    non-lock sim is live or RAM is low. Raising here MUST NOT nuke (ran is still False).
        if require_clear:
            pre_deadline = time.monotonic() + wait_timeout
            while True:
                live = live_sim_pids()
                avail = free_gb()
                if not live and avail >= min_free_gb:
                    break
                if time.monotonic() >= pre_deadline:
                    raise SimBusy(f"host not sim-free after {wait_timeout}s (live={live}, free={avail}GB)")
                time.sleep(poll)
        # Pre-existing sims to SPARE on teardown (empty after a clear preflight; matters when
        # require_clear=False, so we never kill a sim that was already running).
        protected = set(live_sim_pids())
        try:
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()} {int(time.time())}\n".encode())
        except Exception:  # noqa: BLE001
            pass
        ran = True  # from here on a sim may run -> teardown is OURS to do
        yield
    finally:
        if ran and nuke_after:
            nuke(protect=protected)
        if acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:  # noqa: BLE001
                pass
        os.close(fd)
