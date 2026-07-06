# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Stage 5 (S5.4) — frontend cut-over regressions for the unified controller.

S5.4 cuts the CLI and MCP frontends over to ``run_turn_unified`` and DEMOTES the
keyword ``should_use_vgg`` gate from a correctness fork (in front of verify) to an
optimization HINT feeding the decomposer. The conversational-question guard stays
a guard: "hello" / "为什么这么慢" / questions must still answer DIRECTLY and CHEAPLY
(no heavy decomposition, no action tools), while real commands ("把所有东西抓一遍",
a skill) still produce a verified plan.

These assert OBSERVABLE behaviour through the ONE controller both frontends now
call — on the MOCK backend, no live LLM / robot / mujoco. They guard the exact
regressions the cut-over risks:

  (a) conversational input -> answer-only path, NO action plan, NO action tools;
  (b) a real command -> the vgg plan path, verified;
  (c) the scope command "把所有东西抓一遍" -> the complex (long-chain) plan path;
  (d) a denied-permission action turn still denies (covered in S5.3, re-asserted
      here through the real-router routing decision);
  (e) the legacy fallback (run_turn) is still reachable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from zeno.vcli.backends.types import LLMResponse, LLMToolCall
from zeno.vcli.cognitive.trace_store import evidence_passed

# Live verify-namespace callable names for the R1 evidence gate (replaces is_robot).
ORACLES = frozenset({
    "at_position", "facing", "visited", "holding_object", "arm_at_home",
    "file_exists", "path_contains", "get_position", "get_heading",
    "describe_scene", "detect_objects", "placed_count", "nearest_room",
    "objects_in_room", "find_object", "room_coverage",
})
from zeno.vcli.engine import UnifiedTurnResult, VectorEngine
from zeno.vcli.intent_router import IntentRouter
from zeno.vcli.permissions import PermissionContext
from zeno.vcli.session import TokenUsage, create_session
from zeno.vcli.tools.base import CategorizedToolRegistry
from zeno.vcli.tools.file_tools import FileWriteTool
from zeno.vcli.worlds import DevWorld


# ---------------------------------------------------------------------------
# Mock backend that records every call + would emit an action tool if asked
# ---------------------------------------------------------------------------


class _SpyChatBackend:
    """Streams a fixed chat answer; records calls so we can prove no decomposition.

    If the controller ever wrongly took the action-plan path for conversational
    input, the GoalDecomposer would call this backend with a decompose prompt; we
    assert the backend is called exactly ONCE (the single ReAct answer round-trip)
    and that no action tool ever ran.
    """

    def __init__(self, answer: str) -> None:
        self._answer = answer
        self.calls = 0
        self.last_system: Any = None

    def call(self, messages=None, tools=None, system=None, max_tokens=0,
             on_text=None, on_reasoning=None, **_: Any) -> LLMResponse:
        self.calls += 1
        self.last_system = system
        if on_text is not None:
            on_text(self._answer)
        return LLMResponse(text=self._answer, tool_calls=[], stop_reason="end_turn",
                           usage=TokenUsage(input_tokens=3, output_tokens=5))


class _DecomposeBackend:
    """Returns a fixed decompose JSON for the VGG (plan) path."""

    def __init__(self, response_text: str) -> None:
        self._response = response_text
        self.calls = 0

    def call(self, messages=None, tools=None, system=None, max_tokens=0,
             on_text=None, **_: Any) -> Any:
        self.calls += 1

        class _R:
            text = self._response

        return _R()


def _dev_engine(backend: Any, resolver: Any, persist_dir: Path,
                intent_router: Any) -> VectorEngine:
    registry = CategorizedToolRegistry()
    registry.register(FileWriteTool(), category="code")
    engine = VectorEngine(
        backend=backend, registry=registry,
        permissions=PermissionContext(), intent_router=intent_router,
    )
    engine.init_vgg(agent=None, skill_registry=None, world=DevWorld(),
                    tool_permission_resolver=resolver, persist_dir=persist_dir)
    assert engine._vgg_enabled is True
    return engine


# ===========================================================================
# (a) Conversational input answers directly — NO action plan, NO action tools
# ===========================================================================


def test_greeting_answers_directly_no_action_plan(tmp_path: Path) -> None:
    """"hello" -> answer-only path. Backend called once; no decomposition."""
    backend = _SpyChatBackend("Hi, I'm Vector OS.")
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("hello", session)

    assert isinstance(result, UnifiedTurnResult)
    # Routed to the cheap answer path via the conversational guard — NOT a plan.
    assert result.intent.route == "tool_use"
    assert result.text == "Hi, I'm Vector OS."
    # The ONLY trace is the trivially-verified answer-only step (no action plan).
    assert result.trace is not None
    assert len(result.trace.steps) == 1
    assert result.trace.goal_tree.sub_goals[0].answer_only is True
    # No action tool ran (the chat turn touched nothing on disk).
    assert [tc.tool_name for tc in result.tool_calls] == []
    assert list(tmp_path.glob("*.txt")) == []
    # Exactly one backend round-trip — the decomposer was never consulted.
    assert backend.calls == 1


