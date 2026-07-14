# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.2 CoT display — /cot mode command, /why replay, native reasoning capture.

docs/CLI_UX_REDESIGN.md §4 P1.2: DeepSeek's reasoning stream already reaches
the display layer and was discarded. Contract pinned here:

- /cot off|tail|full sets the DISPLAY-ONLY mode (app_state["cot_mode"]),
  persisted via the same config mechanism as /permissions; bad args refuse
  and keep the mode; bare /cot reports the current mode.
- _apply_saved_cot_mode loads the persisted mode at startup (bogus -> default).
- The native turn records the FULL reasoning buffer to app_state
  ["last_reasoning"] (display buffer — never the session); /why prints it,
  with an honest fallback when a turn carried no reasoning.
- cot_mode=full prints the complete reasoning block after the turn; tail
  (default) keeps a bounded two-line preview with /why as the honest expansion
  path; off suppresses the ┆ tail entirely.
"""
from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.cells import cell_len

from zeno.vcli import cli
from zeno.vcli.turn_events import NativeEvent

from tests.vcli.test_repl_native_cutover import (
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)
from tests.vcli.test_chain_view_repl import _EventFakeEngine


def _capture_console(monkeypatch) -> StringIO:
    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False, width=120))
    return buf


# ---------------------------------------------------------------------------
# /cot — mode set + persistence (the /permissions pattern)
# ---------------------------------------------------------------------------


def test_cot_registered_in_slash_commands() -> None:
    names = [c[0] for c in cli.SLASH_COMMANDS]
    assert "cot" in names and "why" in names


def test_cot_bare_reports_current_mode(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    app_state: dict = {"cot_mode": "off"}
    cont = cli._handle_slash_command("cot", [], None, None, app_state)
    assert cont is True
    assert "off" in buf.getvalue()


def test_cot_sets_and_persists_mode(monkeypatch) -> None:
    _capture_console(monkeypatch)
    saved: list[str] = []
    monkeypatch.setattr(cli, "_save_cot_mode", saved.append)
    app_state: dict = {}
    cli._handle_slash_command("cot", ["full"], None, None, app_state)
    assert app_state["cot_mode"] == "full"
    assert saved == ["full"]
    cli._handle_slash_command("cot", ["off"], None, None, app_state)
    assert app_state["cot_mode"] == "off"
    assert saved == ["full", "off"]


def test_cot_bad_arg_refuses_and_keeps_mode(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    app_state: dict = {"cot_mode": "tail"}
    cli._handle_slash_command("cot", ["loud"], None, None, app_state)
    assert app_state["cot_mode"] == "tail"
    assert "off" in buf.getvalue() and "full" in buf.getvalue()  # usage shown


def test_apply_saved_cot_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        "zeno.vcli.config.load_config", lambda: {"cot_mode": "off"}
    )
    app_state: dict = {}
    cli._apply_saved_cot_mode(app_state)
    assert app_state["cot_mode"] == "off"


def test_apply_saved_cot_mode_bogus_keeps_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "zeno.vcli.config.load_config", lambda: {"cot_mode": "shout"}
    )
    app_state: dict = {}
    cli._apply_saved_cot_mode(app_state)
    assert cli._cot_mode(app_state) == "tail"


# ---------------------------------------------------------------------------
# native turn -> last_reasoning capture -> /why
# ---------------------------------------------------------------------------


class _ReasoningFakeEngine(_EventFakeEngine):
    def run_turn_native(self, user_message, agent=None, session=None,
                        app_state=None, on_progress=None, on_event=None):  # noqa: ANN001
        self.received_on_event = on_event
        if on_event is not None:
            on_event(NativeEvent(kind="reasoning", detail="用户要左转30度。"))
            on_event(NativeEvent(kind="reasoning", detail="turn 技能即可,verify turned(18)。"))
            on_event(NativeEvent(kind="tool_start", label="turn"))
            on_event(NativeEvent(kind="verify", label="turned(18)", ok=True))
        return self._trace


def _run_reasoning_turn(monkeypatch, app_state: dict) -> tuple[object, object]:
    _stub_oracle(monkeypatch)
    trace = _acted_trace("g", strategy="turn", verify="turned(18)", verified_pose=True)
    engine = _ReasoningFakeEngine(trace)
    console_double = _FakeConsoleProxy()
    session = _FakeSession()
    acted = cli._repl_attempt_native(engine, "往左转动30度", session, app_state, console_double)
    assert acted is True
    return console_double, session


class _FakeConsoleProxy:
    """Line-recording console double (the cutover pattern)."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def print(self, *a: object, **k: object) -> None:
        buf = StringIO()
        Console(file=buf, force_terminal=False, width=120).print(*a, **k)
        self.lines.append(buf.getvalue().rstrip())

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def test_native_turn_records_last_reasoning(monkeypatch) -> None:
    app_state: dict = {}
    _run_reasoning_turn(monkeypatch, app_state)
    assert "左转30度" in app_state.get("last_reasoning", "")


