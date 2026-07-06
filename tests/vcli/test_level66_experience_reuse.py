# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 66 — Phase B.2.2: experience compilation -> template reuse.

Acceptance criteria (docs/agent-kernel-phase-b-plan.md, B-4):
- a successful trace compiles to a template that carries verify AND
  strategy_params (so a tool_call payload survives compile -> reuse).
- the template round-trips through JSON (v1 files without strategy_params still
  load — back-compat).
- a matching task reuses the template with the LLM backend asserted NOT called.
- the engine compiles successful runs into its TemplateLibrary on the hot path.

Pure kernel logic — no robot, no network, no mujoco fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from zeno.vcli.cognitive.experience_compiler import ExperienceCompiler
from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer
from zeno.vcli.cognitive.template_library import TemplateLibrary
from zeno.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from zeno.vcli.worlds.dev import DEV_VOCAB


_TOOL_PARAMS = {"tool": "file_write", "args": {"file_path": "config.txt", "content": "ready\n"}}


def _tool_trace(goal: str = "create config.txt with ready") -> ExecutionTrace:
    # Sub-goal name words ("create", "config") both appear in the reuse task, so
    # the (strict, full-subset) concrete matcher fires — a realistic LLM naming.
    sg = SubGoal(
        name="create_config",
        description="write config.txt",
        verify="path_contains('config.txt', 'ready')",
        strategy="tool_call",
        strategy_params=_TOOL_PARAMS,
    )
    return ExecutionTrace(
        goal_tree=GoalTree(goal=goal, sub_goals=(sg,)),
        steps=(StepRecord("create_config", "tool_call", True, True, 0.1),),
        success=True,
        total_duration_sec=0.1,
    )


# ---------------------------------------------------------------------------
# Compilation carries verify + strategy_params
# ---------------------------------------------------------------------------


def test_compile_carries_verify_and_strategy_params() -> None:
    templates = ExperienceCompiler().compile([_tool_trace()])
    assert len(templates) == 1
    sgt = templates[0].sub_goal_templates[0]
    assert sgt.verify_pattern == "path_contains('config.txt', 'ready')"
    assert sgt.strategy == "tool_call"
    assert sgt.strategy_params == _TOOL_PARAMS


def test_failed_traces_compile_to_nothing() -> None:
    bad = ExecutionTrace(
        goal_tree=GoalTree(goal="x", sub_goals=(SubGoal(name="a", description="", verify="True"),)),
        steps=(StepRecord("a", "", False, False, 0.0),),
        success=False,
        total_duration_sec=0.0,
    )
    assert ExperienceCompiler().compile([bad]) == []


# ---------------------------------------------------------------------------
# Serialization round-trip + back-compat
# ---------------------------------------------------------------------------


def test_template_json_round_trip_preserves_payload(tmp_path: Path) -> None:
    path = str(tmp_path / "tpl.json")
    lib = TemplateLibrary(persist_path=path)
    lib.add(ExperienceCompiler().compile([_tool_trace()])[0])
    lib.save()

    raw = json.loads(Path(path).read_text())
    assert raw[0]["sub_goal_templates"][0]["strategy_params"] == _TOOL_PARAMS

    lib2 = TemplateLibrary(persist_path=path)
    tpl, params = lib2.match("create config.txt with ready")
    instantiated = lib2.instantiate(tpl, params).sub_goals[0]
    assert instantiated.strategy == "tool_call"
    assert instantiated.strategy_params == _TOOL_PARAMS


def test_v1_template_without_strategy_params_loads(tmp_path: Path) -> None:
    """A pre-B.2 template (no strategy_params key) must still load."""
    path = tmp_path / "v1.json"
    path.write_text(json.dumps([{
        "name": "reach",
        "description": "go to ${room}",
        "parameters": ["room"],
        "sub_goal_templates": [{
            "name_pattern": "reach_${room}",
            "description_pattern": "go to ${room}",
            "verify_pattern": "nearest_room() == '${room}'",
            "strategy": "navigate_skill",
            "timeout_sec": 30.0,
            "depends_on": [],
            "fail_action": "",
        }],
        "success_count": 1,
        "fail_count": 0,
    }]))
    lib = TemplateLibrary(persist_path=str(path))
    tpl, params = lib.match("go to kitchen")
    inst = lib.instantiate(tpl, params).sub_goals[0]
    # Back-compat: no stored payload -> the extracted params (historical robot behaviour).
    assert inst.strategy == "navigate_skill"
    assert inst.strategy_params == {"room": "kitchen"}


