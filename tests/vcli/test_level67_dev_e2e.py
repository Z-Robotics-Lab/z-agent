# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 67 — Phase B.1 end-to-end: dev world decompose -> execute -> evidence.

The full pipeline as one flow (units are covered by level63/64; this proves they
compose): a mocked LLM decomposes a task into a tool_call sub-goal, the real
GoalExecutor + ToolDispatcher actually write the file through the permission
gate, GoalVerifier confirms the deterministic predicate, and the trace is
evidence-gated. Also the deny path: a denied permission produces a failed,
non-evidenced trace and no file.

Pure kernel logic — no robot, no network, no mujoco fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vector_os_nano.vcli.cognitive.trace_store import evidence_passed

# Live verify-namespace callable names for the R1 evidence gate (replaces is_robot).
ORACLES = frozenset({
    "at_position", "facing", "visited", "holding_object", "arm_at_home",
    "file_exists", "path_contains", "get_position", "get_heading",
    "describe_scene", "detect_objects", "placed_count", "nearest_room",
    "objects_in_room", "find_object", "room_coverage",
})
from vector_os_nano.vcli.engine import VectorEngine
from vector_os_nano.vcli.permissions import PermissionContext
from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
from vector_os_nano.vcli.tools.file_tools import FileWriteTool
from vector_os_nano.vcli.worlds import DevWorld


def _goal_tree_json(file_path: str, content: str, verify: str) -> str:
    return json.dumps({
        "goal": f"create {file_path}",
        "sub_goals": [
            {
                "name": "write_target",
                "description": f"write {file_path}",
                "verify": verify,
                "strategy": "tool_call",
                "timeout_sec": 30,
                "depends_on": [],
                "strategy_params": {
                    "tool": "file_write",
                    "args": {"file_path": file_path, "content": content},
                },
                "fail_action": "",
            }
        ],
        "context_snapshot": "",
    })


class _MockBackend:
    """Returns a fixed decompose response; records call count."""

    def __init__(self, response_text: str) -> None:
        self._response = response_text
        self.calls = 0

    def call(self, messages: Any, tools: Any = None, system: Any = None,
             max_tokens: int = 0, on_text: Any = None) -> Any:
        self.calls += 1

        class _R:
            text = self._response

        return _R()


def _build_engine(backend: Any, resolver: Any, persist_dir: Path) -> VectorEngine:
    registry = CategorizedToolRegistry()
    registry.register(FileWriteTool(), category="code")
    engine = VectorEngine(backend=backend, registry=registry,
                          permissions=PermissionContext(), intent_router=None)
    engine.init_vgg(agent=None, skill_registry=None, world=DevWorld(),
                    tool_permission_resolver=resolver, persist_dir=persist_dir)
    assert engine._vgg_enabled is True
    return engine


def test_dev_e2e_tool_call_writes_and_is_evidenced(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    backend = _MockBackend(_goal_tree_json("hello.txt", "hello\n",
                                           "path_contains('hello.txt', 'hello')"))
    engine = _build_engine(backend, lambda _n, _p: "y", tmp_path)

    tree = engine._goal_decomposer.decompose("create hello.txt with hello", "")
    trace = engine.vgg_execute(tree)

    # The file was actually written through the permission gate.
    assert (tmp_path / "hello.txt").read_text() == "hello\n"
    # Verified + evidence-backed.
    assert trace.success is True
    assert trace.steps[0].verify_result is True
    assert evidence_passed(trace, ORACLES) is True


def test_dev_e2e_denied_permission_fails_without_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    backend = _MockBackend(_goal_tree_json("blocked.txt", "nope\n",
                                           "file_exists('blocked.txt')"))
    engine = _build_engine(backend, lambda _n, _p: "n", tmp_path)  # auto-deny

    tree = engine._goal_decomposer.decompose("create blocked.txt", "")
    trace = engine.vgg_execute(tree)

    assert not (tmp_path / "blocked.txt").exists()
    assert trace.success is False
    assert evidence_passed(trace, ORACLES) is False


def test_dev_e2e_off_allowlist_tool_is_blocked(tmp_path: Path, monkeypatch) -> None:
    """A sub-goal naming a tool outside DEV_TOOL_ALLOWLIST never executes."""
    monkeypatch.chdir(tmp_path)
    payload = json.dumps({
        "goal": "delete things",
        "sub_goals": [{
            "name": "run_cmd",
            "description": "run a tool not on the allowlist",
            "verify": "file_exists('x.txt')",
            "strategy": "tool_call",
            "timeout_sec": 30,
            "depends_on": [],
            "strategy_params": {"tool": "world_query", "args": {}},
            "fail_action": "",
        }],
        "context_snapshot": "",
    })
    backend = _MockBackend(payload)
    engine = _build_engine(backend, lambda _n, _p: "y", tmp_path)

    tree = engine._goal_decomposer.decompose("use a robot tool", "")
    trace = engine.vgg_execute(tree)

    assert trace.success is False  # off-allowlist -> denied before execution


def test_dev_e2e_run_compiles_a_template(tmp_path: Path, monkeypatch) -> None:
    """A successful run feeds the experience compiler (the learning hook fires).

    Template *matching* nuance is covered by level66; here we only assert the
    successful run produced a persisted template carrying the tool payload.
    """
    monkeypatch.chdir(tmp_path)
    backend = _MockBackend(_goal_tree_json("reuse.txt", "data\n",
                                           "path_contains('reuse.txt', 'data')"))
    engine = _build_engine(backend, lambda _n, _p: "y", tmp_path)

    tree = engine._goal_decomposer.decompose("create reuse.txt with data", "")
    engine.vgg_execute(tree)  # success -> compiled into the template library

    saved = tmp_path / "goal_templates.json"
    assert saved.exists()
    data = json.loads(saved.read_text())
    assert data
    assert data[0]["sub_goal_templates"][0]["strategy_params"]["tool"] == "file_write"
