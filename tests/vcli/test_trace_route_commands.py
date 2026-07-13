# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.5 — /trace turn replay + /route routing transparency.

Forensic finding (docs/CLI_UX_REDESIGN.md): NOTHING in the product calls
trace_store.save_trace — traces were never persisted, so a disk-reading
/trace would honestly show nothing forever. Design: the REPL keeps a BOUNDED
in-session history (app_state["trace_history"], last 5 turns, native + VGG),
/trace renders full detail from memory, and /trace save writes the latest via
the EXISTING save_trace on explicit request only.

render_trace_detail is display-only: it shows what the trace STORES
(verify_result PASS/FAIL, actor annotation, honest durations, diagnosis,
validation notes) and NEVER re-derives evidence/verified (that needs the live
oracle namespace — the verdict line/card own that at turn time).
"""
from __future__ import annotations

from io import StringIO

from rich.console import Console

from zeno.vcli import cli
from zeno.vcli.cognitive.actor_causation import ActorCaused
from zeno.vcli.cognitive.types import ExecutionTrace, GoalTree, StepRecord, SubGoal
from zeno.vcli.turn_render import render_trace_detail

from tests.vcli.test_repl_native_cutover import (
    _FakeConsole,
    _FakeEngine,
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)


def _capture_console(monkeypatch) -> StringIO:
    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False, width=140))
    return buf


def _trace(goal: str = "往左转动30度", verify: str = "turned(18)") -> ExecutionTrace:
    sub = SubGoal(name="native_step_0", description="d", verify=verify, strategy="turn")
    step = StepRecord(
        sub_goal_name="native_step_0",
        strategy="turn",
        success=True,
        verify_result=True,
        duration_sec=3.4,
        actor_caused=ActorCaused.NOT_GRADED,
        result_data={"diagnosis": "", "verify_value": 29.8},
    )
    return ExecutionTrace(
        goal_tree=GoalTree(goal=goal, sub_goals=(sub,)),
        steps=(step,),
        success=True,
        total_duration_sec=14.2,
    )


# ---------------------------------------------------------------------------
# render_trace_detail — pure projection of the stored trace
# ---------------------------------------------------------------------------


def test_trace_detail_shows_stored_facts() -> None:
    text = "\n".join(render_trace_detail(_trace()))
    assert "往左转动30度" in text
    assert "turned(18)" in text
    assert "turn" in text
    assert "PASS" in text
    assert "3.4s" in text and "14.2s" in text
    assert "NOT_GRADED" in text


def test_trace_detail_never_rederives_verdict() -> None:
    # No live oracle namespace here — the detail must not claim GROUNDED or
    # verified; those belong to turn-time classification.
    text = "\n".join(render_trace_detail(_trace()))
    assert "GROUNDED" not in text
    assert "verified=" not in text


def test_trace_detail_honest_duration_and_failure_class() -> None:
    sub = SubGoal(name="s", description="d", verify="moved(2.0)", strategy="walk")
    step = StepRecord(
        sub_goal_name="s", strategy="walk", success=False, verify_result=False,
        duration_sec=0.0, error="nav timeout", failure_class="timeout",
    )
    trace = ExecutionTrace(
        goal_tree=GoalTree(goal="g", sub_goals=(sub,)), steps=(step,),
        success=False, total_duration_sec=0.0,
    )
    text = "\n".join(render_trace_detail(trace))
    assert "FAIL" in text
    assert "timeout" in text
    assert "0.0s" not in text  # unmeasured legacy zero renders as dash


# ---------------------------------------------------------------------------
# /trace — bounded in-session history
# ---------------------------------------------------------------------------


def test_trace_registered_in_slash_commands() -> None:
    names = [c[0] for c in cli.SLASH_COMMANDS]
    assert "trace" in names and "route" in names


def test_trace_empty_history_is_honest(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    cont = cli._handle_slash_command("trace", [], None, None, {})
    assert cont is True
    assert "无" in buf.getvalue()


def test_native_turn_appends_bounded_history(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    app_state: dict = {}
    for i in range(7):
        trace = _acted_trace(f"g{i}", strategy="walk", verify="at_position(1.0, 2.0)", verified_pose=True)
        engine = _FakeEngine(trace)
        assert cli._repl_attempt_native(engine, f"目标{i}", _FakeSession(), app_state, _FakeConsole())
    history = app_state.get("trace_history")
    assert history is not None and len(history) == 5  # bounded
    assert history[-1].goal_tree.goal == "g6"  # latest last


def test_trace_renders_latest_and_indexed(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    app_state: dict = {"trace_history": [_trace("第一个目标"), _trace("第二个目标")]}
    cli._handle_slash_command("trace", [], None, None, app_state)
    assert "第二个目标" in buf.getvalue()  # latest by default
    buf2 = _capture_console(monkeypatch)
    cli._handle_slash_command("trace", ["2"], None, None, app_state)
    assert "第一个目标" in buf2.getvalue()


def test_trace_list_shows_summaries(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    app_state: dict = {"trace_history": [_trace("第一个目标"), _trace("第二个目标")]}
    cli._handle_slash_command("trace", ["list"], None, None, app_state)
    out = buf.getvalue()
    assert "第一个目标" in out and "第二个目标" in out


def test_trace_save_writes_via_existing_store(monkeypatch, tmp_path) -> None:
    buf = _capture_console(monkeypatch)
    saved: list[object] = []

    def _fake_save(trace):  # noqa: ANN001
        saved.append(trace)
        return tmp_path / "trace-x.json"

    monkeypatch.setattr("zeno.vcli.cognitive.trace_store.save_trace", _fake_save)
    app_state: dict = {"trace_history": [_trace()]}
    cli._handle_slash_command("trace", ["save"], None, None, app_state)
    assert len(saved) == 1
    assert "trace-x.json" in buf.getvalue()


# ---------------------------------------------------------------------------
# /route — routing transparency
# ---------------------------------------------------------------------------


class _RouteEngine:
    def classify_intent(self, text: str):  # noqa: ANN001
        from types import SimpleNamespace

        return SimpleNamespace(route="vgg", reason="vgg-actionable", complex=True, use_vgg=True)


def test_route_explains_decision(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    app_state: dict = {"engine": _RouteEngine()}
    cont = cli._handle_slash_command("route", ["往左转动30度"], None, None, app_state)
    assert cont is True
    out = buf.getvalue()
    assert "vgg-actionable" in out
    assert "native" in out  # says what the REPL will attempt first


def test_route_without_engine_is_honest(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    cli._handle_slash_command("route", ["x"], None, None, {})
    assert "engine" in buf.getvalue().lower() or "未" in buf.getvalue()


def test_route_without_args_shows_usage(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    cli._handle_slash_command("route", [], None, None, {"engine": _RouteEngine()})
    assert "/route" in buf.getvalue()