# ---------------------------------------------------------------------------
# The headline AC: template hit skips the LLM backend
# ---------------------------------------------------------------------------


def test_decomposer_template_hit_skips_backend(tmp_path: Path) -> None:
    path = str(tmp_path / "tpl.json")
    lib = TemplateLibrary(persist_path=path)
    lib.add(ExperienceCompiler().compile([_tool_trace()])[0])

    backend = MagicMock()
    gd = GoalDecomposer(backend, template_library=lib, **DEV_VOCAB.as_kwargs())

    tree = gd.decompose("create config.txt with ready", "")

    assert backend.call.call_count == 0  # no LLM call on a template hit
    assert tree.sub_goals[0].strategy == "tool_call"
    assert tree.sub_goals[0].strategy_params == _TOOL_PARAMS


def test_concrete_template_does_not_hijack_unrelated_task(tmp_path: Path) -> None:
    """A single shared token must NOT trigger reuse (stale tool_call hijack)."""
    lib = TemplateLibrary(persist_path=str(tmp_path / "tpl.json"))
    lib.add(ExperienceCompiler().compile([_tool_trace()])[0])  # name words {create, config}

    backend = MagicMock()
    backend.call.return_value = MagicMock(text='{"goal": "x", "sub_goals": []}')
    gd = GoalDecomposer(backend, template_library=lib, **DEV_VOCAB.as_kwargs())

    # Shares only "create" with the template's sub-goal name -> no full-subset match.
    gd.decompose("create a summary report", "")
    assert backend.call.call_count == 1  # fell through to the LLM, no stale reuse


def test_decomposer_no_template_falls_through_to_backend(tmp_path: Path) -> None:
    """With an empty library, decompose must still call the backend."""
    lib = TemplateLibrary(persist_path=str(tmp_path / "empty.json"))
    backend = MagicMock()
    backend.call.return_value = MagicMock(text='{"goal": "x", "sub_goals": []}')
    gd = GoalDecomposer(backend, template_library=lib, **DEV_VOCAB.as_kwargs())

    gd.decompose("some entirely unrelated request zzz", "")
    assert backend.call.call_count == 1


# ---------------------------------------------------------------------------
# Engine compiles successful runs into its library
# ---------------------------------------------------------------------------


def test_engine_compiles_successful_trace(tmp_path: Path) -> None:
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import DevWorld

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None, world=DevWorld(), persist_dir=tmp_path)

    eng._maybe_compile_experience(_tool_trace())

    saved = tmp_path / "goal_templates.json"
    assert saved.exists()
    data = json.loads(saved.read_text())
    assert data
    assert data[0]["sub_goal_templates"][0]["strategy_params"] == _TOOL_PARAMS
    # A failed trace must not be compiled.
    before = len(eng._successful_traces)
    eng._maybe_compile_experience(
        ExecutionTrace(goal_tree=GoalTree("x", ()), steps=(), success=False, total_duration_sec=0.0)
    )
    assert len(eng._successful_traces) == before


# ---------------------------------------------------------------------------
# W1.1 — evidence gate on the compile path: a no-evidence "success" must NOT
# compile into a reusable 'verified' template (it would dilute the moat).
# ---------------------------------------------------------------------------


def _visual_override_trace(goal: str = "create config.txt with ready") -> ExecutionTrace:
    """A 'successful' trace whose pass is a VLM visual override (no deterministic
    evidence) — same structure as ``_tool_trace`` so the ONLY difference that
    blocks compilation is the missing evidence, not the shape."""
    sg = SubGoal(
        name="create_config",
        description="write config.txt",
        verify="path_contains('config.txt', 'ready')",
        strategy="tool_call",
        strategy_params=_TOOL_PARAMS,
    )
    return ExecutionTrace(
        goal_tree=GoalTree(goal=goal, sub_goals=(sg,)),
        steps=(StepRecord("create_config", "tool_call", True, True, 0.1, visual_override=True),),
        success=True,
        total_duration_sec=0.1,
    )


def test_visual_override_success_does_not_compile(tmp_path: Path) -> None:
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import DevWorld

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None, world=DevWorld(), persist_dir=tmp_path)

    # A visual-override "success" must NOT enter _successful_traces or compile.
    eng._maybe_compile_experience(_visual_override_trace())
    assert len(eng._successful_traces) == 0
    assert not (tmp_path / "goal_templates.json").exists()

    # A real-evidence success on the SAME structure still compiles.
    eng._maybe_compile_experience(_tool_trace())
    assert len(eng._successful_traces) == 1
    saved = tmp_path / "goal_templates.json"
    assert saved.exists()
    data = json.loads(saved.read_text())
    assert data[0]["sub_goal_templates"][0]["strategy_params"] == _TOOL_PARAMS


