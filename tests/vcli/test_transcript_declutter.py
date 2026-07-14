# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P3.9 transcript declutter (owner field feedback 2026-07-13 深夜).

Real-machine transcript showed: the same fact rendered three times (streamed
tree + pinned step line + card row), a 4-line interject burst, fabricated
"0.0s" on fast tool_use tools, and raw markdown tables in ● answers.
"""
from __future__ import annotations

from zeno.vcli import cli
from zeno.vcli.turn_render import render_verdict_card
from zeno.vcli.turn_runner import ComposerInterjectQueue, TurnRunner

from tests.unit.vcli.test_turn_render import _grounded_step, _ran_step, _report, _trace_for
from tests.vcli.test_chain_view_repl import _EventFakeEngine
from tests.vcli.test_repl_native_cutover import (
    _FakeConsole,
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)
from zeno.vcli.cognitive.actor_causation import ActorCaused


def test_card_rows_suppressible_keeping_explanations() -> None:
    per_step = (_grounded_step(), _ran_step())
    report = _report(per_step, verified=False)
    trace = _trace_for(per_step, [1.0, 1.0], [ActorCaused.NOT_GRADED, ActorCaused.UNCAUSED])
    lines = render_verdict_card(report, trace, include_rows=False)
    text = "\n".join(lines)
    assert "ⓘ" in text  # explanations survive
    assert not [l for l in lines if "moved(2.0)" in l and "ⓘ" not in l]  # rows gone


def test_streamed_native_turn_prints_no_duplicate_card_rows(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace("g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True)
    runner = TurnRunner(run_turn=lambda _t: None, interject_queue=ComposerInterjectQueue(), echo=lambda _s: None)
    console = _FakeConsole()
    assert cli._repl_attempt_native(
        _EventFakeEngine(trace), "走到坐标", _FakeSession(), {"turn_runner": runner}, console
    )
    # the verify expr appears in the streamed tree + the pinned ▸ line — but
    # NOT a third time as a card row.
    hits = [l for l in console.lines if "at_position(11.0, 3.0)" in l]
    assert len(hits) <= 2, hits


def test_interject_summary_line_suppressed_under_runner(monkeypatch) -> None:
    # sync mode keeps the pinned '插队' summary; runner mode drops it (the
    # queue echo + kernel ⟲ line already tell the story).
    _stub_oracle(monkeypatch)
    trace = _acted_trace("g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True)

    class _Q(ComposerInterjectQueue):
        def has_pending(self) -> bool:
            return True  # simulate a queued line at turn end

    runner = TurnRunner(run_turn=lambda _t: None, interject_queue=_Q(), echo=lambda _s: None)
    console = _FakeConsole()
    app_state = {"turn_runner": runner, "interject": _Q()}
    cli._repl_attempt_native(_EventFakeEngine(trace), "走", _FakeSession(), app_state, console)
    assert "已取消当前动作,剩余步骤不再执行" not in console.text


def test_tool_activity_duration_is_honest_for_fast_tools() -> None:
    fast = cli.render_tool_activity("x", is_error=False, elapsed=0.03)
    assert "0.0s" not in fast.plain
    assert "<0.1s" in fast.plain
    zero = cli.render_tool_activity("x", is_error=False, elapsed=0.0)
    assert "0.0s" not in zero.plain


def test_answer_markdown_table_renders_not_raw_pipes() -> None:
    from io import StringIO
    from rich.console import Console

    text = (
        "全部完成：\n\n| # | 任务 | 结果 |\n|---|---|---|\n"
        "| 1 | 前进 2 米 | ✅ |\n| 2 | 左转 | ✅ |\n\n还需要什么？"
    )
    buf = StringIO()
    Console(file=buf, force_terminal=False, width=60).print(
        cli.render_response(text, width=60)
    )
    out = buf.getvalue()
    assert "| 1 |" not in out  # raw pipe row must not appear
    assert "前进 2 米" in out and "任务" in out  # content survives as a real table
