# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Markup-injection display safety (code-review fix).

Model/user-authored text (goal strings, verify expressions, strategy/diag
text) is interpolated into Rich markup strings before being printed. Any
stray ``[...]`` in that text (e.g. a bracketed file path like
``[/tmp/out.json]``, or Rich markup an LLM emits verbatim) must never crash
the display and must never be silently swallowed from the rendered text —
escaping only affects the markup SOURCE, the rendered (plain-text) output is
unchanged. These tests exercise the escape path through the REAL Rich
console (not a line-recording double) so a `MarkupError` would actually
surface if the fix regressed.
"""
from __future__ import annotations

import dataclasses
from io import StringIO

from rich.console import Console
from rich.text import Text

from zeno.vcli import cli
from zeno.vcli.cognitive.types import GoalTree
from zeno.vcli.turn_render import _escape_markup, render_verdict_card
from zeno.vcli.verdict import StepVerdict, VerdictReport

from tests.vcli.test_repl_native_cutover import (
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)


def test_trace_list_survives_bracketed_goal_text(monkeypatch) -> None:
    trace = _acted_trace(
        "确认 [/tmp/out.json] 已生成",
        strategy="walk",
        verify="at_position(1.0, 2.0)",
        verified_pose=True,
    )
    # Rebuild the goal_tree with the bracket-bearing goal (mirrors _acted_trace's
    # own construction — GoalTree is frozen, so replace() rather than mutate).
    trace = dataclasses.replace(
        trace, goal_tree=dataclasses.replace(trace.goal_tree, goal="确认 [/tmp/out.json] 已生成")
    )
    app_state = {"trace_history": [trace]}

    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False, width=120))

    cli._handle_slash_command("trace", ["list"], None, None, app_state)

    out = buf.getvalue()
    assert "out.json" in out


def test_repl_attempt_native_survives_bracketed_verify(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(1.0, 2.0) [/boom]", verified_pose=True,
    )
    engine = _EngineForTrace(trace)
    session = _FakeSession()
    real_console = Console(file=StringIO(), force_terminal=False)

    acted = cli._repl_attempt_native(engine, "走到 (1,2)", session, {}, real_console)

    assert acted is True
    plain = real_console.file.getvalue()
    assert "→ verify" in plain
    assert "actor=" in plain


class _EngineForTrace:
    def __init__(self, trace: object) -> None:
        self._vgg_agent = None
        self._trace = trace

    def run_turn_native(self, user_message, agent=None, session=None, app_state=None, on_progress=None, on_event=None):  # noqa: ANN001
        return self._trace


def test_render_verdict_card_survives_bracketed_verify() -> None:
    step = StepVerdict(
        name="native_step_0",
        strategy="walk",
        success=True,
        verify="at_position(1.0, 2.0) [/boom]",
        verify_result=True,
        evidence="RAN",
    )
    report = VerdictReport(
        verified=False,
        success=True,
        evidence="RAN",
        goal="g",
        n_steps=1,
        n_grounded=0,
        oracle_names=(),
        per_step=(step,),
    )
    console = Console(file=StringIO(), force_terminal=False)

    lines = render_verdict_card(report)
    for line in lines:
        console.print(line)

    plain = console.file.getvalue()
    assert "boom" in plain


def test_escape_markup_handles_backslash_before_bracket() -> None:
    escaped = _escape_markup(r"\[/x]")
    # Must not raise when fed back through Rich's markup parser.
    Text.from_markup(escaped)
