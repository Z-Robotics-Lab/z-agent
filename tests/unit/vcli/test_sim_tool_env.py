"""Runtime-identity fidelity: the NL (bare-REPL) sim path honours ZENO_ env vars.

Constitution Invariant #2: the acceptance face is the bare `zeno` REPL + natural
language. On that face the user starts a sim with NL ("启动带手臂的 go2 仿真")
and configures it with env vars. .env.example advertises ZENO_SIM_WITH_ARM /
ZENO_NO_ROS2 as honoured. Before this fix only the --sim-go2 FLAG path read
ZENO_-first; the NL path read the raw VECTOR_ names (mujoco_go2:441 /
sim_tool:490 / go2_inprocess:108) so ``export ZENO_SIM_WITH_ARM=1`` on the
product face silently did nothing (a DOC↔RUNTIME fidelity gap).

These tests pin the three-cell matrix (ZENO-only / VECTOR-only / both) at the
scene-selection and NL-routing seams. Fully offline — ``build_room_scene`` and
the in-process builder are stubbed; no MuJoCo, no ROS2, no network.
"""
from __future__ import annotations

from unittest import mock

import pytest


# ---- mujoco_go2._build_room_scene_xml reads SIM_WITH_ARM (ZENO_-first) ----

def _capture_scene_arm(monkeypatch: pytest.MonkeyPatch) -> bool:
    """Call _build_room_scene_xml(with_arm=None) with build_room_scene stubbed;
    return whether the ARM (piper) robot xml was selected — i.e. with_arm resolved
    True from the env, without spawning anything."""
    from zeno.hardware.sim import mujoco_go2

    captured: dict = {}

    def fake_build_room_scene(*, robot_model_path, **kwargs):  # noqa: ANN001
        captured["robot_model_path"] = robot_model_path
        return (object(), robot_model_path)

    monkeypatch.setattr(
        "zeno.hardware.sim.scene_builder.build_room_scene", fake_build_room_scene
    )
    mujoco_go2._build_room_scene_xml(with_arm=None)
    return captured["robot_model_path"] == mujoco_go2._GO2_PIPER_XML


@pytest.fixture(autouse=True)
def _clear_arm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ZENO_SIM_WITH_ARM", "VECTOR_SIM_WITH_ARM",
                 "ZENO_NO_ROS2", "VECTOR_NO_ROS2"):
        monkeypatch.delenv(name, raising=False)


def test_scene_arm_from_zeno_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZENO_SIM_WITH_ARM=1 alone (no VECTOR_) attaches the arm — the fix."""
    monkeypatch.setenv("ZENO_SIM_WITH_ARM", "1")
    assert _capture_scene_arm(monkeypatch) is True


def test_scene_arm_from_vector_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy VECTOR_SIM_WITH_ARM=1 alone still attaches the arm (fallback kept)."""
    monkeypatch.setenv("VECTOR_SIM_WITH_ARM", "1")
    assert _capture_scene_arm(monkeypatch) is True


def test_scene_arm_zeno_wins_over_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZENO_ wins: ZENO_=1 with VECTOR_=0 -> arm on."""
    monkeypatch.setenv("ZENO_SIM_WITH_ARM", "1")
    monkeypatch.setenv("VECTOR_SIM_WITH_ARM", "0")
    assert _capture_scene_arm(monkeypatch) is True


def test_scene_no_arm_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither set -> bare go2 (default 0)."""
    assert _capture_scene_arm(monkeypatch) is False


# ---- go2_inprocess mirrors the arm choice to BOTH env names ----

def test_inprocess_mirrors_arm_to_both_env_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_inprocess_go2_agent writes ZENO_ (primary) AND VECTOR_ (mirror) so an
    un-migrated downstream reader still sees the arm choice."""
    import os

    # monkeypatch.setenv registers the vars so any write inside the builder is
    # rolled back at teardown (the builder writes to the real os.environ).
    monkeypatch.setenv("ZENO_SIM_WITH_ARM", "sentinel")
    monkeypatch.setenv("VECTOR_SIM_WITH_ARM", "sentinel")

    from zeno.hardware.sim import go2_inprocess

    # Stub the heavy build so we only exercise the env-write contract.
    with mock.patch.object(go2_inprocess, "reconcile_render_backend", lambda g: g), \
         mock.patch("zeno.core.agent.Agent"), \
         mock.patch("zeno.hardware.sim.mujoco_go2.MuJoCoGo2") as MockBase:
        MockBase.return_value.connect.return_value = None
        try:
            go2_inprocess.build_inprocess_go2_agent(with_arm=True)
        except Exception:
            # We only care that the env write happened before any failure point.
            pass
        assert os.environ.get("ZENO_SIM_WITH_ARM") == "1"
        assert os.environ.get("VECTOR_SIM_WITH_ARM") == "1"


# ---- sim_tool NL path honours ZENO_NO_ROS2 (in-process, no stack) ----

def test_start_go2_no_ros2_from_zeno_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZENO_NO_ROS2=1 alone routes the NL launcher to the in-process builder and
    never spawns the launch_explore.sh stack — same as the legacy VECTOR_ path."""
    monkeypatch.setenv("ZENO_NO_ROS2", "1")

    from zeno.vcli.tools import sim_tool

    sentinel = object()
    calls: dict = {}

    def fake_builder(**kwargs):  # noqa: ANN003
        calls["called"] = True
        return sentinel

    monkeypatch.setattr(
        "zeno.hardware.sim.go2_inprocess.build_inprocess_go2_agent", fake_builder
    )

    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("must NOT spawn the ROS2 launch_explore.sh stack")

    monkeypatch.setattr("subprocess.Popen", _boom)

    tool = sim_tool.SimStartTool()
    result = tool._start_go2(with_arm=False)
    assert calls.get("called") is True
    assert result is sentinel
