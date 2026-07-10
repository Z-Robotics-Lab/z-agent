# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real route wiring — far_planner route mode as a world skill/tool/verify.

Pins the plug-and-play seam for far_planner GLOBAL routing WITHOUT ROS or a
robot: the route manager is a duck-typed fake. Ground truth = the registry
graph, the tool/skill dispatch contract, and the verify predicate's fail-safe
math. The route wiring is registered ONLY in the '# v2-extension point: *'
append-only sections of go2w_real.py (it must not disturb the explore wiring).
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


class _FakeRouteMgr:
    """Duck-typed Go2WRouteManager the tools/skills/verify drive."""

    def __init__(self, reached: bool = False) -> None:
        self.started: int = 0
        self.stopped: list[Any] = []
        self.goals: list[tuple[float, float]] = []
        self.cancelled: int = 0
        self._reached = reached

    def start_route(self):
        self.started += 1
        return True, "route launched (far_planner)"

    def stop_route(self, resume: bool = False):
        self.stopped.append(resume)
        return True, "route stopped by request"

    def goto_via_route(self, x: float, y: float, timeout: float = 120.0) -> bool:
        self.goals.append((x, y))
        return self._reached

    def cancel_route(self):
        self.cancelled += 1
        return True, "route goal cancelled"

    def route_reached(self) -> bool:
        return self._reached

    def state(self) -> str:
        return "active"

    @property
    def is_active(self) -> bool:
        return True

    def status(self):
        from zeno.hardware.ros2.go2w_hw_route import RouteStatus

        return RouteStatus(
            state="active", pid=4243, reached=self._reached,
            goal=None, far_reach=self._reached, runtime_s=None,
            reason="", oracle_attached=True,
        )


def _tool_ctx(agent: Any):
    from zeno.vcli.tools.base import ToolContext

    return ToolContext(agent=agent, cwd=Path("/tmp"), session=None,
                       permissions=None, abort=threading.Event())


# ---------------------------------------------------------------------------
# Registration — tool present in the go2w_real category
# ---------------------------------------------------------------------------


def test_register_tools_includes_route_tool() -> None:
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.worlds import resolve_world_named

    registry = CategorizedToolRegistry()
    _register_world_tools(resolve_world_named("go2w_real"), registry, agent=None)

    assert "go2w_real_route" in set(registry.list_tools())
    assert "go2w_real_route" in set(registry.list_categories().get("go2w_real", []))


def test_embodiment_wires_route_manager_into_skill_context() -> None:
    """The embodiment owns ONE route manager bound to its hardware base, and
    exposes it to skills as the 'route' service (SkillContext.services)."""
    from zeno.vcli.worlds import resolve_world_named

    emb = resolve_world_named("go2w_real").build_embodiment()

    mgr = getattr(emb, "_route", None)
    assert mgr is not None
    assert type(mgr).__name__ == "Go2WRouteManager"
    ctx = emb._build_context()
    assert ctx.services.get("route") is mgr
    # Route skills are registered next to the v1 + explore skills.
    skills = set(emb._skill_registry.list_skills())
    assert {"route_via", "stop_route"} <= skills


# ---------------------------------------------------------------------------
# Verify namespace — route_reached (fail-safe)
# ---------------------------------------------------------------------------


def _world_and_agent(mgr: Any):
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    return world, SimpleNamespace(_base=None, _explore=None, _route=mgr)


def test_verify_namespace_exposes_route_reached() -> None:
    world, agent = _world_and_agent(_FakeRouteMgr(reached=True))
    ns = world.build_verify_namespace(agent)

    assert ns["route_reached"]() is True


