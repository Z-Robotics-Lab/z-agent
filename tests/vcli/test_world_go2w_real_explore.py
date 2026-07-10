# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real explore wiring — TARE exploration as a world skill/tool/verify (v2).

Pins the plug-and-play seam for autonomous exploration WITHOUT ROS or a robot:
the explore manager is a duck-typed fake. Ground truth = the registry graph,
the tool/skill dispatch contract, and the verify predicates' fail-safe math.

Also pins the v2 EXTENSION-SEAM CONTRACT: go2w_real.py carries append-only,
marker-commented registration sections ('# v2-extension point: <name>') that
the parallel feature agents (route-mode, etc.) extend without touching the
explore wiring — the markers are load-bearing coordination points, so a test
guards their existence.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeExploreMgr:
    """Duck-typed Go2WExploreManager the tools/skills/verify drive."""

    def __init__(self, finished: bool = False, progress: float = 0.0) -> None:
        self.started: list[Any] = []
        self.stopped: list[Any] = []
        self._finished = finished
        self._progress = progress

    def start_explore(self, scenario: str | None = None):
        self.started.append(scenario)
        return True, f"explore launched (scenario={scenario})"

    def stop_explore(self, resume: bool = False):
        self.stopped.append(resume)
        return True, "explore stopped by request"

    def explore_finished(self) -> bool:
        return self._finished

    def explored_progress(self) -> float:
        return self._progress

    def state(self) -> str:
        return "exploring"

    @property
    def is_active(self) -> bool:
        return True

    def status(self):
        from zeno.hardware.ros2.go2w_hw_explore import ExploreStatus

        return ExploreStatus(
            state="exploring", scenario="indoor_small", pid=4242,
            finished=self._finished, travel_m=self._progress,
            runtime_s=1.5, reason="", oracle_attached=True,
        )


def _tool_ctx(agent: Any):
    from zeno.vcli.tools.base import ToolContext

    return ToolContext(agent=agent, cwd=Path("/tmp"), session=None,
                       permissions=None, abort=threading.Event())


# ---------------------------------------------------------------------------
# Registration — tool present in the go2w_real category
# ---------------------------------------------------------------------------


def test_register_tools_includes_explore_tool() -> None:
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.worlds import resolve_world_named

    registry = CategorizedToolRegistry()
    _register_world_tools(resolve_world_named("go2w_real"), registry, agent=None)

    assert "go2w_real_explore" in set(registry.list_tools())
    assert "go2w_real_explore" in set(registry.list_categories().get("go2w_real", []))


def test_embodiment_wires_explore_manager_into_skill_context() -> None:
    """The embodiment owns ONE explore manager bound to its hardware base, and
    exposes it to skills as the 'explore' service (SkillContext.services)."""
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()

    mgr = getattr(emb, "_explore", None)
    assert mgr is not None
    assert type(mgr).__name__ == "Go2WExploreManager"
    ctx = emb._build_context()
    assert ctx.services.get("explore") is mgr
    # Explore skills are registered next to the v1 skills.
    skills = set(emb._skill_registry.list_skills())
    assert {"explore", "stop_explore"} <= skills


# ---------------------------------------------------------------------------
# Verify namespace — explore_finished / explored_progress (fail-safe)
# ---------------------------------------------------------------------------


def _world_and_agent(mgr: Any):
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    return world, SimpleNamespace(_base=None, _explore=mgr)


def test_verify_namespace_exposes_explore_predicates() -> None:
    world, agent = _world_and_agent(_FakeExploreMgr(finished=True, progress=7.5))
    ns = world.build_verify_namespace(agent)

    assert ns["explore_finished"]() is True
    assert ns["explored_progress"]() == pytest.approx(7.5)


