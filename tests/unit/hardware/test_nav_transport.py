# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""nav_transport — LOCAL vs SSH nav.sh execution seam (pure-unit, no real ssh).

Ground truth is the COMMAND CONTRACT each transport must honor:

* local — ``bash <nav.sh> …`` argv, exactly as before this module existed; the
  nav host is this box so RViz can open here (``opens_local_gui``);
* ssh   — ``ssh <opts> <host> 'bash <remote-nav.sh> …'``; the remote nav.sh keeps
  a literal ``~`` (the REMOTE shell expands it); overlays record the remote
  ros2-launch PID to a pidfile so teardown is a TARGETED ``ssh <host> kill -INT
  <pid>`` (never the local ssh, never pkill); RViz is refused (headless NUC).

The ssh transport's subprocess seam is injected, so NO real ssh ever runs.
"""

from __future__ import annotations

import signal
from types import SimpleNamespace
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# import contract
# ---------------------------------------------------------------------------


def test_module_imports_without_ros_env() -> None:
    from zeno.hardware.ros2.nav_transport import (
        NavTransport, SshNavTransport, nav_transport)

    assert NavTransport is not None
    assert SshNavTransport is not None
    assert nav_transport is not None


# ---------------------------------------------------------------------------
# factory resolution — GO2W_NAV_TRANSPORT = auto | local | ssh
# ---------------------------------------------------------------------------


def test_factory_local_is_forced(monkeypatch, tmp_path) -> None:
    from zeno.hardware.ros2.nav_transport import NavTransport, nav_transport

    monkeypatch.setenv("GO2W_NAV_TRANSPORT", "local")
    t = nav_transport(str(tmp_path / "nav.sh"))
    assert isinstance(t, NavTransport) and t.mode == "local"
    assert t.is_remote is False


def test_factory_ssh_is_forced(monkeypatch) -> None:
    from zeno.hardware.ros2.nav_transport import SshNavTransport, nav_transport

    monkeypatch.setenv("GO2W_NAV_TRANSPORT", "ssh")
    t = nav_transport()
    assert isinstance(t, SshNavTransport) and t.mode == "ssh"
    assert t.is_remote is True


def test_auto_picks_local_when_navsh_exists(monkeypatch, tmp_path) -> None:
    from zeno.hardware.ros2.nav_transport import nav_transport

    nav = tmp_path / "nav.sh"
    nav.write_text("#!/usr/bin/env bash\n")
    monkeypatch.setenv("GO2W_NAV_TRANSPORT", "auto")
    t = nav_transport(str(nav))
    assert t.mode == "local"
    assert t.nav_sh == str(nav)


def test_auto_falls_back_to_ssh_when_navsh_missing(monkeypatch, tmp_path) -> None:
    from zeno.hardware.ros2.nav_transport import nav_transport

    monkeypatch.setenv("GO2W_NAV_TRANSPORT", "auto")
    t = nav_transport(str(tmp_path / "does-not-exist.sh"))
    assert t.mode == "ssh"


def test_default_unset_is_auto(monkeypatch, tmp_path) -> None:
    """No env var at all behaves as auto (missing local nav.sh -> ssh)."""
    from zeno.hardware.ros2.nav_transport import nav_transport

    monkeypatch.delenv("GO2W_NAV_TRANSPORT", raising=False)
    assert nav_transport(str(tmp_path / "nope.sh")).mode == "ssh"


# ---------------------------------------------------------------------------
# LOCAL transport — argv shape / preflight / interrupt / gui
# ---------------------------------------------------------------------------


def _local(tmp_path, exists: bool = True):
    from zeno.hardware.ros2.nav_transport import NavTransport

    nav = tmp_path / "nav.sh"
    if exists:
        nav.write_text("#!/usr/bin/env bash\n")
    return NavTransport(str(nav)), str(nav)


def test_local_command_argv_is_plain_bash(tmp_path) -> None:
    t, nav = _local(tmp_path)
    assert t.command_argv("status") == ["bash", nav, "status"]
    assert t.command_argv("start", "zeno_office") == \
        ["bash", nav, "start", "zeno_office"]


def test_local_preflight_flags_missing_navsh(tmp_path) -> None:
    t, nav = _local(tmp_path, exists=False)
    err = t.preflight()
    assert err is not None and "nav.sh" in err and nav in err


def test_local_preflight_ok_when_present(tmp_path) -> None:
    t, _nav = _local(tmp_path, exists=True)
    assert t.preflight() is None


def test_local_overlay_argv_drops_empty_mode(tmp_path) -> None:
    t, nav = _local(tmp_path)
    h = t.new_overlay_handle()
    assert t.overlay_argv(nav, "explore", h, "indoor_small") == \
        ["bash", nav, "explore", "indoor_small"]
    # a standalone-script overlay (empty mode) is just ['bash', <script>]
    assert t.overlay_argv(nav, "", h) == ["bash", nav]


def test_local_overlay_interrupt_sigints_the_child(tmp_path) -> None:
    t, _nav = _local(tmp_path)
    sent: list[int] = []
    proc = SimpleNamespace(send_signal=lambda s: sent.append(s))
    t.overlay_interrupt(proc, t.new_overlay_handle())
    assert sent == [signal.SIGINT]


def test_local_opens_local_gui(tmp_path) -> None:
    t, _nav = _local(tmp_path)
    assert t.opens_local_gui is True


# ---------------------------------------------------------------------------
# SSH transport — remote argv / pidfile teardown / gui refusal
# ---------------------------------------------------------------------------


class _FakeRunner:
    """Records every subprocess argv the ssh transport runs; scripts a result."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self._stdout = stdout
        self._rc = returncode

    def __call__(self, argv: list[str], timeout: float) -> Any:  # noqa: ARG002
        self.calls.append(list(argv))
        return SimpleNamespace(returncode=self._rc, stdout=self._stdout, stderr="")


