# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Phase A — verified agent kernel / world decoupling.

Covers: dev verify predicates (read-only + opt-in tests_pass), world
resolution + persona, GoalDecomposer vocabulary injection (dev) with robot
defaults preserved, VGG un-gated over a robot-free dev world, robot-path
regression, and tool category gating in the dev world.

The LLM backend is always mocked; no network, no robot deps.
"""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import Any

from vector_os_nano.vcli.worlds import (
    DevWorld,
    RobotWorld,
    resolve_world,
    dev_verify_namespace,
)
from vector_os_nano.vcli.worlds.dev import DEV_VOCAB


# ---------------------------------------------------------------------------
# Mock LLM backend (records system prompt, returns a fixed response)
# ---------------------------------------------------------------------------


class MockBackend:
    def __init__(self, response: str = "") -> None:
        self._response = response
        self.last_system: Any = None

    def call(self, messages, tools, system, max_tokens, on_text=None):
        self.last_system = system

        class _R:
            text = self._response

        return _R()


# ---------------------------------------------------------------------------
# Dev verify predicates
# ---------------------------------------------------------------------------


class TestDevPredicates:
    def test_read_only_predicates(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "greet.py").write_text("def greet():\n    return 'hi'\n")
        ns = dev_verify_namespace()
        assert set(ns) == {"file_exists", "grep_count", "path_contains"}
        assert ns["file_exists"]("greet.py") is True
        assert ns["file_exists"]("missing.py") is False
        assert ns["grep_count"]("def greet", "greet.py") == 1
        assert ns["path_contains"]("greet.py", "return 'hi'") is True

    def test_path_traversal_blocked(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        ns = dev_verify_namespace()
        # Escaping cwd must be rejected (observational predicates only).
        assert ns["file_exists"]("../../../../etc/hosts") is False
        assert ns["grep_count"]("root", "..") == 0
        assert ns["path_contains"]("../../etc/hosts", "localhost") is False

    def test_tests_pass_opt_in(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        # Disabled by default -> not even in the namespace.
        monkeypatch.delenv("VECTOR_DEV_ALLOW_TESTS", raising=False)
        assert "tests_pass" not in dev_verify_namespace()
        # Opt-in -> present and bounded; a trivially-true command returns True.
        monkeypatch.setenv("VECTOR_DEV_ALLOW_TESTS", "1")
        ns = dev_verify_namespace()
        assert "tests_pass" in ns
        py = sys.executable
        assert ns["tests_pass"](f'{py} -c "raise SystemExit(0)"') is True
        assert ns["tests_pass"](f'{py} -c "raise SystemExit(1)"') is False
        # A nonexistent command fails safe (no crash).
        assert ns["tests_pass"]("definitely-not-a-real-binary-xyz") is False


# ---------------------------------------------------------------------------
# World resolution + persona
# ---------------------------------------------------------------------------


class TestWorldResolution:
    def test_resolve(self) -> None:
        assert resolve_world(None).name == "dev"
        assert resolve_world(None).is_robot() is False
        assert resolve_world(SimpleNamespace()).name == "robot"
        assert resolve_world(SimpleNamespace()).is_robot() is True

    def test_personas_distinct(self) -> None:
        dev_role, dev_tools = DevWorld().persona_blocks()
        rob_role, rob_tools = RobotWorld().persona_blocks()
        assert "verified coding and automation agent" in dev_role
        assert "AI core of a real robot" in rob_role
        assert dev_role != rob_role


# ---------------------------------------------------------------------------
# GoalDecomposer vocabulary injection (T-VOCAB)
# ---------------------------------------------------------------------------


class TestDecomposerInjection:
    def _decomposer(self, **kw):
        from vector_os_nano.vcli.cognitive.goal_decomposer import GoalDecomposer

        return GoalDecomposer(MockBackend("{}"), **kw)

    def test_dev_vocab_in_prompt(self) -> None:
        gd = self._decomposer(**DEV_VOCAB.as_kwargs())
        prompt = gd._build_system_prompt()[0]["text"]
        assert "software task planner" in prompt
        assert "file_exists(path: str)" in prompt
        assert "nearest_room" not in prompt  # robot vocab gone

    def test_robot_defaults_preserved(self) -> None:
        gd = self._decomposer()  # no injection
        prompt = gd._build_system_prompt()[0]["text"]
        assert "robot task planner" in prompt
        assert "nearest_room" in prompt

    def test_validate_verify_dev(self) -> None:
        gd = self._decomposer(**DEV_VOCAB.as_kwargs())
        assert (
            gd._validate_verify("file_exists('greet.py')") == "file_exists('greet.py')"
        )
        assert gd._validate_verify("grep_count('def', 'a.py') > 0") is not None
        # robot predicate not in dev vocab -> rejected
        assert gd._validate_verify("nearest_room() == 'kitchen'") is None

    def test_validate_verify_robot_default(self) -> None:
        gd = self._decomposer()
        assert gd._validate_verify("nearest_room() == 'kitchen'") is not None


# ---------------------------------------------------------------------------
# VGG un-gated over the dev world (T-VGG)
# ---------------------------------------------------------------------------


def _make_engine(mock_response: str):
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.intent_router import IntentRouter
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry

    backend = MockBackend(mock_response)
    eng = VectorEngine(
        backend=backend,
        registry=CategorizedToolRegistry(),
        system_prompt=[],
        intent_router=IntentRouter(),
    )
    return eng


_DEV_TREE = json.dumps(
    {
        "goal": "create greet.py and define greet",
        "sub_goals": [
            {
                "name": "create_greet_file",
                "description": "create greet.py",
                "verify": "file_exists('greet.py')",
                "strategy": "",
                "timeout_sec": 30,
                "depends_on": [],
                "strategy_params": {},
                "fail_action": "",
            },
            {
                "name": "define_greet",
                "description": "define greet",
                "verify": "grep_count('def greet', 'greet.py') > 0",
                "strategy": "",
                "timeout_sec": 30,
                "depends_on": ["create_greet_file"],
                "strategy_params": {},
                "fail_action": "",
            },
        ],
        "context_snapshot": "",
    }
)


class TestVggDevDecompose:
    def test_decompose_without_robot(self) -> None:
        eng = _make_engine(_DEV_TREE)
        eng.init_vgg(agent=None, skill_registry=None, world=DevWorld())
        assert eng._vgg_enabled is True
        tree = eng.vgg_decompose("create greet.py then make sure greet is defined")
        assert tree is not None
        assert len(tree.sub_goals) == 2
        assert tree.sub_goals[0].verify == "file_exists('greet.py')"

    def test_plain_question_not_decomposed(self) -> None:
        eng = _make_engine(_DEV_TREE)
        eng.init_vgg(agent=None, skill_registry=None, world=DevWorld())
        assert eng.vgg_decompose("how are you today") is None

    def test_dev_verify_namespace_evaluates(self, tmp_path, monkeypatch) -> None:
        """The decomposed dev predicates actually evaluate via GoalVerifier."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "greet.py").write_text("def greet():\n    pass\n")
        from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier

        eng = _make_engine(_DEV_TREE)
        ns = eng._build_verifier_namespace(None)
        gv = GoalVerifier(ns)
        assert gv.verify("file_exists('greet.py')") is True
        assert gv.verify("grep_count('def greet', 'greet.py') > 0") is True