def test_why_question_answers_directly_no_action_plan(tmp_path: Path) -> None:
    """"为什么这么慢" -> answer path (guard), not a measure-startup action plan."""
    backend = _SpyChatBackend("因为仿真在预热缓存。")
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("为什么这么慢", session)

    assert result.intent.route == "tool_use"
    assert result.text == "因为仿真在预热缓存。"
    assert result.trace is not None
    assert result.trace.goal_tree.sub_goals[0].answer_only is True
    assert backend.calls == 1


# ===========================================================================
# (b) A real command routes to the VGG plan path and verifies
# ===========================================================================


def test_command_routes_to_verified_plan(tmp_path: Path, monkeypatch) -> None:
    """A real action command -> vgg plan path, file written + evidence-verified."""
    monkeypatch.chdir(tmp_path)
    decompose = json.dumps({
        "goal": "create note.txt",
        "sub_goals": [{
            "name": "write_note",
            "description": "write note.txt",
            "verify": "path_contains('note.txt', 'note')",
            "strategy": "tool_call",
            "timeout_sec": 30,
            "depends_on": [],
            "strategy_params": {
                "tool": "file_write",
                "args": {"file_path": "note.txt", "content": "note\n"},
            },
        }],
        "context_snapshot": "",
    })

    class _VggRouter(IntentRouter):
        def should_use_vgg(self, msg, skill_registry=None) -> bool:
            return True

    backend = _DecomposeBackend(decompose)
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=_VggRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("create note.txt with note", session)

    assert result.intent.route == "vgg"
    assert (tmp_path / "note.txt").read_text() == "note\n"
    assert result.trace is not None and result.trace.success is True
    assert result.verified is True
    assert evidence_passed(result.trace, ORACLES) is True


# ===========================================================================
# (c) The scope command stays on the complex (long-chain) plan path
# ===========================================================================


def test_scope_command_routes_complex(tmp_path: Path) -> None:
    """"把所有东西抓一遍" -> vgg route, complex=True (the foreach long-chain path).

    The keyword hint still recognises a scope command as complex, so the unified
    controller decomposes it (the long-chain path) rather than answering it. We
    assert the ROUTING decision (real IntentRouter), which is what the cut-over
    must preserve; the foreach expansion itself is covered in the S5.3 suite.
    """
    backend = _DecomposeBackend("{}")
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())

    decision = engine.classify_intent("把所有东西抓一遍")
    assert decision.route == "vgg"
    assert decision.complex is True
    assert decision.use_vgg is True


# ===========================================================================
# (d) A denied-permission action turn still denies (no file, no evidence)
# ===========================================================================


def test_denied_action_turn_still_denies(tmp_path: Path, monkeypatch) -> None:
    """A denied tool plan fails: no file, not verified — through the real router."""
    monkeypatch.chdir(tmp_path)
    decompose = json.dumps({
        "goal": "create blocked.txt",
        "sub_goals": [{
            "name": "write_blocked",
            "description": "write blocked.txt",
            "verify": "file_exists('blocked.txt')",
            "strategy": "tool_call",
            "timeout_sec": 30,
            "depends_on": [],
            "strategy_params": {
                "tool": "file_write",
                "args": {"file_path": "blocked.txt", "content": "x"},
            },
        }],
        "context_snapshot": "",
    })

    class _VggRouter(IntentRouter):
        def should_use_vgg(self, msg, skill_registry=None) -> bool:
            return True

    backend = _DecomposeBackend(decompose)
    engine = _dev_engine(backend, lambda _n, _p: "n", tmp_path,  # auto-deny
                         intent_router=_VggRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("create blocked.txt", session)

    assert result.intent.route == "vgg"
    assert not (tmp_path / "blocked.txt").exists()
    assert result.trace is not None and result.trace.success is False
    assert result.verified is False


# ===========================================================================
# (e) The legacy fallback (run_turn) is still available and unchanged
# ===========================================================================


def test_legacy_run_turn_still_available(tmp_path: Path) -> None:
    """The old open ReAct loop (run_turn) still works as the one-release fallback.

    The frontends gate on VECTOR_LEGACY_TURN to call run_turn directly; here we
    assert run_turn itself is intact (a chat turn returns the text with no trace),
    independent of the unified controller.
    """
    backend = _SpyChatBackend("legacy answer")
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())
    session = create_session(directory=tmp_path / "_sessions")

    turn = engine.run_turn("hello", session)

    assert turn.text == "legacy answer"
    assert turn.tool_calls == []
    assert turn.stop_reason == "end_turn"
