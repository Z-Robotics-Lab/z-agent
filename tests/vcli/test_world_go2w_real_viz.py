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

from tests.unit.hardware.test_go2w_hw_overlay import FakePopenFactory


def _tool():
    from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool
    return Go2WRealVizTool(popen_factory=FakePopenFactory())


def _ctx():
    return SimpleNamespace(agent=None)


def _run(tool, **params):
    result = tool.execute(params, _ctx())
    return result


# ---------------------------------------------------------------------------
# viz tool
# ---------------------------------------------------------------------------


def test_viz_open_launches_rviz_overlay_nonblocking():
    tool = _tool()
    result = _run(tool, action="open")
    assert not result.is_error
    assert "rviz" in result.content.lower()
    # exactly one child spawned: bash <nav.sh> rviz
    (spawn,) = tool._launchers["rviz"]._popen_factory.spawned  # noqa: SLF001
    assert spawn.argv[0] == "bash"
    assert spawn.argv[1].endswith("nav.sh")
    assert spawn.argv[2] == "rviz"


def test_viz_views_map_to_nav_sh_modes():
    tool = _tool()
    assert not _run(tool, action="open", view="explore").is_error
    assert not _run(tool, action="open", view="route").is_error
    modes = set(tool._launchers)  # noqa: SLF001
    assert {"rviz-explore", "rviz-route"} <= modes


def test_viz_double_open_reports_already_running():
    tool = _tool()
    _run(tool, action="open")
    result = _run(tool, action="open")
    assert not result.is_error
    assert "already" in result.content.lower()


def test_viz_close_stops_children():
    tool = _tool()
    _run(tool, action="open")
    result = _run(tool, action="close")
    assert not result.is_error
    launcher = tool._launchers["rviz"]  # noqa: SLF001
    assert launcher.stop_requested
    assert not launcher.is_running()


def test_viz_close_when_nothing_open_is_not_an_error():
    result = _run(_tool(), action="close")
    assert not result.is_error


def test_viz_unknown_action_errors():
    assert _run(_tool(), action="teleport").is_error


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
