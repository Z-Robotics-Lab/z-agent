# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Coding-agent style terminal composer for the bare ``zeno`` REPL.

The composer is display/input UI only.  These tests pin the independent framed
surface, multiline editing contract, history/completion reuse, interrupt/EOF
semantics, dynamic status footer, and safe compact transcript projection.
"""
from __future__ import annotations

from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML, fragment_list_to_text, to_formatted_text
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import Frame, SearchToolbar
import pytest

from zeno.vcli.composer import (
    COMPOSER_PROMPT_TEXT,
    ZenoComposer,
    render_submission,
)


class _NoopCompleter(Completer):
    def get_completions(self, document, complete_event):  # noqa: ANN001
        return
        yield  # pragma: no cover — keeps this a generator


class _HelpCompleter(Completer):
    def get_completions(self, document, complete_event):  # noqa: ANN001
        if document.text_before_cursor == "/he":
            yield Completion("/help", start_position=-3)


def _composer(*, input=None, history=None, toolbar=None) -> ZenoComposer:  # noqa: ANN001
    return ZenoComposer(
        history=history or InMemoryHistory(),
        completer=_NoopCompleter(),
        toolbar=toolbar,
        input=input,
        output=DummyOutput(),
    )


def test_composer_is_a_distinct_framed_surface() -> None:
    composer = _composer(toolbar=lambda: HTML("model:test | msgs:3"))

    assert isinstance(composer.frame, Frame)
    assert isinstance(composer.search_toolbar, SearchToolbar)
    assert fragment_list_to_text(to_formatted_text(composer.frame.title)) == "Zeno"
    assert COMPOSER_PROMPT_TEXT == "zeno> "  # acceptance harness compatibility
    footer = fragment_list_to_text(composer.footer_fragments())
    assert "Enter" in footer and "发送" in footer
    assert "Alt+Enter" in footer and "换行" in footer
    assert "Tab" in footer and "补全" in footer
    assert "model:test" in footer and "msgs:3" in footer


def test_alt_enter_inserts_newline_and_enter_submits() -> None:
    with create_pipe_input() as pipe:
        composer = _composer(input=pipe)
        pipe.send_text("first line\x1b\rsecond line\r")
        assert composer.prompt() == "first line\nsecond line"


@pytest.mark.parametrize("submit", ["\r", "\n"])
def test_cr_and_lf_enter_both_submit_for_pty_compatibility(submit: str) -> None:
    """Acceptance sendline() writes LF while physical Enter commonly writes CR."""
    with create_pipe_input() as pipe:
        composer = _composer(input=pipe)
        pipe.send_text("quit" + submit)
        assert composer.prompt() == "quit"


def test_submitted_text_is_appended_to_history() -> None:
    history = InMemoryHistory()
    with create_pipe_input() as pipe:
        composer = _composer(input=pipe, history=history)
        pipe.send_text("remember me\r")
        assert composer.prompt() == "remember me"
    assert history.get_strings() == ["remember me"]


def test_completer_is_reused_by_text_area() -> None:
    completer = _NoopCompleter()
    composer = ZenoComposer(
        history=InMemoryHistory(),
        completer=completer,
        output=DummyOutput(),
    )
    assert composer.text_area.completer is completer
    assert composer.text_area.complete_while_typing is True


def test_tab_applies_an_unambiguous_completion() -> None:
    with create_pipe_input() as pipe:
        composer = ZenoComposer(
            history=InMemoryHistory(),
            completer=_HelpCompleter(),
            input=pipe,
            output=DummyOutput(),
        )
        pipe.send_text("/he\t\r")
        assert composer.prompt() == "/help"


def test_ctrl_r_searches_existing_history() -> None:
    with create_pipe_input() as pipe:
        composer = ZenoComposer(
            history=InMemoryHistory(["alpha old command"]),
            completer=_NoopCompleter(),
            input=pipe,
            output=DummyOutput(),
        )
        pipe.send_text("\x12old\r\r")  # Ctrl+R, query, accept search, submit.
        assert composer.prompt() == "alpha old command"


def test_ctrl_c_raises_keyboard_interrupt_and_discards_draft() -> None:
    with create_pipe_input() as pipe:
        composer = _composer(input=pipe)
        pipe.send_text("discard this\x03")
        with pytest.raises(KeyboardInterrupt):
            composer.prompt()
        assert composer.text_area.text == ""


def test_ctrl_d_on_empty_composer_raises_eof() -> None:
    with create_pipe_input() as pipe:
        composer = _composer(input=pipe)
        pipe.send_text("\x04")
        with pytest.raises(EOFError):
            composer.prompt()


def test_toolbar_failure_is_display_only() -> None:
    def broken_toolbar():
        raise RuntimeError("sensor failed")

    composer = _composer(toolbar=broken_toolbar)
    footer = fragment_list_to_text(composer.footer_fragments())
    assert "Enter" in footer
    assert "sensor failed" not in footer


def test_submission_projection_is_compact_multiline_and_markup_safe() -> None:
    rendered = render_submission("move [bold red]now[/]\nthen verify")
    assert rendered.plain == "› move [bold red]now[/]\n  then verify"