def _ssh(host: str = "go2w-nuc", nav_sh: str = "~/go2w-nuc/scripts/nav.sh",
         runner: _FakeRunner | None = None):
    from zeno.hardware.ros2.nav_transport import SshNavTransport

    return SshNavTransport(host=host, nav_sh=nav_sh, runner=runner or _FakeRunner())


def test_ssh_command_argv_is_a_single_remote_bash_string() -> None:
    t = _ssh()
    argv = t.command_argv("start", "zeno_office")
    assert argv[0] == "ssh"
    assert "BatchMode=yes" in argv          # never prompts for a password
    assert "go2w-nuc" in argv
    # the whole nav.sh invocation is ONE remote command string (last element)
    assert argv[-1] == "bash ~/go2w-nuc/scripts/nav.sh start zeno_office"


def test_ssh_keeps_tilde_unquoted_for_remote_expansion() -> None:
    """A quoted ``~`` would not expand on the remote — the path must stay bare."""
    t = _ssh()
    remote = t.command_argv("status")[-1]
    assert remote.startswith("bash ~/go2w-nuc/scripts/nav.sh")
    assert "'~" not in remote and '"~' not in remote


def test_ssh_preflight_is_none() -> None:
    # remote presence is assumed; a failed remote command reports honestly.
    assert _ssh().preflight() is None


def test_ssh_is_remote_and_refuses_local_gui() -> None:
    t = _ssh()
    assert t.is_remote is True
    assert t.opens_local_gui is False


def test_ssh_overlay_argv_records_pid_then_execs() -> None:
    t = _ssh()
    handle = t.new_overlay_handle()
    argv = t.overlay_argv("~/go2w-nuc/scripts/nav.sh", "explore", handle,
                          "indoor_small")
    assert argv[0] == "ssh"
    assert "ServerAliveInterval=15" in argv   # dead-peer detection on the child
    remote = argv[-1]
    # write the ros2-launch PID ($$ survives the exec chain) THEN exec the overlay
    assert remote.startswith(f"echo $$ > {handle.pidfile}; exec ")
    assert "exec bash ~/go2w-nuc/scripts/nav.sh explore indoor_small" in remote


def test_ssh_overlay_interrupt_kills_remote_pid_targeted() -> None:
    runner = _FakeRunner()
    t = _ssh(runner=runner)
    handle = t.new_overlay_handle()
    proc = SimpleNamespace()  # ssh teardown never touches the local ssh proc
    t.overlay_interrupt(proc, handle)
    assert len(runner.calls) == 1
    remote = runner.calls[0][-1]
    # TARGETED SIGINT to the exact remote PID (NEVER-KILL-INFRA: no pkill/SIGKILL)
    assert "kill -INT" in remote
    assert handle.pidfile in remote
    assert "pkill" not in remote and "-9" not in remote


def test_ssh_overlay_interrupt_noops_without_handle() -> None:
    runner = _FakeRunner()
    _ssh(runner=runner).overlay_interrupt(SimpleNamespace(), None)
    assert runner.calls == []


def test_ssh_resident_probe_reads_remote_pgrep() -> None:
    from zeno.hardware.ros2.nav_transport import SshNavTransport

    yes = SshNavTransport(runner=_FakeRunner(stdout="YES\n"))
    no = SshNavTransport(runner=_FakeRunner(stdout="NO\n"))
    assert yes.resident_far_planner() is True
    assert no.resident_far_planner() is False


def test_ssh_host_and_navsh_come_from_env(monkeypatch) -> None:
    from zeno.hardware.ros2.nav_transport import SshNavTransport

    monkeypatch.setenv("GO2W_NAV_SSH_HOST", "robodog")
    monkeypatch.setenv("GO2W_NAV_SH_REMOTE", "~/custom/nav.sh")
    t = SshNavTransport()
    assert t.host == "robodog"
    assert t.command_argv("status")[-1] == "bash ~/custom/nav.sh status"
