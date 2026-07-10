# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real — the REAL-hardware BYO world (P5.4, CEO ruling 2026-07-10).

Sibling to go2w (the Isaac digital twin): same CLI, same tool/skill/verify
seams, but every command goes through the RUNNING nav stack on this NUC
(ROS_DOMAIN_ID=20, CycloneDDS) — no unitree_sdk2, no HTTP bridge. The verify
oracle is /state_estimation odometry (the real ground truth, Inv-1: there is no
/gt on hardware, so ``at``/``moved`` read odometry the actor cannot forge).

These tests pin the plug-and-play seam WITHOUT a sourced ROS env or a live
robot: the Go2WHardware driver is replaced by a fake, and the nav.sh lifecycle
subprocess is monkeypatched. Ground truth = the registry/import graph, the
Protocol contract, and the odometry-reading verify math — none actor-authored.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Resolution — first-class built-in, no VECTOR_WORLD_PLUGINS needed
# ---------------------------------------------------------------------------


def test_go2w_real_is_a_builtin_world_id() -> None:
    """``go2w_real`` is a registered built-in world id (lazy factory)."""
    from zeno.vcli.worlds import get_world_registry

    names = get_world_registry().names()
    assert "go2w_real" in names, "go2w_real must be a first-class built-in world id"


def test_world_flag_go2w_real_resolves_real_world() -> None:
    """``--world go2w_real`` resolves a Go2WRealWorld through the CLI resolver."""
    from zeno.vcli.cli import _resolve_active_world

    args = SimpleNamespace(world="go2w_real", scenario=None)
    world = _resolve_active_world(args, agent=None)
    assert type(world).__name__ == "Go2WRealWorld"
    assert world.is_robot() is True


def test_real_world_is_distinct_from_sim_go2w() -> None:
    """go2w (sim) and go2w_real (hardware) are different world classes."""
    from zeno.vcli.worlds import resolve_world_named

    sim = resolve_world_named("go2w")
    real = resolve_world_named("go2w_real")
    assert type(sim).__name__ == "IsaacGo2WWorld"
    assert type(real).__name__ == "Go2WRealWorld"
    assert type(sim) is not type(real)


# ---------------------------------------------------------------------------
# register_tools — the real world's own tool set under its own category
# ---------------------------------------------------------------------------


_EXPECTED_TOOLS = {
    "go2w_real_bringup",
    "go2w_real_navigate",
    "go2w_real_where",
    "go2w_real_stop",
    "go2w_real_manual",
    "go2w_real_resume",
    "go2w_real_explore",  # v2: TARE autonomous exploration (overlay lifecycle)
    "go2w_real_route",
    "go2w_real_viz",    # v2: far_planner global route mode (overlay lifecycle)
}


def test_register_tools_adds_real_tools_under_go2w_real_category() -> None:
    """After register_tools the CLI tool table carries the go2w_real tools, and
    they are visible in the exported schema (their category is not disabled)."""
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    registry = CategorizedToolRegistry()
    _register_world_tools(world, registry, agent=None)

    tool_names = set(registry.list_tools())
    assert _EXPECTED_TOOLS <= tool_names, (
        f"missing real tools: {_EXPECTED_TOOLS - tool_names}"
    )
    assert set(registry.list_categories().get("go2w_real", [])) == _EXPECTED_TOOLS
    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}
    assert _EXPECTED_TOOLS <= schema_names


def test_real_world_declares_go2w_real_essential_category() -> None:
    """go2w_real declares ``go2w_real`` essential so routing keeps its tools in scope."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    hook = getattr(world, "essential_categories", None)
    assert callable(hook)
    assert "go2w_real" in set(hook())


def test_real_world_suppresses_kernel_sim_category() -> None:
    """A hardware world must NOT offer the kernel MuJoCo sim tools — 'start the
    sim' on real hardware is nonsensical and would mis-route."""
    from zeno.vcli.cli import _register_world_tools
    from zeno.vcli.tools import discover_categorized_tools
    from zeno.vcli.tools.base import CategorizedToolRegistry
    from zeno.vcli.worlds import resolve_world_named

    registry = CategorizedToolRegistry()
    tools_list, cat_map = discover_categorized_tools()
    for t in tools_list:
        cat = next((c for c, names in cat_map.items() if t.name in names), "default")
        registry.register(t, category=cat)
    _register_world_tools(resolve_world_named("go2w_real"), registry, agent=None)

    schema_names = {s["name"] for s in registry.to_anthropic_schemas()}
    assert "go2w_real_bringup" in schema_names
    assert "start_simulation" not in schema_names
    assert "stop_simulation" not in schema_names