def test_cot_full_prints_reasoning_after_turn(monkeypatch) -> None:
    app_state: dict = {"cot_mode": "full"}
    console, _session = _run_reasoning_turn(monkeypatch, app_state)
    assert "左转30度" in console.text


def test_cot_tail_keeps_a_bounded_preview_with_why_expansion(monkeypatch) -> None:
    app_state: dict = {"cot_mode": "tail"}
    console, _session = _run_reasoning_turn(monkeypatch, app_state)
    assert "左转30度" in console.text
    assert "/why" in console.text
    assert "Thinking · preview" in console.text


def test_cot_off_suppresses_live_tail(monkeypatch) -> None:
    app_state: dict = {"cot_mode": "off"}
    _run_reasoning_turn(monkeypatch, app_state)
    view = app_state["last_chain_view"]
    assert "┆" not in "\n".join(view.render_lines())


def test_reasoning_never_reaches_session(monkeypatch) -> None:
    # The full reasoning buffer is a DISPLAY-only artifact (P1.2 docstring) —
    # it must never leak into the persistent session transcript that follow-up
    # turns read back as context.
    app_state: dict = {"cot_mode": "full"}
    _console, session = _run_reasoning_turn(monkeypatch, app_state)
    assert "左转30度" not in "".join(session.asst)
    assert "左转30度" not in "".join(session.user)


def test_why_prints_last_reasoning(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    app_state: dict = {"last_reasoning": "先转 30 度,verify turned(18)。"}
    cont = cli._handle_slash_command("why", [], None, None, app_state)
    assert cont is True
    assert "turned(18)" in buf.getvalue()
    assert "Thinking · last turn" in buf.getvalue()
    assert "┆" in buf.getvalue()


def test_why_honest_fallback_when_empty(monkeypatch) -> None:
    buf = _capture_console(monkeypatch)
    cont = cli._handle_slash_command("why", [], None, None, {})
    assert cont is True
    assert "无推理" in buf.getvalue()


def test_reasoning_block_is_open_normalized_and_responsive() -> None:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=38)
    console.print(
        cli.render_reasoning(
            "first sentence.\n\n  second   sentence.",
            width=38,
            title="Thinking · full",
        )
    )
    lines = [line.rstrip() for line in buf.getvalue().splitlines() if line.strip()]

    assert any("◌ Thinking · full" in line for line in lines)
    assert any("┆ first sentence. second" in line for line in lines)
    assert all(glyph not in buf.getvalue() for glyph in ("╭", "╮", "╯", "╰"))
    assert all(cell_len(line) <= 38 for line in lines)


def test_live_thinking_is_open_and_bounded_to_two_rows() -> None:
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=40)
    console.print(
        cli.render_live_thinking(
            elapsed=3.2,
            reasoning_tail="A long raw thought " * 20,
            width=40,
        )
    )
    lines = [line.rstrip() for line in buf.getvalue().splitlines() if line.strip()]

    assert len(lines) == 2
    assert "◌ Thinking · 3s" in lines[0]
    assert "┆" in lines[1]
    assert all(glyph not in buf.getvalue() for glyph in ("╭", "╮", "╯", "╰"))


def test_reasoning_preview_is_bounded_and_uses_visual_depth() -> None:
    preview = cli.render_reasoning_preview(
        "first thought " * 40,
        width=40,
        max_lines=2,
    )
    buf = StringIO()
    Console(file=buf, force_terminal=False, width=40).print(preview)
    lines = [line.rstrip() for line in buf.getvalue().splitlines() if line.strip()]

    assert len(lines) == 3  # header + exactly two bounded preview rows
    assert "Thinking · preview" in lines[0]
    assert "/why" in lines[0]
    assert lines[-1].endswith("…")
    assert all(cell_len(line) <= 40 for line in lines)


def test_tool_activity_is_a_quiet_separate_visual_layer() -> None:
    rendered = cli.render_tool_activity(
        "[dim]go2w_real_bringup[/](action=status)",
        is_error=False,
        elapsed=49.8,
    )

    assert rendered.plain == "  ◇ Tool · go2w_real_bringup(action=status)  ✓ 49.8s"
    styles = {str(span.style) for span in rendered.spans}
    assert "dim #738091" in styles
    assert "bold green" in styles
