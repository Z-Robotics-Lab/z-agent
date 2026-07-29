# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Hermetic tests for the REPL display/interaction fixes (field 实测 bugs).

Covers, one test group per reported symptom:
  1. stderr 花屏  — _setup_logging routes to a file, strips terminal-bound
     handlers so a library WARNING never paints the prompt line.
  2. 裸 markdown  — the streamed-answer path strips ``**bold**`` / ``# heading``.
  4. 回复啰嗦     — build_system_prompt carries an always-on brevity constraint.
  5. /where 未知   — /where rewrites to the where-am-i skill; unknown slashes
     suggest the closest command + note that natural language works.
  7. 伪中断 banner — the operator-interrupt report no longer falsely asserts
     "导航目标已取消" for an idle-robot / hung-call interrupt.

All hermetic: no sim, no ROS, no network.
"""
from __future__ import annotations

import logging
import sys
from io import StringIO

from rich.console import Console

from zeno.vcli import cli


# ---------------------------------------------------------------------------
# 1. stderr 花屏 — logging routed to file, terminal handlers stripped
# ---------------------------------------------------------------------------


def _snapshot_root_logging():
    root = logging.getLogger()
    return list(root.handlers), root.level


def _restore_root_logging(saved) -> None:
    handlers, level = saved
    root = logging.getLogger()
    for h in list(root.handlers):
        if h not in handlers:
            root.removeHandler(h)
    for h in handlers:
        if h not in root.handlers:
            root.addHandler(h)
    root.setLevel(level)


def test_non_verbose_strips_terminal_handler_and_routes_to_file(monkeypatch, tmp_path):
    """A stderr StreamHandler (the basicConfig flood source) is removed on the
    non-verbose REPL, and a file handler receives the record instead — so a
    library WARNING can never corrupt the prompt_toolkit prompt line."""
    monkeypatch.setenv("HOME", str(tmp_path))
    saved = _snapshot_root_logging()
    root = logging.getLogger()
    # Simulate the production state: a terminal-bound stderr handler on root.
    stray = logging.StreamHandler(sys.stderr)
    root.addHandler(stray)
    try:
        cli._setup_logging(verbose=False)

        # No handler that writes to the real terminal survives.
        terminals = {sys.stderr, sys.stdout, sys.__stderr__, sys.__stdout__}
        for h in root.handlers:
            assert not (
                isinstance(h, logging.StreamHandler)
                and not isinstance(h, logging.FileHandler)
                and getattr(h, "stream", None) in terminals
            ), "a terminal-bound log handler leaked onto the non-verbose REPL"

        # A rotating file handler IS installed and captures a library WARNING.
        assert any(getattr(h, cli._ZENO_FILE_LOG_FLAG, False) for h in root.handlers)
        logging.getLogger("zeno.vcli.backends.openai_compat").warning(
            "Connection error (attempt 1/3), retrying in 1s"
        )
        for h in root.handlers:
            try:
                h.flush()
            except Exception:  # noqa: BLE001
                pass
        log_file = tmp_path / ".zeno" / "logs" / "zeno.log"
        assert log_file.is_file()
        assert "Connection error" in log_file.read_text(encoding="utf-8")
    finally:
        _restore_root_logging(saved)


def test_verbose_keeps_a_console_handler(monkeypatch, tmp_path):
    """--verbose: the dev explicitly asked for logs, so a stderr console handler
    is (re)added even though logging also goes to the file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    saved = _snapshot_root_logging()
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        cli._setup_logging(verbose=True)
        terminals = {sys.stderr, sys.__stderr__}
        assert any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
            and getattr(h, "stream", None) in terminals
            for h in root.handlers
        )
    finally:
        _restore_root_logging(saved)


# ---------------------------------------------------------------------------
# 2. 裸 markdown — streamed answer paragraphs are markdown-stripped
# ---------------------------------------------------------------------------


def test_streamed_answer_line_strips_bold_markdown():
    t = cli._render_streamed_answer_line("**能做什么（大概）** 我可以导航和取物")
    assert "**" not in t.plain
    assert "能做什么（大概）" in t.plain
    assert "我可以导航和取物" in t.plain


def test_streamed_answer_line_strips_heading_and_keeps_paths():
    t = cli._render_streamed_answer_line("# 标题 见 /etc/hosts 与 `code`")
    plain = t.plain
    assert not plain.lstrip().startswith("#")
    assert "标题" in plain
    assert "/etc/hosts" in plain  # path preserved (highlighted, not stripped)
    assert "code" in plain and "`" not in plain  # inline code unwrapped


# ---------------------------------------------------------------------------
# 4. 回复啰嗦 — brevity constraint is always in the system prompt
# ---------------------------------------------------------------------------


def test_system_prompt_carries_brevity_constraint():
    from zeno.vcli.prompt import build_system_prompt

    blocks = build_system_prompt()
    joined = "\n".join(b.get("text", "") for b in blocks)
    assert "1-3 sentences" in joined
    # Directness: don't ask "shall I do it now" — just act.
    assert "要我现在做吗" in joined or "shall I do it now" in joined
    # Don't restate the capability list.
    assert "capability list" in joined


# ---------------------------------------------------------------------------
# 5. /where 未知 — skill-alias slash + closest-match unknown fallback
# ---------------------------------------------------------------------------


def test_where_slash_rewrites_to_skill_phrase():
    assert cli._rewrite_skill_slash("/where") == "where am i"
    assert cli._rewrite_skill_slash("/where lab") == "where am i lab"
    assert cli._rewrite_skill_slash("/WHERE") == "where am i"


def test_non_skill_slashes_and_plain_text_are_not_rewritten():
    assert cli._rewrite_skill_slash("/help") is None
    assert cli._rewrite_skill_slash("hello there") is None
    assert cli._rewrite_skill_slash("/") is None
    assert cli._rewrite_skill_slash("") is None


def test_where_is_a_registered_slash_command():
    assert "where" in [name for name, _desc, _has_args in cli.SLASH_COMMANDS]


def test_unknown_slash_suggests_closest_and_mentions_natural_language(monkeypatch):
    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False, width=100))
    cont = cli._handle_slash_command("wher", [], None, None, {})
    out = buf.getvalue()
    assert cont is True
    assert "/where" in out          # closest-command suggestion
    assert "自然语言" in out         # natural language also works


def test_unknown_slash_with_no_close_match_still_hints_natural_language(monkeypatch):
    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False, width=100))
    cli._handle_slash_command("zzzqqq", [], None, None, {})
    assert "自然语言" in buf.getvalue()


# ---------------------------------------------------------------------------
# 7. 伪中断 banner — the interrupt report is honest, not a false nav-cancel
# ---------------------------------------------------------------------------


def test_operator_interrupt_message_does_not_falsely_claim_nav_cancel():
    from zeno.vcli.cognitive.abort import clear_abort
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    world = Go2WRealWorld()
    try:
        # agent=None -> no base to cancel; the hook still issues a stop + reports.
        msg = world.on_operator_interrupt(None)
    finally:
        clear_abort()  # the hook sets the global abort flag; don't leak it
    assert "导航目标已取消" not in msg  # the misleading specific claim is gone
    assert "已中断" in msg
    assert "stop" in msg  # still tells the operator how to hard-latch a stop