# ---------------------------------------------------------------------------
# bringup tool — action -> nav.sh subcommand mapping (subprocess mocked)
# ---------------------------------------------------------------------------


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _bringup_ctx() -> Any:
    import threading
    from pathlib import Path

    from zeno.vcli.tools.base import ToolContext

    return ToolContext(agent=None, cwd=Path("/tmp"), session=None,
                       permissions=None, abort=threading.Event())


@pytest.fixture
def patch_navsh(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture the argv the bringup tool would hand to nav.sh (no bash runs)."""
    from zeno.vcli.worlds import go2w_real_tools as mod

    calls: list[list[str]] = []

    def _run(cmd: Any, *a: Any, **k: Any) -> _FakeCompleted:
        calls.append(list(cmd))
        return _FakeCompleted(returncode=0, stdout="ok", stderr="")

    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", _run)
    # nav.sh path existence check must pass without the real file.
    monkeypatch.setattr(mod.os.path, "isfile", lambda _p: True)
    return {"mod": mod, "calls": calls}


@pytest.mark.parametrize(
    "action, subcmd",
    [
        ("up", "up"),
        ("down", "down"),
        ("start", "start"),
        ("stop", "stop"),
        ("status", "status"),
    ],
)
def test_bringup_action_maps_to_nav_sh_subcommand(
    patch_navsh: dict[str, Any], action: str, subcmd: str
) -> None:
    """Each bringup action invokes ``bash <nav.sh> <subcmd>`` exactly."""
    mod = patch_navsh["mod"]
    tool = mod.Go2WRealBringupTool()
    res = tool.execute({"action": action}, _bringup_ctx())
    assert not res.is_error, res.content
    assert patch_navsh["calls"], "bringup must invoke nav.sh"
    argv = patch_navsh["calls"][-1]
    assert argv[0] == "bash"
    assert argv[1].endswith("nav.sh")
    assert argv[2] == subcmd


def test_bringup_rejects_unknown_action(patch_navsh: dict[str, Any]) -> None:
    """An action outside the enum fails loud and never shells out."""
    mod = patch_navsh["mod"]
    tool = mod.Go2WRealBringupTool()
    res = tool.execute({"action": "self-destruct"}, _bringup_ctx())
    assert res.is_error
    assert not patch_navsh["calls"], "no nav.sh call may run for a bad action"


def test_bringup_surfaces_nonzero_exit_as_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-zero nav.sh exit is reported honestly (is_error=True), mirroring the
    go2w teardown-fidelity fix — the model must not read a failed start as up."""
    from zeno.vcli.worlds import go2w_real_tools as mod

    def _run(cmd: Any, *a: Any, **k: Any) -> _FakeCompleted:
        return _FakeCompleted(returncode=1, stdout="", stderr="stack not running")

    import subprocess as _sp

    monkeypatch.setattr(_sp, "run", _run)
    monkeypatch.setattr(mod.os.path, "isfile", lambda _p: True)

    tool = mod.Go2WRealBringupTool()
    res = tool.execute({"action": "status"}, _bringup_ctx())
    assert res.is_error
    assert "stack not running" in res.content or "exit=1" in res.content


# ---------------------------------------------------------------------------
# verify namespace — at() / moved() read /state_estimation ONLY (real oracle)
# ---------------------------------------------------------------------------


class _FakeHW:
    """Stand-in Go2WHardware exposing the odometry the verify predicates read."""

    def __init__(self, x: float, y: float) -> None:
        self._x, self._y = x, y

    def get_position(self) -> tuple[float, float, float]:
        return (self._x, self._y, 0.0)


def _real_world_with_fake_agent(x: float, y: float):
    """Resolve go2w_real and give it an embodiment whose _base is a fake HW."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    agent = SimpleNamespace(_base=_FakeHW(x, y))
    return world, agent


def test_verify_namespace_exposes_at_and_moved() -> None:
    """build_verify_namespace contributes ``at`` and ``moved`` predicates."""
    world, agent = _real_world_with_fake_agent(1.0, 2.0)
    ns = world.build_verify_namespace(agent)
    assert callable(ns.get("at"))
    assert callable(ns.get("moved"))


def test_at_grades_on_odometry_within_tolerance() -> None:
    """at(x, y, tol) is True inside the tolerance ball, False outside — reading
    the driver's /state_estimation position, the only oracle on hardware."""
    world, agent = _real_world_with_fake_agent(2.0, 3.0)
    at = world.build_verify_namespace(agent)["at"]
    assert at(2.0, 3.0) is True
    assert at(2.5, 3.0, tol=0.8) is True   # 0.5 m < 0.8 m default-ish
    assert at(5.0, 5.0, tol=0.8) is False  # far outside


def test_at_default_tolerance_is_0_8() -> None:
    """The real-oracle arrival tolerance default is 0.8 m (task contract)."""
    world, agent = _real_world_with_fake_agent(0.0, 0.0)
    at = world.build_verify_namespace(agent)["at"]
    # 0.79 m away passes at default tol, 0.81 m away fails.
    assert at(0.79, 0.0) is True
    assert at(0.81, 0.0) is False


def test_moved_measures_displacement_from_a_start_capture() -> None:
    """moved(min_m) is True once the robot has displaced >= min_m from where the
    predicate first sampled the pose (a monotonic 'did it actually move' check)."""
    world, agent = _real_world_with_fake_agent(0.0, 0.0)
    ns = world.build_verify_namespace(agent)
    moved = ns["moved"]
    # First call captures the origin; robot is still at origin -> not moved yet.
    assert moved(0.5) is False
    # Robot drives 1 m away (fake HW pose changes), now it has moved >= 0.5 m.
    agent._base._x = 1.0
    assert moved(0.5) is True


def test_at_is_fail_safe_when_no_agent() -> None:
    """With no embodiment/base wired, at()/moved() degrade to False, never crash
    (verifier-sandbox fail-safe — a missing oracle must never fake-pass)."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    ns = world.build_verify_namespace(agent=None)
    assert ns["at"](0.0, 0.0) is False
    assert ns["moved"](0.1) is False


# ---------------------------------------------------------------------------
# decompose vocab + persona — REAL-robot wording, no sim/reset language
# ---------------------------------------------------------------------------


def test_decompose_vocab_teaches_real_strategies_and_at_verify() -> None:
    """The vocab teaches navigate/move_relative/stance strategies and the ``at``
    verify fn, and must NOT be a partial (empty-set) DecomposeVocab (the go2w
    foot-gun: strategies=frozenset() wipes KNOWN_STRATEGIES)."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    vocab = world.decompose_vocab()
    assert vocab is not None
    assert vocab.strategies, "strategies set must be non-empty (not the empty foot-gun)"
    assert "at" in vocab.verify_functions
    # The taught strategy set matches the strategy_descriptions keys (no drift).
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)


