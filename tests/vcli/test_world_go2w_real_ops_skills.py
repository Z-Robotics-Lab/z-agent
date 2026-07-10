# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real viz/where SKILLS + shared viz overlay session (v2, RED first).

Field trace 2026-07-10 evening: '启动导航,打开rviz' — VGG planned ONLY the
bringup step: viz existed solely as a TOOL, invisible to strategy planning, so
the second half of the command was silently dropped. Same gap for "where am I"
inside a plan. Pinned here:

* RealVizSkill ('open_viz', strategy open_viz_skill): thin skill over the SAME
  session OverlayLauncher table the go2w_real_viz TOOL uses — the shared
  ``VizOverlaySession`` — so a plan-opened view and a tool-opened view can
  never double-launch RViz; opening an already-open view reports ok (dedupe).
* RealWhereSkill ('where', strategy where_skill): pose from the driver.
* Wiring: embodiment owns one session (rides the driver as base.viz_manager +
  services['viz']); both skills registered; vocab teaches both strategies.

Hermetic: FakePopenFactory (no real nav.sh child), no ROS env, no LLM.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.hardware.test_go2w_hw_overlay import FakePopenFactory, FakeProc


def _nav_sh(tmp_path: Path) -> str:
    p = tmp_path / "nav.sh"
    p.write_text("#!/usr/bin/env bash\n")
    return str(p)


def _session(tmp_path: Path, factory: FakePopenFactory | None = None):
    from zeno.vcli.worlds.go2w_real_viz_tools import VizOverlaySession

    return VizOverlaySession(
        popen_factory=factory or FakePopenFactory(),
        nav_sh=_nav_sh(tmp_path))


def _viz_skill():
    from zeno.vcli.worlds.go2w_real_ops_skills import RealVizSkill

    return RealVizSkill()


def _where_skill():
    from zeno.vcli.worlds.go2w_real_ops_skills import RealWhereSkill

    return RealWhereSkill()


def _ctx(base=None, services=None, instruction: str = ""):
    return SimpleNamespace(base=base, services=services or {},
                           instruction=instruction)


# ---------------------------------------------------------------------------
# open_viz skill — launches through the shared session
# ---------------------------------------------------------------------------


def test_open_viz_skill_launches_view_through_session(tmp_path):
    factory = FakePopenFactory()
    session = _session(tmp_path, factory)
    result = _viz_skill().execute(
        {"view": "explore"}, _ctx(services={"viz": session}))
    assert result.success, result.error_message
    (argv, _kwargs), = factory.calls
    assert argv[0] == "bash" and argv[1].endswith("nav.sh")
    assert argv[2] == "rviz-explore"


def test_open_viz_skill_defaults_to_main_view(tmp_path):
    factory = FakePopenFactory()
    session = _session(tmp_path, factory)
    result = _viz_skill().execute({}, _ctx(services={"viz": session}))
    assert result.success
    assert factory.calls[0][0][2] == "rviz"


def test_open_viz_skill_dedupes_already_open_view(tmp_path):
    """Opening a view that is already open is OK (success, no second child)."""
    factory = FakePopenFactory()
    session = _session(tmp_path, factory)
    skill = _viz_skill()
    assert skill.execute({"view": "main"}, _ctx(services={"viz": session})).success
    result = skill.execute({"view": "main"}, _ctx(services={"viz": session}))
    assert result.success, "already-open must report ok, not an error"
    assert "already" in str(result.result_data or {}).lower()
    assert len(factory.calls) == 1, "no double-launch"


def test_open_viz_skill_rejects_unknown_view(tmp_path):
    session = _session(tmp_path)
    result = _viz_skill().execute(
        {"view": "teleport"}, _ctx(services={"viz": session}))
    assert not result.success


def test_open_viz_skill_finds_session_via_driver_fallback(tmp_path):
    """VGG GoalExecutor contexts carry no world services — the session must
    also ride the driver (base.viz_manager), like explore/route managers."""
    session = _session(tmp_path)
    base = SimpleNamespace(viz_manager=session)
    result = _viz_skill().execute({"view": "main"}, _ctx(base=base))
    assert result.success


def test_open_viz_skill_without_session_fails_honestly():
    result = _viz_skill().execute({"view": "main"}, _ctx())
    assert not result.success


# ---------------------------------------------------------------------------
# tool ↔ skill share ONE session — no double-launch across the two faces
# ---------------------------------------------------------------------------


def test_tool_and_skill_share_the_session_no_double_launch(tmp_path):
    """The TOOL launches a view; the SKILL then sees it as already open (and
    vice versa) because both act on the same session object — the agent's."""
    from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool

    factory = FakePopenFactory()
    session = _session(tmp_path, factory)
    agent = SimpleNamespace(_viz=session, _base=None)

    tool = Go2WRealVizTool()  # NO private state may be used when agent has one
    tool_result = tool.execute({"action": "open", "view": "main"},
                               SimpleNamespace(agent=agent))
    assert not tool_result.is_error
    assert len(factory.calls) == 1

    skill_result = _viz_skill().execute(
        {"view": "main"}, _ctx(services={"viz": session}))
    assert skill_result.success
    assert len(factory.calls) == 1, "tool-opened view must dedupe in the skill"
    assert "already" in str(skill_result.result_data or {}).lower()


def test_embodiment_owns_one_shared_viz_session():
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()
    session = getattr(emb, "_viz", None)
    assert session is not None, "embodiment must own the viz session"
    assert getattr(emb._base, "viz_manager", None) is session
    assert emb._build_context().services.get("viz") is session


# ---------------------------------------------------------------------------
# where skill — pose from the driver
# ---------------------------------------------------------------------------


class _PoseFakeHW:
    def __init__(self, x=1.5, y=-2.0, yaw=0.7, age=0.4):
        self._pose = (x, y, 0.0)
        self._yaw = yaw
        self._age = age

    def get_position(self):
        return self._pose

    def get_heading(self):
        return self._yaw

    def odom_age_s(self):
        return self._age


def test_where_skill_reports_pose_from_driver():
    result = _where_skill().execute({}, _ctx(base=_PoseFakeHW()))
    assert result.success
    data = result.result_data or {}
    assert data.get("x") == pytest.approx(1.5)
    assert data.get("y") == pytest.approx(-2.0)
    assert data.get("yaw") == pytest.approx(0.7)


def test_where_skill_without_base_fails_honestly():
    result = _where_skill().execute({}, _ctx(base=None))
    assert not result.success
    assert result.diagnosis_code == "no_base"


def test_where_skill_honest_when_odometry_never_arrived():
    """A driver that KNOWS it never received odometry must not report the
    default (0,0,0) as a real pose — that is the stack_ready field bug twin."""
    result = _where_skill().execute({}, _ctx(base=_PoseFakeHW(age=None)))
    assert not result.success


# ---------------------------------------------------------------------------
# Wiring — skills registered, vocab teaches the strategies
# ---------------------------------------------------------------------------


def test_viz_and_where_skills_registered_in_embodiment():
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()
    skills = set(emb._skill_registry.list_skills())
    assert "open_viz" in skills
    assert "where" in skills


def test_vocab_teaches_open_viz_and_where_strategies():
    from zeno.vcli.worlds import resolve_world_named

    vocab = resolve_world_named("go2w_real").decompose_vocab()
    assert "open_viz_skill" in vocab.strategies
    assert "where_skill" in vocab.strategies
    assert "open_viz_skill" in vocab.strategy_descriptions
    assert "where_skill" in vocab.strategy_descriptions
    assert "open_viz_skill" in vocab.strategy_params_help
    assert "where_skill" in vocab.strategy_params_help
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)
