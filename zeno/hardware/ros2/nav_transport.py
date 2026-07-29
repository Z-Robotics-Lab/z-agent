# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""nav_transport — run the Go2W nav.sh lifecycle LOCAL or over SSH, one seam.

The nav stack lives on the robot's NUC. Two deployment shapes must both work
from the SAME code (product requirement: the NUC can run standalone, and the
4090 workstation can drive it remotely):

* **local** — nav.sh is on THIS machine (the NUC itself). Every subcommand is a
  plain ``bash <nav.sh> …`` subprocess, exactly as before this module existed.
* **ssh** — nav.sh is on the NUC and we drive it from the 4090 over ssh. nav.sh
  ``start`` launches a ``systemd-run --user`` TRANSIENT UNIT, so the unit keeps
  running on the NUC after the short ssh command returns — ssh short-connections
  are the natural fit. ``stop``/``status``/``up``/``down`` are likewise short.

Selection is ``GO2W_NAV_TRANSPORT`` = ``auto`` (default) | ``local`` | ``ssh``:
``auto`` = local iff ``~/go2w-nuc/scripts/nav.sh`` exists on this box, else ssh.
The ssh host is ``GO2W_NAV_SSH_HOST`` (default ``go2w-nuc``); the remote nav.sh
path is ``GO2W_NAV_SH_REMOTE`` (default ``~/go2w-nuc/scripts/nav.sh``, kept with a
literal ``~`` so the REMOTE shell expands it).

TWO command shapes, one transport:

* **short commands** (``command_argv`` — start/stop/status/up/down, for
  ``subprocess.run``): idempotent, non-blocking, return promptly.
* **overlays** (``overlay_argv`` + ``overlay_interrupt`` — explore/route, spawned
  by :class:`~zeno.hardware.ros2.go2w_hw_overlay.OverlayLauncher` as a FOREGROUND
  child): nav.sh's explore/route ``exec ros2 launch`` in the foreground (NOT a
  transient unit — confirmed by reading nav.sh), torn down with SIGINT ONLY.
  - local: SIGINT the child we spawned (``ros2 launch`` tears its nodes down).
  - ssh:  the child is the ssh client; SIGINT-ing IT would orphan the remote
    nodes. Instead the remote command records the ros2-launch PID to a pidfile
    and teardown does ``ssh <host> kill -INT <pid>`` — a TARGETED SIGINT to the
    exact process we started (NEVER-KILL-INFRA: no pkill, no name matching, no
    SIGKILL escalation).

GUI (RViz) runs on the nav host's screen: legitimate in local mode (the nav host
is this workstation) but useless over ssh (the NUC is headless). ``opens_local_gui``
lets the viz layer refuse a remote RViz and point the operator at Foxglove/RViz
on the 4090 instead (topics are already bridged over DDS domain 20).

No rclpy import here — safe to import with no ROS env (like go2w_hw_overlay).
"""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from typing import Any, Callable

_DEFAULT_NAV_SH = "~/go2w-nuc/scripts/nav.sh"
_DEFAULT_SSH_HOST = "go2w-nuc"

#: Non-interactive ssh: BatchMode never prompts (key auth only — a missing key
#: fails fast instead of hanging a turn on a password prompt); bounded connect.
_SSH_OPTS: tuple[str, ...] = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
#: A long-lived FOREGROUND overlay child additionally needs dead-peer detection
#: so a network drop surfaces as the child exiting (liveness proxy stays honest).
_SSH_OVERLAY_OPTS: tuple[str, ...] = (
    "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def local_nav_sh() -> str:
    """The LOCAL nav.sh path (env ``GO2W_NAV_SH`` overrides; ``~`` expanded here)."""
    return os.path.expanduser(_env("GO2W_NAV_SH", _DEFAULT_NAV_SH))


def remote_nav_sh() -> str:
    """The REMOTE nav.sh path on the NUC (env ``GO2W_NAV_SH_REMOTE`` overrides).

    Kept with a literal ``~`` — the REMOTE shell expands it. Local expansion
    would wrongly resolve to the 4090's home.
    """
    return _env("GO2W_NAV_SH_REMOTE", _DEFAULT_NAV_SH)


def ssh_host() -> str:
    return _env("GO2W_NAV_SSH_HOST", _DEFAULT_SSH_HOST)


def _default_run(argv: list[str], timeout: float) -> Any:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


class _SshOverlayHandle:
    """Per-launch teardown token for an ssh overlay: the remote PID's pidfile."""

    __slots__ = ("pidfile",)

    def __init__(self, pidfile: str) -> None:
        self.pidfile = pidfile


