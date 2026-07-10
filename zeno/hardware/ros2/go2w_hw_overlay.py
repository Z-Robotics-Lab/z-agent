# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""OverlayLauncher — nav.sh overlay child-process lifecycle (explore/route).

The nav stack's FOREGROUND overlay modes (``nav.sh explore`` / ``nav.sh
route``) exec into ``ros2 launch`` (tare_planner / far_planner) on top of the
already-running base stack. This class owns exactly ONE such overlay as a
CHILD subprocess:

* spawn:   ``bash <nav.sh> <mode> [args...]`` — nav.sh sources its own DDS env
  (ROS_DOMAIN_ID=20, CycloneDDS) and ``exec``s ros2 launch, so the child PID
  IS the launch process; ``start_new_session=True`` detaches it from our
  terminal so a REPL Ctrl+C (turn abort) can never kill an exploration.
* teardown: SIGINT to that PID ONLY — ros2 launch tears its nodes down on
  SIGINT. NEVER-KILL-INFRA: no pkill, no name matching, no SIGKILL/SIGTERM
  escalation; a SIGINT-deaf child is reported honestly (still running).
* one overlay per launcher at a time; relaunch is allowed after exit.

``TravelTracker`` lives here too: the odometry-integrated distance metric both
overlay modes use as an independent progress oracle (Inv-1: it reads
/state_estimation samples the actor cannot author).

This is the shared seam for the v2 feature agents: route-mode reuses
``OverlayLauncher("route", ...)`` + ``TravelTracker`` as-is. No rclpy imports
here — the module is safe to import with no ROS env.
"""

from __future__ import annotations

import logging
import math
import os
import signal
import subprocess
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

_DEFAULT_NAV_SH = "~/go2w-nuc/scripts/nav.sh"
_DEFAULT_LOG_DIR = "~/go2w-nuc/logs"


class TravelTracker:
    """Odometry path-length integrator — the independent progress oracle.

    Accumulates planar displacement between consecutive samples, ignoring
    sub-noise-floor steps (odom jitter while parked must not inflate the
    metric) and super-``max_step_m`` jumps (SLAM relocalization is not
    travel; the jump target becomes the new anchor). The metric is monotone
    non-decreasing until ``reset()``.
    """

    def __init__(self, min_step_m: float = 0.02, max_step_m: float = 5.0) -> None:
        self._min_step = float(min_step_m)
        self._max_step = float(max_step_m)
        self._last: tuple[float, float] | None = None
        self._total = 0.0

    def reset(self) -> None:
        self._last = None
        self._total = 0.0

    def sample(self, x: float, y: float) -> None:
        """Feed one (x, y) odometry sample; accumulate honest travel only."""
        here = (float(x), float(y))
        if not (math.isfinite(here[0]) and math.isfinite(here[1])):
            return  # a NaN pose must never poison the metric
        if self._last is None:
            self._last = here
            return
        step = math.hypot(here[0] - self._last[0], here[1] - self._last[1])
        if step > self._max_step:
            self._last = here  # relocalization jump: re-anchor, do not count
            return
        if step < self._min_step:
            return  # noise floor: keep the old anchor so jitter never sums up
        self._total += step
        self._last = here

    @property
    def meters(self) -> float:
        return self._total


class OverlayLauncher:
    """Own ONE nav.sh overlay child (explore/route): spawn, watch, SIGINT.

    ``popen_factory`` is the test seam (defaults to ``subprocess.Popen``);
    everything else is plain process bookkeeping. Thread-safe via one lock —
    tool threads and status polls may race.
    """

    #: extra SIGINT attempts after the first (2 total; then honest failure).
    _SIGINT_RETRIES: int = 1

    def __init__(
        self,
        mode: str,
        nav_sh: str | None = None,
        popen_factory: Callable[..., Any] | None = None,
        log_dir: str | None = None,
    ) -> None:
        self._mode = str(mode)
        raw = nav_sh or os.environ.get("GO2W_NAV_SH", "").strip() or _DEFAULT_NAV_SH
        self._nav_sh = os.path.expanduser(raw)
        self._popen = popen_factory or subprocess.Popen
        self._log_dir = os.path.expanduser(log_dir or _DEFAULT_LOG_DIR)
        self._lock = threading.RLock()
        self._proc: Any = None
        self._stop_requested = False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def pid(self) -> int | None:
        with self._lock:
            return getattr(self._proc, "pid", None) if self._proc is not None else None

    @property
    def stop_requested(self) -> bool:
        with self._lock:
            return self._stop_requested

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def returncode(self) -> int | None:
        with self._lock:
            return self._proc.poll() if self._proc is not None else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def launch(self, *extra_args: str) -> tuple[bool, str]:
        """Spawn ``bash <nav.sh> <mode> [extra...]``; False if one is running."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return False, (
                    f"{self._mode} overlay already running (pid {self._proc.pid})"
                )
            if not os.path.isfile(self._nav_sh):
                return False, (
                    f"nav.sh not found at {self._nav_sh} — set GO2W_NAV_SH"
                )
            argv = ["bash", self._nav_sh, self._mode, *[str(a) for a in extra_args]]
            out = self._open_log()
            try:
                self._proc = self._popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except Exception as exc:  # noqa: BLE001 — spawn boundary, fail loud
                return False, f"failed to spawn {argv[1:]}: {exc}"
            finally:
                if hasattr(out, "close"):
                    try:
                        out.close()  # child holds its own dup; drop ours
                    except Exception:  # noqa: BLE001
                        pass
            self._stop_requested = False
            logger.info("OverlayLauncher: %s (pid %s)", argv, self._proc.pid)
            return True, f"launched {self._mode} overlay (pid {self._proc.pid})"

    def stop(self, grace_s: float = 10.0) -> tuple[bool, int | None]:
        """SIGINT OUR child (1 retry), wait; honest (False, None) if it lingers.

        Never escalates past SIGINT (constitution: only SIGINT processes we
        spawned) — ros2 launch handles SIGINT; a second one triggers launch's
        own shutdown escalation for its nodes.
        """
        with self._lock:
            proc = self._proc
            if proc is None:
                return True, None
            self._stop_requested = True
        for _attempt in range(1 + self._SIGINT_RETRIES):
            if proc.poll() is not None:
                break
            try:
                proc.send_signal(signal.SIGINT)
            except (ProcessLookupError, OSError):
                break  # already gone
            try:
                proc.wait(timeout=grace_s)
                break
            except subprocess.TimeoutExpired:
                continue
        rc = proc.poll()
        if rc is None:
            logger.warning(
                "OverlayLauncher: %s overlay (pid %s) ignored SIGINT x%d",
                self._mode, proc.pid, 1 + self._SIGINT_RETRIES,
            )
            return False, None
        return True, rc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _open_log(self) -> Any:
        """Append-mode log file for the overlay output (DEVNULL fallback)."""
        try:
            os.makedirs(self._log_dir, exist_ok=True)
            path = os.path.join(self._log_dir, f"zeno_{self._mode}_overlay.log")
            return open(path, "ab")  # noqa: SIM115 — handed to Popen, closed after
        except Exception:  # noqa: BLE001 — logging must never block a launch
            return subprocess.DEVNULL