def test_explore_predicates_fail_safe_without_manager() -> None:
    """No embodiment / no manager => False / 0.0, never a raise into the
    verifier sandbox (a missing oracle must never fake-pass)."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    ns = world.build_verify_namespace(agent=None)
    assert ns["explore_finished"]() is False
    assert ns["explored_progress"]() == 0.0


def test_explore_predicates_fail_safe_on_raising_manager() -> None:
    class _Boom:
        def explore_finished(self):
            raise RuntimeError("oracle offline")

        def explored_progress(self):
            raise RuntimeError("oracle offline")

    world, agent = _world_and_agent(_Boom())
    ns = world.build_verify_namespace(agent)
    assert ns["explore_finished"]() is False
    assert ns["explored_progress"]() == 0.0


# ---------------------------------------------------------------------------
# Skills — explore / stop_explore drive the manager through context.services
# ---------------------------------------------------------------------------


def test_explore_skill_starts_exploration_via_service() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_skills import RealExploreSkill

    mgr = _FakeExploreMgr()
    ctx = SkillContext(bases={"go2w": object()}, services={"explore": mgr})

    res = RealExploreSkill().execute({"scenario": "outdoor"}, ctx)

    assert res.success is True
    assert mgr.started == ["outdoor"]


def test_explore_skill_defaults_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_skills import RealExploreSkill

    mgr = _FakeExploreMgr()
    ctx = SkillContext(services={"explore": mgr})
    res = RealExploreSkill().execute({}, ctx)

    assert res.success is True
    assert mgr.started == ["indoor_small"]


def test_explore_skill_fails_clear_without_manager() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_skills import RealExploreSkill

    res = RealExploreSkill().execute({}, SkillContext())

    assert res.success is False
    assert "explore" in (res.error_message or "").lower()


def test_stop_explore_skill_stops_via_service() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_skills import RealStopExploreSkill

    mgr = _FakeExploreMgr()
    res = RealStopExploreSkill().execute({}, SkillContext(services={"explore": mgr}))

    assert res.success is True
    assert mgr.stopped == [False], "skill stop must not auto-release latches"


# ---------------------------------------------------------------------------
# Tool — go2w_real_explore action mapping on the agent's manager
# ---------------------------------------------------------------------------


def test_explore_tool_start_status_stop_mapping() -> None:
    from zeno.vcli.worlds.go2w_real_tools import Go2WRealExploreTool

    mgr = _FakeExploreMgr(finished=False, progress=2.0)
    ctx = _tool_ctx(SimpleNamespace(_explore=mgr, _base=None))
    tool = Go2WRealExploreTool()

    res = tool.execute({"action": "start", "scenario": "indoor_small"}, ctx)
    assert not res.is_error, res.content
    assert mgr.started == ["indoor_small"]

    res = tool.execute({"action": "status"}, ctx)
    assert not res.is_error
    assert "exploring" in res.content
    assert "travel_m" in res.content

    res = tool.execute({"action": "stop"}, ctx)
    assert not res.is_error
    assert mgr.stopped == [False]


def test_explore_tool_rejects_unknown_action_and_missing_manager() -> None:
    from zeno.vcli.worlds.go2w_real_tools import Go2WRealExploreTool

    tool = Go2WRealExploreTool()
    res = tool.execute({"action": "warp"}, _tool_ctx(SimpleNamespace(_explore=_FakeExploreMgr())))
    assert res.is_error

    res = tool.execute({"action": "start"}, _tool_ctx(None))
    assert res.is_error
    assert "explore" in res.content.lower()


# ---------------------------------------------------------------------------
# Decompose vocab — planner taught the explore strategies + verify fns
# ---------------------------------------------------------------------------


def test_vocab_teaches_explore_strategies_and_predicates() -> None:
    from zeno.vcli.worlds import resolve_world_named

    vocab = resolve_world_named("go2w_real").decompose_vocab()

    assert {"explore_skill", "stop_explore_skill"} <= set(vocab.strategies)
    assert {"explore_finished", "explored_progress"} <= set(vocab.verify_functions)
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)
    assert "explore_finished" in vocab.verify_fn_signatures
    assert "explored_progress" in vocab.verify_fn_signatures


# ---------------------------------------------------------------------------
# v2 extension seam — marker-commented append-only registration sections
# ---------------------------------------------------------------------------


def test_v2_extension_seam_markers_present() -> None:
    """The parallel feature agents append at these markers; their absence would
    silently break the coordination contract, so it is pinned here."""
    import inspect

    from zeno.vcli.worlds import go2w_real

    src = inspect.getsource(go2w_real)
    for seam in ("tools", "skills", "verify", "vocab"):
        assert f"v2-extension point: {seam}" in src, (
            f"go2w_real.py must carry the '# v2-extension point: {seam}' marker"
        )