class NavTransport:
    """LOCAL transport — nav.sh runs as a subprocess on THIS machine."""

    mode: str = "local"
    is_remote: bool = False
    #: The nav host IS this box, so its screen is here — a local RViz is visible.
    opens_local_gui: bool = True

    def __init__(self, nav_sh: str | None = None) -> None:
        self._nav_sh = os.path.expanduser(nav_sh) if nav_sh else local_nav_sh()

    @property
    def nav_sh(self) -> str:
        return self._nav_sh

    # -- short commands (start/stop/status/up/down) ----------------------------

    def preflight(self) -> str | None:
        """Loud pre-run error string if nav.sh is unreachable, else None."""
        if not os.path.isfile(self._nav_sh):
            return (f"nav.sh not found at {self._nav_sh} — set GO2W_NAV_SH to the "
                    "nav.sh path, or GO2W_NAV_TRANSPORT=ssh to drive the NUC "
                    "remotely")
        return None

    def command_argv(self, subcmd: str, *args: Any) -> list[str]:
        return ["bash", self._nav_sh, str(subcmd), *[str(a) for a in args]]

    # -- overlays (explore/route foreground children) --------------------------

    def new_overlay_handle(self) -> Any:
        return None

    def overlay_preflight(self, script: str) -> str | None:
        path = os.path.expanduser(script)
        if not os.path.isfile(path):
            return f"nav.sh not found at {path} — set GO2W_NAV_SH"
        return None

    def overlay_argv(self, script: str, mode: str, handle: Any,
                     *extra: Any) -> list[str]:
        argv = ["bash", os.path.expanduser(script)]
        if mode:
            argv.append(str(mode))
        argv.extend(str(a) for a in extra)
        return argv

    def overlay_interrupt(self, proc: Any, handle: Any) -> None:
        """SIGINT the child we spawned (ros2 launch tears its nodes down)."""
        proc.send_signal(signal.SIGINT)

    # -- misc ------------------------------------------------------------------

    def resident_far_planner(self) -> bool:
        """True if a far_planner is already running on the nav host (best-effort)."""
        try:
            r = _default_run(["pgrep", "-f", "far_planner"], timeout=3)
            return r.returncode == 0 and bool((r.stdout or "").strip())
        except Exception:  # noqa: BLE001 — probe failure = assume not resident
            return False

    def describe(self) -> str:
        return f"local subprocess (nav.sh={self._nav_sh})"