# ---------------------------------------------------------------------------
# Robot-path regression (T-ROBOT)
# ---------------------------------------------------------------------------


class TestRobotRegression:
    def test_robot_namespace_intact_plus_dev(self) -> None:
        eng = _make_engine("{}")
        base = SimpleNamespace(
            get_position=lambda: (1.0, 2.0, 0.0), get_heading=lambda: 0.5
        )
        agent = SimpleNamespace(_base=base, _spatial_memory=None, _object_memory=None)
        ns = eng._build_verifier_namespace(agent)
        # Robot primitives present...
        assert "get_position" in ns and "get_heading" in ns
        # ...and the dev predicates coexist.
        assert "file_exists" in ns and "grep_count" in ns

    def test_robot_world_uses_decomposer_defaults(self) -> None:
        assert RobotWorld().decompose_vocab() is None

    def test_robot_vgg_gated_on_base(self) -> None:
        """Robot world must NOT decompose before a base is connected."""
        eng = _make_engine(_DEV_TREE)
        agent_no_base = SimpleNamespace(_base=None, _skill_registry=None)
        eng.init_vgg(agent=agent_no_base, skill_registry=None, world=RobotWorld())
        assert eng.vgg_decompose("walk forward") is None


# ---------------------------------------------------------------------------
# Tool category gating in the dev world (T-TOOLS)
# ---------------------------------------------------------------------------


class TestToolGating:
    def _registry(self):
        from vector_os_nano.vcli.tools import discover_categorized_tools
        from vector_os_nano.vcli.tools.base import CategorizedToolRegistry

        reg = CategorizedToolRegistry()
        tools, cats = discover_categorized_tools()
        for t in tools:
            cat = next((c for c, names in cats.items() if t.name in names), "default")
            reg.register(t, category=cat)
        return reg

    def test_dev_excludes_robot_tools_routed(self) -> None:
        reg = self._registry()
        for c in ("robot", "diag", "system"):
            reg.disable_category(c)
        # Routed path (intent router output) must also honor disable.
        names = {
            s["name"]
            for s in reg.to_anthropic_schemas(categories=["code", "general", "system"])
        }
        assert "web_fetch" in names  # general kept
        assert "file_read" in names  # code kept
        assert "robot_status" not in names  # system (robot infra) gated
        assert "start_simulation" not in names
        assert "scene_graph_query" not in names  # robot gated

    def test_dev_excludes_robot_tools_default(self) -> None:
        reg = self._registry()
        for c in ("robot", "diag", "system"):
            reg.disable_category(c)
        names = {s["name"] for s in reg.to_anthropic_schemas()}
        assert "web_fetch" in names
        assert "ros2_topics" not in names

    def test_robot_world_keeps_all(self) -> None:
        reg = self._registry()  # nothing disabled (robot world)
        names = {s["name"] for s in reg.to_anthropic_schemas()}
        assert {"web_fetch", "robot_status", "scene_graph_query"} <= names
