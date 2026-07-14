# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Coding-agent style terminal composer for the bare ``zeno`` REPL.

The composer is display/input UI only.  These tests pin the independent framed
surface, multiline editing contract, history/completion reuse, interrupt/EOF
semantics, dynamic status footer, and safe compact transcript projection.
"""
from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import HTML, fragment_list_to_text, to_formatted_text
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit, Window
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import SearchToolbar
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


class _ResizableOutput(DummyOutput):
    def __init__(self, columns: int, rows: int = 24) -> None:
        self.columns = columns
        self.rows = rows

    def get_size(self) -> Size:
        return Size(rows=self.rows, columns=self.columns)


def _composer(*, input=None, history=None, toolbar=None) -> ZenoComposer:  # noqa: ANN001
    return ZenoComposer(
        history=history or InMemoryHistory(),
        completer=_NoopCompleter(),
        toolbar=toolbar,
        input=input,
        output=DummyOutput(),
    )


def test_composer_is_a_compact_claude_style_input_rail() -> None:
    composer = _composer(toolbar=lambda: HTML("model:test | msgs:3"))

    assert isinstance(composer.container, HSplit)
    assert isinstance(composer.rail, Window)
    assert not hasattr(composer, "frame")
    assert isinstance(composer.search_toolbar, SearchToolbar)
    assert COMPOSER_PROMPT_TEXT == "zeno> "  # acceptance harness compatibility
    footer = fragment_list_to_text(composer.footer_fragments(width=100))
    assert "? 快捷键" not in footer
    assert footer.strip().startswith("model:test")
    assert "Enter 发送" not in footer
    assert "Alt+Enter 换行" not in footer
    assert "Tab 补全" not in footer
    assert "model:test" in footer and "msgs:3" in footer


def test_input_newlines_and_soft_wraps_align_below_prompt_body() -> None:
    composer = _composer()
    prefix = composer.text_area.window.get_line_prefix
    assert prefix is not None

    plain = lambda value: fragment_list_to_text(to_formatted_text(value))
    prompt_width = get_cwidth(" " + COMPOSER_PROMPT_TEXT)
    assert plain(prefix(0, 0)) == ""
    assert plain(prefix(0, 1)) == " " * prompt_width
    assert plain(prefix(1, 0)) == " " * prompt_width


def test_footer_reflows_whole_status_fields_with_indented_continuations() -> None:
    composer = _composer(
        toolbar=lambda: HTML(
            "(no odometry - stack down?) | base:go2w_hw | "
            "model:deepseek-v4-pro | tools:44 | msgs:2"
        )
    )

    wide = fragment_list_to_text(composer.footer_fragments(width=120))
    assert "\n" not in wide
    assert all(label in wide for label in ("no odometry", "base:go2w_hw", "msgs:2"))

    narrow = fragment_list_to_text(composer.footer_fragments(width=40)).splitlines()
    assert 2 <= len(narrow) <= 3
    assert all(line.startswith("  ") for line in narrow)
    assert all(get_cwidth(line) <= 40 for line in narrow)
    assert "no odometry" in "\n".join(narrow)
    assert "base:go2w_hw" in "\n".join(narrow)
    # Reflow happens at status-field boundaries, never halfway through a label.
    assert "model:\ndeepseek" not in "\n".join(narrow)


def test_resize_eraser_tracks_reflowed_cursor_distance_for_long_drafts() -> None:
    output = _ResizableOutput(columns=60)
    composer = ZenoComposer(
        history=InMemoryHistory(),
        completer=_NoopCompleter(),
        output=output,
    )
    composer.text_area.text = (
        "这是一条用于检查终端缩放后自动换行和正文缩进是否稳定的很长输入消息 "
        "with a long english continuation"
    )
    composer.text_area.buffer.cursor_position = len(composer.text_area.text)
    # The production call runs inside Application.run(), where history has an
    # event-loop task. This pure layout probe deliberately avoids starting one.
    composer.text_area.buffer._load_history_task = object()  # type: ignore[assignment]  # noqa: SLF001

    wide = composer.application.reflowed_cursor_position()
    output.columns = 40
    narrow = composer.application.reflowed_cursor_position()

    assert narrow.y > wide.y
    assert type(composer.application)._on_resize is not Application._on_resize


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
    footer = fragment_list_to_text(composer.footer_fragments(width=80))
    assert footer == ""
    assert "sensor failed" not in footer


def test_submission_projection_is_compact_multiline_and_markup_safe() -> None:
    rendered = render_submission("move [bold red]now[/]\nthen verify")
    assert rendered.plain == "› move [bold red]now[/]\n  then verify"


# ---------------------------------------------------------------------------
# P3.8 — footer typography: per-part style classes (owner ask 2026-07-13)
# ---------------------------------------------------------------------------


def _footer_styles(composer, width=120):
    return [
        (style, text)
        for style, text in composer.footer_fragments(width=width)
        if text.strip() and text != "\n"
    ]


def _mk(toolbar):
    from prompt_toolkit.history import InMemoryHistory
    from zeno.vcli.composer import ZenoComposer
    from zeno.vcli.cli import ZenoCompleter

    return ZenoComposer(
        history=InMemoryHistory(), completer=ZenoCompleter(), toolbar=toolbar
    )


def test_footer_parts_carry_distinct_style_classes() -> None:
    from prompt_toolkit.formatted_text import HTML

    composer = _mk(lambda: HTML(
        "⚙ navigate 执行中… | ⌖ pose x=1.96 y=-1.90 yaw=-6.5deg · odom age 0.1s | "
        "base:go2w_hw | model:deepseek-v4-pro | tools:44 | msgs:12"
    ))
    styles = _footer_styles(composer)
    style_of = {text.strip(): style for style, text in styles}
    act = next(v for k, v in style_of.items() if k.startswith("⚙"))
    pose = next(v for k, v in style_of.items() if "pose" in k)
    meta = next(v for k, v in style_of.items() if k.startswith("base:"))
    assert "activity" in act
    assert "pose" in pose
    assert "meta" in meta
    assert act != pose != meta  # 分区配色,不再一坨 plain


def test_footer_stale_odom_gets_warning_style() -> None:
    from prompt_toolkit.formatted_text import HTML

    composer = _mk(lambda: HTML("⌖ pose x=0.00 y=0.00 yaw=0.0deg · odom age 7.4s"))
    styles = _footer_styles(composer)
    odom_style = next(s for s, t in styles if "odom" in t)
    assert "stale" in odom_style and "pose" in odom_style  # 过期一眼可见,仍属位姿族


def test_footer_fresh_odom_not_stale_styled() -> None:
    from prompt_toolkit.formatted_text import HTML

    composer = _mk(lambda: HTML("⌖ pose x=0.00 y=0.00 yaw=0.0deg · odom age 0.2s"))
    styles = _footer_styles(composer)
    odom_style = next(s for s, t in styles if "odom" in t)
    assert "stale" not in odom_style


def test_footer_plain_text_content_unchanged_by_styling() -> None:
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.formatted_text import fragment_list_to_text

    composer = _mk(lambda: HTML("base:go2w_hw | model:m | tools:4 | msgs:2"))
    text = fragment_list_to_text(composer.footer_fragments(width=100))
    assert "base:go2w_hw" in text and "model:m" in text
    assert "·" in text  # separators preserved


def test_placeholder_visible_only_when_empty() -> None:
    composer = _mk(lambda: None)
    assert composer.placeholder_visible() is True
    composer.text_area.text = "去厨房"
    assert composer.placeholder_visible() is False
    composer.text_area.text = ""
    assert composer.placeholder_visible() is True


def test_rails_span_full_width_and_close_the_block() -> None:
    composer = _mk(lambda: None)
    names = [w for w in ("rail", "subrail") if hasattr(composer, w)]
    assert names == ["rail", "subrail"]
