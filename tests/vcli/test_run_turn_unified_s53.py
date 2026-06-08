# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Stage 5 (S5.3) — the unified closed-loop controller, ``run_turn_unified``.

S5.3 adds ONE controller that ALWAYS produces a GoalTree and runs the SAME harness
loop for every interaction shape — answer-only chat, a 1-step skill/tool plan, an
N-step DAG, a foreach loop — and returns ONE result type
(:class:`UnifiedTurnResult`). It is DARK-LAUNCHED: ``cli.py`` / ``mcp/server.py``
still fork on the old paths; only these tests reach the new method.

The deliverable is PARITY: for a fixed corpus of turns (chat/greeting, a question,
a 1-skill turn, a multi-step plan, a denied-permission turn, a foreach turn) the
unified controller reproduces the OBSERVABLE result of the old path —
- the same answer text for chat (from the ReAct ``run_turn`` loop),
- the same tool outcomes / file effects,
- the same per-step verify PASS/FAIL and the same evidence-gate verdict,
- the same permission (deny) behaviour,
while ALSO closing the loop (every turn now yields a verified-loop trace). The moat
(rule 5) is preserved: an answer-only step is exempt by design, but an action step
with no deterministic predicate still fails the gate.

Pure kernel logic on the MOCK backend — no live LLM, no robot, no mujoco.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vector_os_nano.vcli.backends.types import LLMResponse, LLMToolCall
from vector_os_nano.vcli.cognitive.trace_store import evidence_passed
from vector_os_nano.vcli.engine import UnifiedTurnResult, VectorEngine
from vector_os_nano.vcli.intent_router import IntentRouter
from vector_os_nano.vcli.permissions import PermissionContext
from vector_os_nano.vcli.session import TokenUsage, create_session
from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
from vector_os_nano.vcli.tools.file_tools import FileWriteTool
from vector_os_nano.vcli.worlds import DevWorld


# ---------------------------------------------------------------------------
# Mock backends (no network)
# ---------------------------------------------------------------------------


class _ChatBackend:
    """Returns a fixed chat answer for the ReAct loop; streams it via on_text.

    Used for the answer-only turns. ``run_turn`` calls ``.call(...)`` with text
    streaming; this returns end_turn with no tool calls (a pure conversational
    answer). The same backend is wired into the engine, but the answer-plan harness
    never calls it (``answer_plan`` is deterministic), so call-count stays at 1.
    """

    def __init__(self, answer: str) -> None:
        self._answer = answer
        self.calls = 0

    def call(self, messages=None, tools=None, system=None, max_tokens=0,
             on_text=None, on_reasoning=None, **_: Any) -> LLMResponse:
        self.calls += 1
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


# ---------------------------------------------------------------------------
# Engine builders (dev world, real executor + verifier + dispatcher)
# ---------------------------------------------------------------------------


def _dev_engine(backend: Any, resolver: Any, persist_dir: Path,
                intent_router: Any = None) -> VectorEngine:
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


def _goal_tree_json(file_path: str, content: str, verify: str) -> str:
    return json.dumps({
        "goal": f"create {file_path}",
        "sub_goals": [{
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
        }],
        "context_snapshot": "",
    })


# ===========================================================================
# 1. CHAT / GREETING — answer-only turn
# ===========================================================================


def test_chat_greeting_answer_parity(tmp_path: Path) -> None:
    """A greeting routes to the answer path: same text as ReAct, verified loop."""
    backend = _ChatBackend("Hi! I'm Vector OS.")
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())
    session = create_session(directory=tmp_path / "_sessions")

    streamed: list[str] = []
    result = engine.run_turn_unified(
        "hello", session, on_text=streamed.append,
    )

    assert isinstance(result, UnifiedTurnResult)
    # PARITY: the answer text matches what the ReAct loop produced (+ streamed it).
    assert result.text == "Hi! I'm Vector OS."
    assert "".join(streamed) == "Hi! I'm Vector OS."
    # CLOSED LOOP: an answer-only trace was produced and verifies true.
    assert result.intent.route == "tool_use"
    assert result.trace is not None
    assert result.trace.success is True
    assert len(result.trace.steps) == 1
    answer_sg = result.trace.goal_tree.sub_goals[0]
    assert answer_sg.answer_only is True
    assert answer_sg.strategy == "answer"
    # MOAT: the answer-only step is evidence-backed BY DESIGN (dev world strict).
    assert result.verified is True
    assert evidence_passed(result.trace, is_robot=False) is True
    # The backend was called exactly once (chat answer); answer_plan is deterministic.
    assert backend.calls == 1
    # The snapshot is the JSON-safe export view and round-trips.
    json.dumps(result.snapshot)
    assert result.snapshot["success"] is True


