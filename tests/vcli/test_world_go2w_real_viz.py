# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real viz tool + capability-md persona — product-face contracts.

The agent must be able to bring up RViz itself (non-blocking overlay child) and
must load its self-knowledge from ``go2w_real_capabilities.md`` so capabilities
are editable without touching code.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tests.unit.hardware.test_go2w_hw_overlay import FakePopenFactory, FakeProc


def _nav_sh(tmp_path: Path) -> str:
    p = tmp_path / "nav.sh"
    p.write_text("#!/usr/bin/env bash\n")
    return str(p)


def _tool(tmp_path: Path, factory: FakePopenFactory | None = None):
    from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool
    return Go2WRealVizTool(
        popen_factory=factory or FakePopenFactory(),
        nav_sh=_nav_sh(tmp_path))


def _run(tool, **params):
    return tool.execute(params, SimpleNamespace(agent=None))


# ---------------------------------------------------------------------------
# viz tool
# ---------------------------------------------------------------------------


def test_viz_open_launches_rviz_overlay_nonblocking(tmp_path):
    factory = FakePopenFactory()
    tool = _tool(tmp_path, factory)
    result = _run(tool, action="open")
    assert not result.is_error
    assert "rviz" in result.content.lower()
    (argv, _kwargs), = factory.calls
    assert argv[0] == "bash"
    assert argv[1].endswith("nav.sh")
    assert argv[2] == "rviz"


def test_viz_views_map_to_nav_sh_modes(tmp_path):
    factory = FakePopenFactory()
    tool = _tool(tmp_path, factory)
    assert not _run(tool, action="open", view="explore").is_error
    modes = [argv[2] for argv, _ in factory.calls]
    assert modes == ["rviz-explore"]
    # route view now maps to the MAIN 'rviz' mode: far_planner's displays were
    # merged into vehicle_simulator.rviz (2026-07-15), so there is no separate
    # rviz-route overlay. Fresh tool (FakePopenFactory shares one proc).
    factory2 = FakePopenFactory()
    tool2 = _tool(tmp_path, factory2)
    assert not _run(tool2, action="open", view="route").is_error
    assert [argv[2] for argv, _ in factory2.calls] == ["rviz"]


def test_viz_double_open_reports_already_running(tmp_path):
    tool = _tool(tmp_path)
    _run(tool, action="open")
    result = _run(tool, action="open")
    assert not result.is_error
    assert "already" in result.content.lower()


def test_viz_close_stops_children(tmp_path):
    factory = FakePopenFactory(FakeProc(exits_on_sigint=1))
    tool = _tool(tmp_path, factory)
    _run(tool, action="open")
    result = _run(tool, action="close")
    assert not result.is_error
    launcher = tool._launchers["rviz"]  # noqa: SLF001
    assert launcher.stop_requested
    assert not launcher.is_running()


def test_viz_close_when_nothing_open_is_not_an_error(tmp_path):
    result = _run(_tool(tmp_path), action="close")
    assert not result.is_error


def test_viz_unknown_action_errors(tmp_path):
    assert _run(_tool(tmp_path), action="teleport").is_error


# ---------------------------------------------------------------------------
# workstation-local RViz (ssh transport: nav host = headless NUC, window on 4090)
#
# Phase-2 stub replacement (CEO-authorized 2026-07-29): under ssh the earlier code
# returned a "go connect Foxglove yourself" pointer; now an RViz view opens LOCALLY
# on the workstation (the 4090), subscribing over DDS domain 20.
# ---------------------------------------------------------------------------


def _ssh_session(factory: FakePopenFactory | None = None):
    """A VizOverlaySession forced onto the ssh transport (nav host = headless NUC)."""
    from zeno.hardware.ros2.nav_transport import SshNavTransport
    from zeno.vcli.worlds.go2w_real_viz_tools import VizOverlaySession

    return VizOverlaySession(
        popen_factory=factory or FakePopenFactory(),
        transport=SshNavTransport(host="go2w-nuc"))