def test_route_predicate_fail_safe_without_manager() -> None:
    """No embodiment / no manager => False, never a raise into the verifier
    sandbox (a missing oracle must never fake-pass)."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    ns = world.build_verify_namespace(agent=None)
    assert ns["route_reached"]() is False


def test_route_predicate_fail_safe_on_raising_manager() -> None:
    class _Boom:
        def route_reached(self):
            raise RuntimeError("oracle offline")

    world, agent = _world_and_agent(_Boom())
    ns = world.build_verify_namespace(agent)
    assert ns["route_reached"]() is False


# ---------------------------------------------------------------------------
# Skills — route_via / stop_route drive the manager through context.services
# ---------------------------------------------------------------------------


def test_route_skill_sends_goal_via_service() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_route_skills import RealRouteViaSkill

    mgr = _FakeRouteMgr(reached=True)
    ctx = SkillContext(bases={"go2w": object()}, services={"route": mgr})

    res = RealRouteViaSkill().execute({"x": 4.0, "y": 5.0}, ctx)

    assert res.success is True
    assert mgr.started == 1, "route skill must ensure far_planner is up"
    assert mgr.goals == [(4.0, 5.0)]


def test_route_skill_reports_failure_when_not_reached() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_route_skills import RealRouteViaSkill

    mgr = _FakeRouteMgr(reached=False)
    ctx = SkillContext(services={"route": mgr})
    res = RealRouteViaSkill().execute({"x": 1.0, "y": 2.0}, ctx)

    assert res.success is False
    assert mgr.goals == [(1.0, 2.0)]


def test_route_skill_fails_clear_without_manager() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_route_skills import RealRouteViaSkill

    res = RealRouteViaSkill().execute({"x": 1.0, "y": 2.0}, SkillContext())

    assert res.success is False
    assert "route" in (res.error_message or "").lower()


def test_route_skill_needs_a_target() -> None:
    """No (x, y) anywhere => a clear failure, not a crash or a phantom goal."""
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_route_skills import RealRouteViaSkill

    mgr = _FakeRouteMgr()
    res = RealRouteViaSkill().execute({}, SkillContext(services={"route": mgr}))

    assert res.success is False
    assert mgr.goals == []


def test_stop_route_skill_stops_via_service() -> None:
    from zeno.core.skill import SkillContext
    from zeno.vcli.worlds.go2w_real_route_skills import RealStopRouteSkill

    mgr = _FakeRouteMgr()
    res = RealStopRouteSkill().execute({}, SkillContext(services={"route": mgr}))

    assert res.success is True
    assert mgr.stopped == [False], "skill stop must not auto-release latches"


# ---------------------------------------------------------------------------
# Tool — go2w_real_route action mapping on the agent's manager
# ---------------------------------------------------------------------------


def test_route_tool_start_goto_status_cancel_stop_mapping() -> None:
    from zeno.vcli.worlds.go2w_real_route_tools import Go2WRealRouteTool

    mgr = _FakeRouteMgr(reached=True)
    ctx = _tool_ctx(SimpleNamespace(_route=mgr, _base=None))
    tool = Go2WRealRouteTool()

    res = tool.execute({"action": "start"}, ctx)
    assert not res.is_error, res.content
    assert mgr.started == 1

    res = tool.execute({"action": "goto", "x": 6.0, "y": 7.0}, ctx)
    assert not res.is_error, res.content
    assert mgr.goals == [(6.0, 7.0)]

    res = tool.execute({"action": "status"}, ctx)
    assert not res.is_error
    assert "active" in res.content

    res = tool.execute({"action": "cancel"}, ctx)
    assert not res.is_error
    assert mgr.cancelled == 1

    res = tool.execute({"action": "stop"}, ctx)
    assert not res.is_error
    assert mgr.stopped == [False]


def test_route_tool_goto_requires_coordinates() -> None:
    from zeno.vcli.worlds.go2w_real_route_tools import Go2WRealRouteTool

    tool = Go2WRealRouteTool()
    res = tool.execute({"action": "goto"}, _tool_ctx(SimpleNamespace(_route=_FakeRouteMgr())))
    assert res.is_error


def test_route_tool_rejects_unknown_action_and_missing_manager() -> None:
    from zeno.vcli.worlds.go2w_real_route_tools import Go2WRealRouteTool

    tool = Go2WRealRouteTool()
    res = tool.execute({"action": "warp"}, _tool_ctx(SimpleNamespace(_route=_FakeRouteMgr())))
    assert res.is_error

    res = tool.execute({"action": "start"}, _tool_ctx(None))
    assert res.is_error
    assert "route" in res.content.lower()


# ---------------------------------------------------------------------------
# Decompose vocab — planner taught the route strategies + verify fn
# ---------------------------------------------------------------------------


def test_vocab_teaches_route_strategies_and_predicate() -> None:
    from zeno.vcli.worlds import resolve_world_named

    vocab = resolve_world_named("go2w_real").decompose_vocab()

    assert {"route_via_skill", "stop_route_skill"} <= set(vocab.strategies)
    assert "route_reached" in vocab.verify_functions
    # The taught strategy set still matches the strategy_descriptions keys.
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)
    assert "route_reached" in vocab.verify_fn_signatures
    # params-help mentions the new strategy so the planner can fill it.
    assert "route_via_skill" in vocab.strategy_params_help


def test_route_vocab_strategies_resolve_to_registered_skills() -> None:
    """The new route strategies resolve through a real StrategySelector to skills
    registered in this world's embodiment (the W1.2 consistency contract), and
    every strategy name ends '_skill' (StrategySelector fail-loud)."""
    from zeno.vcli.cognitive.strategy_selector import StrategySelector
    from zeno.vcli.cognitive.types import SubGoal
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    embodiment = world.build_embodiment()
    registry = embodiment._skill_registry
    selector = StrategySelector(skill_registry=registry, has_base=True)
    skills = set(registry.list_skills())
    for strategy in ("route_via_skill", "stop_route_skill"):
        assert strategy.endswith("_skill")
        sub = SubGoal(name="s", description="s", verify="True", strategy=strategy)
        result = selector.select(sub)
        assert result.executor_type == "skill", (
            f"strategy {strategy!r} routed to {result.executor_type!r}, not a skill"
        )
        assert result.name in skills