def test_question_answer_parity(tmp_path: Path) -> None:
    """A question (conversational guard) also routes to the answer path."""
    backend = _ChatBackend("Because the sim warms up its caches first.")
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("为什么一开始那么卡？", session)

    assert result.intent.route == "tool_use"  # conversational guard short-circuits
    assert result.text == "Because the sim warms up its caches first."
    assert result.trace is not None and result.trace.success is True
    assert result.verified is True


def test_answer_path_preserves_tool_calls(tmp_path: Path) -> None:
    """A chat turn that calls a read-only tool surfaces those tool calls.

    The ReAct loop owns tool dispatch on the answer path; the unified result must
    carry the tool calls it executed (parity with run_turn's TurnResult.tool_calls).
    """

    class _ToolThenAnswer:
        """First round: a read-only glob call. Second round: the answer."""

        def __init__(self) -> None:
            self.calls = 0

        def call(self, messages=None, tools=None, system=None, max_tokens=0,
                 on_text=None, on_reasoning=None, **_: Any) -> LLMResponse:
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    text="", stop_reason="tool_use",
                    tool_calls=[LLMToolCall(id="t1", name="file_write",
                                            input={"file_path": str(tmp_path / "a.txt"),
                                                   "content": "x"})],
                )
            if on_text is not None:
                on_text("done")
            return LLMResponse(text="done", stop_reason="end_turn")

    backend = _ToolThenAnswer()
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=IntentRouter())
    session = create_session(directory=tmp_path / "_sessions")
    result = engine.run_turn_unified("hello there", session,
                                     ask_permission=lambda _n, _p: "y")

    assert result.text == "done"
    assert [tc.tool_name for tc in result.tool_calls] == ["file_write"]
    # The tool actually ran through the gate on the answer path.
    assert (tmp_path / "a.txt").read_text() == "x"


# ===========================================================================
# 2. 1-SKILL / 1-TOOL PLAN — action turn
# ===========================================================================


def test_single_tool_plan_parity(tmp_path: Path, monkeypatch) -> None:
    """A 1-step tool_call plan: same file effect + same evidence verdict as VGG."""
    monkeypatch.chdir(tmp_path)
    # is_complex("create file ...") triggers via the action-verb path is false; we
    # force the vgg route by giving a router whose should_use_vgg returns True.
    decompose = _goal_tree_json("hello.txt", "hello\n",
                                "path_contains('hello.txt', 'hello')")

    class _VggRouter(IntentRouter):
        def should_use_vgg(self, msg, skill_registry=None) -> bool:
            return True

    backend = _DecomposeBackend(decompose)
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=_VggRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("create hello.txt with hello", session)

    assert result.intent.route == "vgg"
    assert result.trace is not None
    # PARITY with the old VGG path (test_level67): file written, verified, evidenced.
    assert (tmp_path / "hello.txt").read_text() == "hello\n"
    assert result.trace.success is True
    assert result.trace.steps[0].verify_result is True
    assert result.verified is True
    assert evidence_passed(result.trace, is_robot=False) is True


# ===========================================================================
# 3. DENIED PERMISSION — action turn, fails without evidence
# ===========================================================================


def test_denied_permission_parity(tmp_path: Path, monkeypatch) -> None:
    """A denied tool plan fails + no file + no evidence — same as the VGG path."""
    monkeypatch.chdir(tmp_path)
    decompose = _goal_tree_json("blocked.txt", "nope\n", "file_exists('blocked.txt')")

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
    assert result.trace is not None
    assert result.trace.success is False
    assert result.verified is False
    assert evidence_passed(result.trace, is_robot=False) is False


