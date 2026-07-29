# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""manip_transport — run the Z-Mobile-manip ``manip`` operator CLI LOCAL or SSH.

The mobile-manipulation stack is owned by its own repo (``Z-Mobile-manip``); its
component lifecycle is driven through the fixed-surface operator CLI
``scripts/runtime/manip`` (which wraps ``go2w_component_manager.sh`` +
``systemctl --user`` behind an allowlist). This module is the SAME dual-mode seam
as :mod:`~zeno.hardware.ros2.nav_transport`, but for that CLI — so the agent can
start/stop/query the manip vision stack whether z-agent runs ON the 4090 (local)
or drives it over ssh.

There are NO overlays here (the manip CLI drives systemd/docker, not a foreground
``ros2 launch``), so this is strictly the SHORT-COMMAND half of nav_transport.

SAFETY (why this is arm-safe to drive from the agent): the ``manip`` CLI's whole
operator surface — ``start`` / ``stop`` / ``bringup`` / ``status`` / ``logs`` —
can NEVER move the arm. Home and grasp are deliberately UI-only (a human beside
the E-stop). So bringing components up/down through this seam cannot cross the
arm red line by construction.

``GO2W_MANIP_TRANSPORT`` = ``auto`` (default) | ``local`` | ``ssh``:
``auto`` = local iff the CLI path exists on this box, else ssh. Env overrides:
``GO2W_MANIP_CLI`` (local path), ``GO2W_MANIP_CLI_REMOTE`` (remote, literal ``~``
so the REMOTE shell expands it), ``GO2W_MANIP_SSH_HOST`` (required for ssh mode).

No rclpy import here — safe to import with no ROS env (like nav_transport).
"""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any, Callable

#: The manip CLI lives in the sibling Z-Mobile-manip repo checkout.
_DEFAULT_CLI = "~/Z-Robotics-Lab/Z-Mobile-manip/scripts/runtime/manip"

#: Non-interactive ssh: BatchMode never prompts (key auth only); bounded connect.
_SSH_OPTS: tuple[str, ...] = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def local_manip_cli() -> str:
    """The LOCAL manip CLI path (``GO2W_MANIP_CLI`` overrides; ``~`` expanded)."""
    return os.path.expanduser(_env("GO2W_MANIP_CLI", _DEFAULT_CLI))


def remote_manip_cli() -> str:
    """The REMOTE manip CLI path (``GO2W_MANIP_CLI_REMOTE`` overrides).

    Kept with a literal ``~`` — the REMOTE shell expands it (local expansion would
    wrongly resolve to this box's home).
    """
    return _env("GO2W_MANIP_CLI_REMOTE", _DEFAULT_CLI)


def _default_run(argv: list[str], timeout: float) -> Any:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


class ManipTransport:
    """Resolve ``manip <subcmd>`` to an argv, LOCAL subprocess or over ssh."""

    def __init__(
        self,
        mode: str,
        cli: str,
        host: str | None = None,
        runner: Callable[..., Any] | None = None,
    ) -> None:
        self.mode = mode
        self.is_remote = mode == "ssh"
        self._cli = cli
        self._host = host
        self._run = runner or _default_run

    @property
    def cli(self) -> str:
        return self._cli

    @property
    def host(self) -> str | None:
        return self._host

    def preflight(self) -> str | None:
        """Loud pre-run error string if the CLI is unreachable, else None."""
        if self.mode == "local":
            if not os.path.isfile(self._cli):
                return (
                    f"manip CLI not found at {self._cli} — set GO2W_MANIP_CLI to "
                    "the Z-Mobile-manip scripts/runtime/manip path, or "
                    "GO2W_MANIP_TRANSPORT=ssh to drive it remotely"
                )
            return None
        if not self._host:
            return (
                "GO2W_MANIP_SSH_HOST is unset — cannot drive the manip CLI over "
                "ssh; set it, or run z-agent on the host that has the CLI"
            )
        return None

    def command_argv(self, subcmd: str, *args: Any) -> list[str]:
        """``manip <subcmd> [args…]`` as an argv (local bash or ssh remote)."""
        tokens = (subcmd, *args)
        if self.mode == "local":
            return ["bash", self._cli, *[str(t) for t in tokens]]
        # ssh: CLI path UNquoted so the remote shell expands its leading ``~``;
        # every subcommand/arg token shell-quoted.
        remote = " ".join(
            ["bash", self._cli, *[shlex.quote(str(t)) for t in tokens]]
        )
        return ["ssh", *_SSH_OPTS, self._host, remote]

    def describe(self) -> str:
        if self.mode == "local":
            return f"local subprocess (manip={self._cli})"
        return f"ssh {self._host} (remote manip={self._cli})"


def manip_transport(runner: Callable[..., Any] | None = None) -> ManipTransport:
    """Resolve the manip transport from ``GO2W_MANIP_TRANSPORT`` (auto|local|ssh).

    ``auto`` (default) = local iff the local CLI exists on this box, else ssh.
    ``local``/``ssh`` force it.
    """
    mode = _env("GO2W_MANIP_TRANSPORT", "auto").lower()
    host = _env("GO2W_MANIP_SSH_HOST") or None
    if mode == "ssh":
        return ManipTransport("ssh", remote_manip_cli(), host, runner)
    if mode == "local":
        return ManipTransport("local", local_manip_cli(), None, runner)
    # auto
    local = local_manip_cli()
    if os.path.isfile(local):
        return ManipTransport("local", local, None, runner)
    return ManipTransport("ssh", remote_manip_cli(), host, runner)
