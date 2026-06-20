# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""D9 #2 latency: batching the action + its verify into ONE response cuts native
round-trips. The user's "load 好几秒" is the SYNCHRONOUS LLM round-trips (per-turn
setup is ~0.04ms — negligible). The runner already dispatches multiple tool calls
in one turn (native_loop.py:528-543); the system prompt now instructs the model to
emit (action, verify) together. This pins that batching => fewer backend.call
round-trips, with an identical honest trace (one action->verify step).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


class _CountingBackend:
    """Wraps a scripted backend, counting .call() round-trips."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = 0

    def call(self, **kwargs):
        self.calls += 1
        return self._inner.call(**kwargs)


def _run(tool_script, on_progress=None):
    from vector_os_nano.core.agent import Agent
    from vector_os_nano.core.types import SkillResult
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.permissions import PermissionContext
    from vector_os_nano.vcli.session import Session
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
    from vector_os_nano.vcli.worlds.dev import DevWorld
    from tests.harness.fake_backend import FakeToolScriptBackend

    class _WriteFileSkill:
        name = "write_file"
        description = "TEST: write text to a file (a dev action)."
        parameters = {"file_path": {"type": "string", "required": True},
                      "content": {"type": "string", "required": True}}
        preconditions: list = []
        effects: dict = {}

        def execute(self, params, context):
            Path(params["file_path"]).write_text(str(params.get("content", "")), encoding="utf-8")
            return SkillResult(success=True, result_data={"file_path": params.get("file_path")})

    work = tempfile.mkdtemp(prefix="batch_rt_")
    prev = os.getcwd()
    os.chdir(work)
    try:
        agent = Agent(config={})
        agent._skill_registry.register(_WriteFileSkill())
        backend = _CountingBackend(FakeToolScriptBackend.from_tool_script(tool_script))
        eng = VectorEngine(backend=backend, registry=CategorizedToolRegistry(),
                           permissions=PermissionContext())
        eng._world = DevWorld()
        eng.init_vgg(agent=agent, skill_registry=agent._skill_registry, world=DevWorld())
        eng._vgg_agent = agent
        eng._backend = backend
        session = Session(session_id="batch", created_at="t", updated_at="t",
                          path=Path(work) / "s.jsonl")
        trace = eng.run_turn_native("create out.txt containing ready", session=session,
                                    on_progress=on_progress)
        return backend.calls, trace
    finally:
        os.chdir(prev)


def test_batched_action_verify_uses_fewer_roundtrips():
    from tests.harness.fake_backend import tool_turn

    write = ("write_file", {"file_path": "out.txt", "content": "ready\n"})
    verify = ("verify", {"expr": "path_contains('out.txt', 'ready')"})

    # Sequential: action / verify / finish — 3 round-trips.
    seq_calls, seq_trace = _run([tool_turn(write), tool_turn(verify), tool_turn(end=True)])
    # Batched: (action, verify) in ONE response / finish — 2 round-trips.
    batch_calls, batch_trace = _run([tool_turn(write, verify), tool_turn(end=True)])

    assert seq_calls == 3
    assert batch_calls == 2
    assert batch_calls < seq_calls  # the latency win is realized by the runner
    # Same honest trace shape: exactly one action->verify step either way.
    assert len(seq_trace.steps) == 1
    assert len(batch_trace.steps) == 1


def test_on_progress_streams_steps():
    """D9 #2 perceived latency: on_progress fires per tool call (+ model text), so
    the REPL spinner shows live activity instead of a frozen 'load 好几秒'."""
    from tests.harness.fake_backend import tool_turn

    msgs: list[str] = []
    _run(
        [tool_turn(("write_file", {"file_path": "out.txt", "content": "ready\n"}),
                   ("verify", {"expr": "path_contains('out.txt', 'ready')"})),
         tool_turn(end=True)],
        on_progress=msgs.append,
    )
    assert msgs, "on_progress never fired — the wait stays opaque"
    blob = " | ".join(msgs)
    assert "write_file" in blob          # the action streamed
    assert "verify" in blob              # the verify streamed
