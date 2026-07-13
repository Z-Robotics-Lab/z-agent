# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Coding-agent style terminal composer for the bare ``zeno`` REPL.

The composer is display/input UI only.  These tests pin the independent framed
surface, multiline editing contract, history/completion reuse, interrupt/EOF
semantics, dynamic status footer, and safe compact transcript projection.
"""
from __future__ import annotations

from prompt_toolkit.completion import Completer
from prompt_toolkit.formatted_text import HTML, fragment_list_to_text, to_formatted_text
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import Frame
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
    assert fragment_list_to_text(to_formatted_text(composer.frame.title)) == "Zeno"
    assert COMPOSER_PROMPT_TEXT == "zeno> "  # acceptance harness compatibility
    footer = fragment_list_to_text(composer.footer_fragments())
    assert "Enter" in footer and "发送" in footer
    assert "Ctrl+J" in footer and "换行" in footer
    assert "Tab" in footer and "补全" in footer
    assert "model:test" in footer and "msgs:3" in footer


def test_ctrl_j_inserts_newline_and_enter_submits() -> None:
    with create_pipe_input() as pipe:
        composer = _composer(input=pipe)
        pipe.send_text("first line\nsecond line\r")
        assert composer.prompt() == "first line\nsecond line"


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