def test_workstation_ssh_open_launches_local_rviz2(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    factory = FakePopenFactory()
    status, _detail = _ssh_session(factory).open("main")
    assert status == "opened_workstation"
    (argv, kwargs), = factory.calls
    # rviz2 is spawned HERE, sourcing the workstation DDS env, with the main config.
    assert argv[0] == "bash" and argv[1] == "-c"
    cmd = argv[2]
    assert "rviz2 -d" in cmd
    assert "vehicle_simulator.rviz" in cmd  # main/route config
    assert "ros_env.sh" in cmd  # sources RMW=cyclonedds + ROS_DOMAIN_ID=20 profile
    # detached: a REPL Ctrl+C / exit must never take RViz with it.
    assert kwargs.get("start_new_session") is True


def test_workstation_explore_uses_tare_config(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    factory = FakePopenFactory()
    status, _ = _ssh_session(factory).open("explore")
    assert status == "opened_workstation"
    (argv, _kwargs), = factory.calls
    assert "tare_planner_ground.rviz" in argv[2]


def test_workstation_route_dedupes_with_main(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    factory = FakePopenFactory()
    session = _ssh_session(factory)
    assert session.open("main")[0] == "opened_workstation"
    status, _ = session.open("route")
    # route shares the 'rviz' mode with main -> already open, NOT a second window.
    assert status == "already_open"
    assert len(factory.calls) == 1


def test_workstation_no_display_degrades_to_foxglove(monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    factory = FakePopenFactory()
    status, detail = _ssh_session(factory).open("main")
    # No X here -> honest Foxglove pointer, never a doomed window spawn.
    assert status == "remote_gui"
    assert "Foxglove" in detail
    assert factory.calls == []


def test_workstation_3d_view_stays_foxglove_pointer(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    factory = FakePopenFactory()
    # The 3D View3D (Foxglove) stream is built on the NUC — under ssh it keeps its
    # honest pointer (option preserved), it does NOT spawn a local process.
    status, detail = _ssh_session(factory).open("3d")
    assert status == "remote_gui"
    assert "Foxglove" in detail
    assert factory.calls == []


def test_workstation_missing_config_is_honest_error(monkeypatch, tmp_path):
    monkeypatch.setenv("DISPLAY", ":1")
    monkeypatch.setenv("ZENO_NAV_STACK_REPO", str(tmp_path))  # no rviz configs here
    factory = FakePopenFactory()
    status, detail = _ssh_session(factory).open("main")
    assert status == "error"
    assert "rviz config not found" in detail
    assert factory.calls == []  # preflight failed before any spawn


def test_workstation_tool_message_says_opened_on_workstation(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool

    session = _ssh_session()
    result = Go2WRealVizTool().execute(
        {"action": "open", "view": "main"},
        SimpleNamespace(agent=SimpleNamespace(_viz=session)))
    assert not result.is_error
    assert "已在工作站打开 RViz(main)" in result.content


def test_workstation_skill_message_says_opened_on_workstation(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":1")
    from zeno.vcli.worlds.go2w_real_ops_skills import RealVizSkill

    session = _ssh_session()
    ctx = SimpleNamespace(services={"viz": session}, instruction="打开rviz")
    res = RealVizSkill().execute({"view": "main"}, ctx)
    assert res.success
    assert "已在工作站打开 RViz(main)" in res.result_data["message"]


# ---------------------------------------------------------------------------
# capability md -> persona
# ---------------------------------------------------------------------------


def _md_path() -> Path:
    import zeno.vcli.worlds.go2w_real as w
    return Path(w.__file__).with_name("go2w_real_capabilities.md")


def test_capability_md_exists_and_has_split_marker():
    text = _md_path().read_text(encoding="utf-8")
    assert "<!-- persona-split -->" in text
    # the agent's safety floor and its primary tools must be documented
    for needle in ("go2w_real_bringup", "go2w_real_stop", "E-stop",
                   "go2w_real_explore", "go2w_real_viz"):
        assert needle in text, f"capability md must document {needle}"


def test_persona_blocks_come_from_capability_md():
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld
    text = _md_path().read_text(encoding="utf-8")
    head, tail = text.split("<!-- persona-split -->", 1)
    block1, block2 = Go2WRealWorld().persona_blocks()
    assert block1.strip() == head.strip()
    assert block2.strip() == tail.strip()


def test_persona_survives_missing_md(tmp_path, monkeypatch):
    # deleting the md must degrade to a safe minimal persona, never crash
    import zeno.vcli.worlds.go2w_real as w
    monkeypatch.setattr(
        w, "_CAPABILITIES_MD", tmp_path / "gone.md", raising=False)
    block1, block2 = w.Go2WRealWorld().persona_blocks()
    assert "REAL" in block1
    assert block2  # non-empty fallback