def test_persona_mentions_real_robot_and_estop_not_sim_reset() -> None:
    """Persona must frame the robot as REAL (E-stop reminder, no reset), never as
    a resettable sim — mistakes have physical consequences on hardware."""
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    role, tools = world.persona_blocks()
    blob = (role + " " + tools).lower()
    assert "real" in blob
    assert "e-stop" in blob or "estop" in blob or "emergency" in blob
    # No sim-only affordances leaking into the hardware persona.
    assert "isaac" not in blob
    assert "reset the sim" not in blob


def test_vocab_strategies_resolve_to_registered_skills() -> None:
    """Every taught strategy resolves through a real StrategySelector to a skill
    registered in this world's embodiment (the W1.2 consistency contract)."""
    from zeno.vcli.cognitive.strategy_selector import StrategySelector
    from zeno.vcli.cognitive.types import SubGoal
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    embodiment = world.build_embodiment()
    registry = embodiment._skill_registry
    selector = StrategySelector(skill_registry=registry, has_base=True)
    skills = set(registry.list_skills())
    vocab = world.decompose_vocab()
    for strategy in sorted(vocab.strategies):
        sub = SubGoal(name="s", description="s", verify="True", strategy=strategy)
        result = selector.select(sub)
        assert result.executor_type == "skill", (
            f"strategy {strategy!r} routed to {result.executor_type!r}, not a skill"
        )
        assert result.name in skills


# ---------------------------------------------------------------------------
# build_embodiment — the BYO front door yields a hardware-backed agent
# ---------------------------------------------------------------------------


def test_build_embodiment_returns_agent_with_hardware_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_embodiment returns an object with a Go2WHardware _base + skills.

    Construction must NOT connect to ROS (offline): the driver is created but not
    connected until session setup. _base is the VGG readiness criterion.
    """
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    embodiment = world.build_embodiment()
    assert embodiment is not None
    assert getattr(embodiment, "_base", None) is not None
    assert getattr(embodiment, "_skill_registry", None) is not None
    # The base is the real-hardware driver type (duck-typed name check).
    assert type(embodiment._base).__name__ == "Go2WHardware"
    # Fresh embodiment each call (no shared mutable state across sessions).
    assert world.build_embodiment() is not embodiment