# ===========================================================================
# 4. MULTI-STEP PLAN — DAG with a dependency
# ===========================================================================


def test_multi_step_plan_parity(tmp_path: Path, monkeypatch) -> None:
    """A 2-step plan (write then re-check) runs both steps in order, all verified."""
    monkeypatch.chdir(tmp_path)
    payload = json.dumps({
        "goal": "create two files",
        "sub_goals": [
            {
                "name": "write_a",
                "description": "write a.txt",
                "verify": "path_contains('a.txt', 'AAA')",
                "strategy": "tool_call",
                "timeout_sec": 30,
                "depends_on": [],
                "strategy_params": {"tool": "file_write",
                                    "args": {"file_path": "a.txt", "content": "AAA"}},
            },
            {
                "name": "write_b",
                "description": "write b.txt",
                "verify": "path_contains('b.txt', 'BBB')",
                "strategy": "tool_call",
                "timeout_sec": 30,
                "depends_on": ["write_a"],
                "strategy_params": {"tool": "file_write",
                                    "args": {"file_path": "b.txt", "content": "BBB"}},
            },
        ],
        "context_snapshot": "",
    })

    class _VggRouter(IntentRouter):
        def should_use_vgg(self, msg, skill_registry=None) -> bool:
            return True

    backend = _DecomposeBackend(payload)
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=_VggRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("create a and b", session)

    assert result.intent.route == "vgg"
    assert (tmp_path / "a.txt").read_text() == "AAA"
    assert (tmp_path / "b.txt").read_text() == "BBB"
    assert result.trace is not None
    assert len(result.trace.steps) == 2
    assert all(s.verify_result for s in result.trace.steps)
    assert result.verified is True


# ===========================================================================
# 5. FOREACH — loop over a produced list
# ===========================================================================


def _foreach_tree() -> Any:
    """A foreach GoalTree: a code producer emits a 2-item list; the body writes one
    file per item, binding ``${it.name}`` through the pure blackboard path."""
    from vector_os_nano.vcli.cognitive.types import ForEachSpec, GoalTree, SubGoal

    produce = SubGoal(
        name="produce",
        description="produce the item list",
        verify="True",
        strategy="code_as_policy",
        # The CodeExecutor captures the value of the LAST expression as the step's
        # output; a bare dict literal makes ``produce.output.items`` resolvable.
        strategy_params={
            "code": "{'items': [{'name': 'one'}, {'name': 'two'}]}"
        },
    )
    write_item = SubGoal(
        name="write_item",
        description="write the item file",
        verify="path_contains('${it.name}.txt', '${it.name}')",
        strategy="tool_call",
        strategy_params={
            "tool": "file_write",
            "args": {"file_path": "${it.name}.txt", "content": "${it.name}"},
        },
    )
    write_each = SubGoal(
        name="write_each",
        description="write one file per item",
        verify="True",
        strategy="",
        depends_on=("produce",),
        foreach=ForEachSpec(
            source_step="produce", source_path="items", var="it",
            body=(write_item,),
        ),
    )
    return GoalTree(goal="write a file per item", sub_goals=(produce, write_each))


def _decomposer_returning(tree: Any) -> Any:
    class _Dec:
        def decompose(self, task: str, world_context: str) -> Any:
            return tree

    return _Dec()