class SshNavTransport(NavTransport):
    """SSH transport — nav.sh runs on the NUC, driven from this box over ssh."""

    mode = "ssh"
    is_remote = True
    #: The NUC is headless — a remote RViz has no screen. Viz points at the 4090.
    opens_local_gui = False

    def __init__(self, host: str | None = None, nav_sh: str | None = None,
                 runner: Callable[..., Any] | None = None) -> None:
        self._host = host or ssh_host()
        self._nav_sh = nav_sh or remote_nav_sh()   # literal ~ (remote expands)
        self._run = runner or _default_run

    @property
    def host(self) -> str:
        return self._host

    def _ssh_argv(self, remote: str, *, overlay: bool = False) -> list[str]:
        opts = list(_SSH_OPTS)
        if overlay:
            opts += list(_SSH_OVERLAY_OPTS)
        return ["ssh", *opts, self._host, remote]

    @staticmethod
    def _remote_cmd(script: str, tokens: tuple[Any, ...]) -> str:
        """``bash <script> <tok…>`` — script UNquoted so the remote shell expands
        its leading ``~``; every other token shell-quoted (map names etc.)."""
        parts = ["bash", script]
        parts += [shlex.quote(str(t)) for t in tokens]
        return " ".join(parts)

    # -- short commands --------------------------------------------------------

    def preflight(self) -> str | None:
        # Remote presence is assumed; a failed remote command surfaces its own
        # error honestly (no per-call ssh round-trip just to stat the file).
        return None

    def command_argv(self, subcmd: str, *args: Any) -> list[str]:
        return self._ssh_argv(self._remote_cmd(self._nav_sh, (subcmd, *args)))

    # -- overlays --------------------------------------------------------------

    def new_overlay_handle(self) -> Any:
        token = f"{os.getpid()}-{time.monotonic_ns()}"
        return _SshOverlayHandle(f"/tmp/zeno-nav-overlay-{token}.pid")

    def overlay_preflight(self, script: str) -> str | None:
        return None

    def overlay_argv(self, script: str, mode: str, handle: Any,
                     *extra: Any) -> list[str]:
        tokens: tuple[Any, ...] = ((mode, *extra) if mode else tuple(extra))
        inner = self._remote_cmd(script, tokens)
        # Record the ros2-launch PID ($$ survives the exec chain: bash-nav.sh
        # exec's ros2 launch, same PID) to a pidfile, THEN exec the overlay — so
        # teardown can `kill -INT` exactly that PID on the NUC.
        pidfile = handle.pidfile if isinstance(handle, _SshOverlayHandle) else \
            "/tmp/zeno-nav-overlay-fallback.pid"
        remote = f"echo $$ > {pidfile}; exec {inner}"
        return self._ssh_argv(remote, overlay=True)

    def overlay_interrupt(self, proc: Any, handle: Any) -> None:
        """TARGETED SIGINT to the REMOTE ros2 launch (never the local ssh).

        Signalling the local ssh client would orphan the remote nodes instead of
        letting ros2 launch shut them down; kill -INT <pid> on the NUC delivers
        the exact SIGINT the local path delivers. NEVER-KILL-INFRA: one PID we
        spawned, no pkill, no SIGKILL. Best-effort — a failure leaves the honest
        "still running" report to OverlayLauncher (which waits on the child).
        """
        if not isinstance(handle, _SshOverlayHandle):
            return
        pf = handle.pidfile
        remote = (f"P=$(cat {pf} 2>/dev/null); "
                  f'[ -n "$P" ] && kill -INT "$P" 2>/dev/null; '
                  f"rm -f {pf} 2>/dev/null; true")
        try:
            self._run(self._ssh_argv(remote), timeout=15)
        except Exception:  # noqa: BLE001 — teardown signal is best-effort
            pass

    # -- misc ------------------------------------------------------------------

    def resident_far_planner(self) -> bool:
        try:
            r = self._run(
                self._ssh_argv("pgrep -f far_planner >/dev/null 2>&1 && "
                               "echo YES || echo NO"),
                timeout=10)
            return "YES" in (getattr(r, "stdout", "") or "")
        except Exception:  # noqa: BLE001 — probe failure = assume not resident
            return False

    def describe(self) -> str:
        return f"ssh {self._host} (remote nav.sh={self._nav_sh})"


def nav_transport(nav_sh_hint: str | None = None,
                  runner: Callable[..., Any] | None = None) -> NavTransport:
    """Resolve the nav transport from ``GO2W_NAV_TRANSPORT`` (auto|local|ssh).

    ``auto`` (default) = local iff the local nav.sh (hint / GO2W_NAV_SH / default)
    exists on this box, else drive the NUC over ssh. ``local``/``ssh`` force it.
    """
    mode = _env("GO2W_NAV_TRANSPORT", "auto").lower()
    if mode == "ssh":
        return SshNavTransport(runner=runner)
    if mode == "local":
        return NavTransport(nav_sh_hint)
    # auto
    local = os.path.expanduser(nav_sh_hint) if nav_sh_hint else local_nav_sh()
    if os.path.isfile(local):
        return NavTransport(local)
    return SshNavTransport(runner=runner)