# ---------------------------------------------------------------------------
# R1 (was W1.1) — MCP/world= regression: init_vgg must SINGLE-SOURCE the live
# verify namespace into the GoalExecutor reward gate. The old is_robot flag (and
# its world bypass) is GONE: the executor's reward gate is now evidence-honest via
# ``_verify_oracle_names()``, which reads the SAME namespace GoalVerifier uses
# (engine._build_verifier_namespace, with the active world merged on top). A LIVE
# robot-control entry point (mcp/server.py) that omits world= would build the
# executor over a namespace without the robot oracles -> robot steps could never
# reach GROUNDED. So init_vgg must wire the world into the namespace.
# ---------------------------------------------------------------------------


def test_init_vgg_robot_world_wires_live_namespace_into_executor() -> None:
    # R1: the executor's reward-gate oracle names are SINGLE-SOURCED from the SAME
    # namespace the engine's GoalVerifier uses (no second hand-authored copy, no
    # is_robot flag). With agent=None the RobotWorld adds no embodiment oracles, so
    # the meaningful invariant is the single-source identity, asserted here.
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import RobotWorld

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None, world=RobotWorld())
    assert not hasattr(eng._goal_executor, "_is_robot")  # the bypass flag is GONE
    assert (
        eng._goal_executor._verify_oracle_names()
        == frozenset(eng._build_verifier_namespace(None).keys())
    )


def test_init_vgg_dev_world_wires_live_namespace_into_executor() -> None:
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import DevWorld

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None, world=DevWorld())
    names = eng._goal_executor._verify_oracle_names()
    # The dev predicates anchor the gate; the SAME namespace single-sources it.
    assert "file_exists" in names
    assert names == frozenset(eng._build_verifier_namespace(None).keys())


def test_init_vgg_no_world_still_single_sources_namespace() -> None:
    # The legacy no-world path still builds the executor over the live namespace
    # (dev predicates), never over an empty/hand-authored allowlist.
    from zeno.vcli.engine import VectorEngine

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None)
    names = eng._goal_executor._verify_oracle_names()
    assert "file_exists" in names
    assert not hasattr(eng._goal_executor, "_is_robot")


def test_mcp_server_builds_engine_with_robot_world() -> None:
    """mcp/server.py:_build_engine must pass world=resolve_world(agent) so a robot
    agent's verify namespace (the sim oracles) is wired into the executor reward
    gate. Mirrors the live entry point end-to-end with the network/backend stubbed."""
    import zeno.mcp.server as srv

    captured: dict[str, object] = {}

    class _StubEngine:
        def init_vgg(self, **kwargs):
            captured["world"] = kwargs.get("world")

    class _StubBackend:
        pass

    class _StubAgent:
        _skill_registry = object()

    # _build_engine imports everything locally, so monkeypatch via the imported modules.
    import zeno.vcli.config as cfg
    import zeno.vcli.backends as backends
    import zeno.vcli.tools as vtools
    import zeno.vcli.tools.skill_wrapper as skw
    import zeno.vcli.prompt as prompt
    import zeno.vcli.engine as engine_mod
    import zeno.vcli.session as session_mod
    import zeno.vcli.worlds as worlds_mod

    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    try:
        mp.setattr(cfg, "resolve_credentials", lambda: ("k", "p", "m", None))
        mp.setattr(backends, "create_backend", lambda **_: _StubBackend())

        class _Reg:
            def register(self, *a, **k):
                pass

        mp.setattr(vtools, "CategorizedToolRegistry", lambda: _Reg())
        mp.setattr(vtools, "discover_categorized_tools", lambda: ([], {}))
        mp.setattr(skw, "wrap_skills", lambda _a: [])
        mp.setattr(prompt, "build_system_prompt", lambda agent=None: "sys")
        mp.setattr(engine_mod, "VectorEngine", lambda **_: _StubEngine())
        mp.setattr(session_mod, "create_session", lambda metadata=None: object())
        # A robot agent -> resolve_world returns the robot world.
        mp.setattr(worlds_mod, "resolve_world", lambda _agent: worlds_mod.RobotWorld())

        engine, _session = srv._build_engine(_StubAgent())
    finally:
        mp.undo()

    assert captured["world"] is not None
    # The robot world is wired into init_vgg -> its sim oracles reach the executor's
    # reward-gate namespace (single source). The is_robot bypass flag is gone (R1).
    assert captured["world"].is_robot() is True