def test_foreach_plan_parity(tmp_path: Path, monkeypatch) -> None:
    """A foreach plan writes one file per produced item; all children verified.

    A code producer emits a list of items captured on the blackboard; the foreach
    body writes one file per item (binding ``${it.name}`` by pure path traversal).
    The unified controller runs the SAME harness loop as a direct ``vgg_execute``,
    so the loop expands and every child verifies — parity asserted against that
    baseline. The decomposer is stubbed to the foreach tree (its ``foreach`` /
    ``code_as_policy`` vocab is not part of the chat-oriented dev DecomposeVocab),
    which is the established pattern for foreach harness tests.
    """
    monkeypatch.chdir(tmp_path)

    class _VggRouter(IntentRouter):
        def should_use_vgg(self, msg, skill_registry=None) -> bool:
            return True

    engine = _dev_engine(_DecomposeBackend("{}"), lambda _n, _p: "y", tmp_path,
                         intent_router=_VggRouter())
    # Force the (complex) slow path so vgg_decompose consults the decomposer, and
    # stub the decomposer to the foreach tree.
    engine._goal_decomposer = _decomposer_returning(_foreach_tree())

    class _ComplexRouter(_VggRouter):
        def is_complex(self, msg) -> bool:
            return True

    engine._intent_router = _ComplexRouter()
    session = create_session(directory=tmp_path / "_sessions")

    # PARITY baseline: run the SAME tree directly through vgg_execute.
    baseline = engine.vgg_execute(_foreach_tree())
    assert baseline.success is True
    for n in ("one", "two"):
        (tmp_path / f"{n}.txt").unlink()  # clean up so the unified run re-creates

    result = engine.run_turn_unified("write a file per item", session)

    assert result.intent.route == "vgg"
    assert result.trace is not None
    assert result.trace.success is True
    # Same observable effect: one file per item, each containing its name.
    assert (tmp_path / "one.txt").read_text() == "one"
    assert (tmp_path / "two.txt").read_text() == "two"
    # Same number of executed steps as the baseline (producer + 2 loop children).
    assert len(result.trace.steps) == len(baseline.steps)


# ===========================================================================
# 6. DEGRADE — VGG unavailable still returns the chat text (no silent drop)
# ===========================================================================


def test_unified_degrades_to_text_without_vgg(tmp_path: Path) -> None:
    """When VGG is disabled, the answer text is still returned (trace=None)."""
    backend = _ChatBackend("plain answer")
    engine = VectorEngine(backend=backend, registry=CategorizedToolRegistry(),
                          permissions=PermissionContext(), intent_router=None)
    # init_vgg NOT called -> _vgg_enabled is False -> classify_intent => tool_use.
    assert engine._vgg_enabled is False
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("hello", session)

    assert result.text == "plain answer"
    assert result.intent.route == "tool_use"
    assert result.trace is None
    assert result.verified is False


# ===========================================================================
# 7. MOAT — an unverified action plan still fails the gate through the unified path
# ===========================================================================


def test_unified_action_no_predicate_still_fails_gate(tmp_path: Path, monkeypatch) -> None:
    """An action step with a sentinel verify is NOT laundered as verified.

    The decomposer emits a tool_call with verify="True" (no deterministic
    predicate). The harness runs it (the file IS written), but the evidence gate
    refuses to count it as verified — the unified result.verified is False even
    though the run "succeeded". The moat (rule 5) holds through the merge.
    """
    monkeypatch.chdir(tmp_path)
    payload = json.dumps({
        "goal": "write a file with no real check",
        "sub_goals": [{
            "name": "write_it",
            "description": "write sneaky.txt",
            "verify": "True",  # sentinel — no evidence
            "strategy": "tool_call",
            "timeout_sec": 30,
            "depends_on": [],
            "strategy_params": {"tool": "file_write",
                                "args": {"file_path": "sneaky.txt", "content": "x"}},
        }],
        "context_snapshot": "",
    })

    class _VggRouter(IntentRouter):
        def should_use_vgg(self, msg, skill_registry=None) -> bool:
            return True

    backend = _DecomposeBackend(payload)
    engine = _dev_engine(backend, lambda _n, _p: "y", tmp_path,
                         intent_router=_VggRouter())
    session = create_session(directory=tmp_path / "_sessions")

    result = engine.run_turn_unified("write sneaky.txt", session)

    # The run "succeeded" (the file was written + sentinel verify is truthy)...
    assert result.trace is not None
    assert (tmp_path / "sneaky.txt").read_text() == "x"
    assert result.trace.success is True
    # ...but it is NOT verified — no deterministic predicate backs it (the moat).
    assert result.verified is False
    assert evidence_passed(result.trace, is_robot=False) is False
