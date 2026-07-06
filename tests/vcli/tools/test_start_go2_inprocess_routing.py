# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""D163/D164 C(b): _start_go2 single-sources the in-process Go2 builder.

The acceptance face is the bare `zeno` REPL + NL. There, "启动带手臂的 go2
仿真" routes to SimStartTool._start_go2, which historically ALWAYS launched the
external ROS2 launch_explore.sh stack (MuJoCo + bridge + nav + TARE) as a
subprocess and connected via Go2ROS2Proxy — a path that FAILED fetch/place
(D163). The proven path is the lightweight in-process MuJoCoGo2 builder that
`zeno --sim-go2` uses.

D164 Decision C(b) — HYBRID: repoint the NL launcher at the in-process builder
when VECTOR_NO_ROS2=1, via a SINGLE-SOURCE extraction (Rule 3/11) so cli.py's
--sim-go2 path and sim_tool's NL path resolve to ONE helper and can never drift.
A copy is forbidden. These guards enforce exactly that.
"""
from __future__ import annotations

import inspect
from unittest import mock


def test_inprocess_builder_is_single_sourced() -> None:
    """Both launchers call the ONE canonical builder — proves extraction, not a
    copy (Rule 3/11)."""
    from zeno.hardware.sim import go2_inprocess

    assert hasattr(go2_inprocess, "build_inprocess_go2_agent"), (
        "the single-source in-process Go2 builder must live in "
        "hardware/sim/go2_inprocess.py"
    )

    from zeno.vcli import cli
    from zeno.vcli.tools import sim_tool

    cli_src = inspect.getsource(cli._init_agent)
    sim_src = inspect.getsource(sim_tool.SimStartTool._start_go2)
    assert "build_inprocess_go2_agent" in cli_src, (
        "cli._init_agent must build the in-process Go2 via the shared helper"
    )
    assert "build_inprocess_go2_agent" in sim_src, (
        "sim_tool._start_go2 must build the in-process Go2 via the shared helper"
    )


def test_start_go2_no_ros2_uses_inprocess_builder_and_never_spawns_stack(
    monkeypatch,
) -> None:
    """With VECTOR_NO_ROS2=1, _start_go2 returns the in-process agent from the
    shared builder and NEVER spawns the launch_explore.sh subprocess."""
    monkeypatch.setenv("VECTOR_NO_ROS2", "1")

    sentinel = object()
    calls: dict = {}

    def fake_builder(**kwargs):
        calls.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "zeno.hardware.sim.go2_inprocess.build_inprocess_go2_agent",
        fake_builder,
    )

    from zeno.vcli.tools import sim_tool

    with mock.patch("subprocess.Popen") as popen:
        agent = sim_tool.SimStartTool._start_go2(gui=False, with_arm=True)

    assert agent is sentinel, "must return the in-process builder's agent"
    popen.assert_not_called()  # NO ROS2 launch_explore.sh subprocess
    assert calls.get("with_arm") is True, "with_arm must be forwarded"


def test_start_go2_default_still_launches_ros2_stack(monkeypatch) -> None:
    """Byte-compat guard: without VECTOR_NO_ROS2, the ROS2-stack path is
    preserved (deferred/deep — we assert it does NOT early-return to the
    in-process builder, keeping the real-robot path alive for explore/nav)."""
    monkeypatch.delenv("VECTOR_NO_ROS2", raising=False)

    called = {"builder": False}

    def fake_builder(**kwargs):
        called["builder"] = True
        return object()

    monkeypatch.setattr(
        "zeno.hardware.sim.go2_inprocess.build_inprocess_go2_agent",
        fake_builder,
    )

    from zeno.vcli.tools import sim_tool

    # subprocess.Popen raising short-circuits the heavy ROS2 path immediately so
    # the test never actually launches the stack or sleeps 20s.
    with mock.patch("subprocess.Popen", side_effect=RuntimeError("stop")):
        try:
            sim_tool.SimStartTool._start_go2(gui=False, with_arm=False)
        except RuntimeError:
            pass

    assert called["builder"] is False, (
        "default path must NOT route to the in-process builder — ROS2 stack "
        "path is preserved (D164 C: (a) preserved-deferred)"
    )
