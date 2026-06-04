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

from vector_os_nano.vcli.cognitive.experience_compiler import ExperienceCompiler
from vector_os_nano.vcli.cognitive.goal_decomposer import GoalDecomposer
from vector_os_nano.vcli.cognitive.template_library import TemplateLibrary
from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from vector_os_nano.vcli.worlds.dev import DEV_VOCAB


_TOOL_PARAMS = {"tool": "file_write", "args": {"file_path": "config.txt", "content": "ready\n"}}


def _tool_trace(goal: str = "create config.txt with ready") -> ExecutionTrace:
    sg = SubGoal(
        name="write_config",
        description="write config.txt",
        verify="path_contains('config.txt', 'ready')",
        strategy="tool_call",
        strategy_params=_TOOL_PARAMS,
    )
    return ExecutionTrace(
        goal_tree=GoalTree(goal=goal, sub_goals=(sg,)),
        steps=(StepRecord("write_config", "tool_call", True, True, 0.1),),
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
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.worlds import DevWorld

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
