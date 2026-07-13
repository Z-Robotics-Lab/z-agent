# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Framed multiline input composer for the interactive Zeno REPL.

This module owns input *presentation and editing only*.  It never sees an
engine, world, tool, route, trace, or verdict.  ``ZenoComposer`` replaces the
bare one-line ``PromptSession`` surface with a coding-agent style frame while
preserving the stable ``zeno>`` acceptance marker, history, completion,
KeyboardInterrupt, and EOF contracts.

Interaction contract:
- Enter submits the complete draft (both CR and LF terminal encodings).
- Alt+Enter inserts a newline.
- Tab / Shift+Tab cycle completions.
- Ctrl+C discards the draft and raises ``KeyboardInterrupt``.
- Ctrl+D on an empty draft raises ``EOFError``.

The application uses ``erase_when_done=True`` so editing chrome does not fill
scrollback.  ``render_submission`` projects the accepted draft into a compact
plain ``›`` transcript line; model/user text is appended as literal Rich text,
never parsed as markup.
"""
from __future__ import annotations

from typing import Any, Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.completion import CompleteEvent, Completer
from prompt_toolkit.formatted_text import (
    AnyFormattedText,
    FormattedText,
    to_formatted_text,
)
from prompt_toolkit.filters import has_focus
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Dimension, Float, FloatContainer, HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.styles import BaseStyle
from prompt_toolkit.widgets import Frame, SearchToolbar, TextArea
from rich.text import Text


COMPOSER_TITLE: AnyFormattedText = FormattedText(
    [("class:composer.title", "Zeno")]
)
COMPOSER_PROMPT_TEXT = "zeno> "
COMPOSER_PROMPT: AnyFormattedText = FormattedText(
    [("", " "), ("class:composer.prompt", COMPOSER_PROMPT_TEXT)]
)


class ZenoComposer:
    """Reusable non-full-screen prompt_toolkit composer.

    ``input``/``output`` are injectable prompt_toolkit endpoints so every key
    contract can be tested without a real TTY.  ``toolbar`` is a dynamic,
    display-only formatted-text callback (model/world/live-status in cli.py).
    A broken callback is swallowed and only the static key help remains.
    """

    def __init__(
        self,
        *,
        history: History,
        completer: Completer,
        toolbar: Callable[[], AnyFormattedText] | None = None,
        style: BaseStyle | None = None,
        input: Any = None,
        output: Any = None,
    ) -> None:
        self._toolbar = toolbar

        def _accept(buffer: Any) -> bool:
            get_app().exit(result=buffer.text)
            return False

        self.search_toolbar = SearchToolbar()
        self.text_area = TextArea(
            multiline=True,
            prompt=COMPOSER_PROMPT,
            history=history,
            completer=completer,
            complete_while_typing=True,
            accept_handler=_accept,
            search_field=self.search_toolbar,
            wrap_lines=True,
            focus_on_click=True,
            height=Dimension(min=1, max=6),
            dont_extend_height=True,
            style="class:composer.input",
            name="zeno-composer",
        )

        footer = Window(
            content=FormattedTextControl(self.footer_fragments, show_cursor=False),
            height=1,
            dont_extend_height=True,
            style="class:composer.footer",
        )
        separator = Window(
            height=1,
            char="─",
            dont_extend_height=True,
            style="class:composer.separator",
        )
        self.frame = Frame(
            HSplit([self.text_area, self.search_toolbar, separator, footer]),
            title=COMPOSER_TITLE,
            style="class:composer.frame",
        )
        root = FloatContainer(
            content=self.frame,
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(
                        max_height=12,
                        scroll_offset=1,
                        display_arrows=True,
                    ),
                )
            ],
        )

        bindings = self._build_key_bindings()
        kwargs: dict[str, Any] = {}
        if input is not None:
            kwargs["input"] = input
        if output is not None:
            kwargs["output"] = output
        self.application: Application[str] = Application(
            layout=Layout(root, focused_element=self.text_area),
            key_bindings=bindings,
            style=style,
            full_screen=False,
            erase_when_done=True,
            refresh_interval=0.5,
            mouse_support=False,
            **kwargs,
        )

    def footer_fragments(self) -> list[tuple[str, str]]:
        """Static editing help plus the best-effort dynamic status surface."""
        fragments: list[tuple[str, str]] = [
            ("class:composer.footer.key", " Enter "),
            ("class:composer.footer.hint", "发送 · "),
            ("class:composer.footer.key", "Alt+Enter"),
            ("class:composer.footer.hint", " 换行 · "),
            ("class:composer.footer.key", "Tab"),
            ("class:composer.footer.hint", " 补全"),
        ]
        if self._toolbar is None:
            return fragments
        try:
            dynamic = self._toolbar()
            dynamic_fragments = list(to_formatted_text(dynamic)) if dynamic else []
        except Exception:  # noqa: BLE001 — status is display-only, never fatal
            dynamic_fragments = []
        if dynamic_fragments:
            fragments.append(("class:composer.footer.divider", "  │  "))
            # prompt_toolkit also accepts 3-tuples carrying mouse handlers.  The
            # REPL toolbar currently emits 2-tuples; normalize defensively so
            # this method keeps a simple, stable return contract for rendering.
            for item in dynamic_fragments:
                fragments.append((item[0], item[1]))
        return fragments

    def _build_key_bindings(self) -> KeyBindings:
        bindings = KeyBindings()
        composer_focused = has_focus(self.text_area.buffer)

        @bindings.add("c-m", filter=composer_focused)
        @bindings.add("c-j", filter=composer_focused)
        def _submit(event: Any) -> None:
            event.current_buffer.validate_and_handle()

        @bindings.add("escape", "c-m", filter=composer_focused)
        @bindings.add("escape", "c-j", filter=composer_focused)
        def _newline(event: Any) -> None:
            event.current_buffer.insert_text("\n")

        @bindings.add("tab", filter=composer_focused)
        def _next_completion(event: Any) -> None:
            buffer = event.current_buffer
            state = buffer.complete_state
            if state is not None and state.current_completion is not None:
                buffer.apply_completion(state.current_completion)
            elif state is not None:
                buffer.complete_next()
            else:
                # Apply an unambiguous completion in one Tab, matching the old
                # PromptSession UX.  Ambiguous sets open the normal menu; the
                # next Tab applies its selected entry.
                try:
                    completions = list(
                        self.text_area.completer.get_completions(
                            buffer.document,
                            CompleteEvent(completion_requested=True),
                        )
                    )
                except Exception:  # noqa: BLE001 — broken completion is non-fatal
                    completions = []
                if len(completions) == 1:
                    buffer.apply_completion(completions[0])
                else:
                    buffer.start_completion(select_first=True)

        @bindings.add("s-tab", filter=composer_focused)
        def _previous_completion(event: Any) -> None:
            buffer = event.current_buffer
            if buffer.complete_state is None:
                buffer.start_completion(select_first=True)
            else:
                buffer.complete_previous()

        @bindings.add("c-c", filter=composer_focused)
        def _interrupt(event: Any) -> None:
            event.app.exit(exception=KeyboardInterrupt())

        @bindings.add("c-d", filter=composer_focused)
        def _eof_or_delete(event: Any) -> None:
            buffer = event.current_buffer
            if not buffer.text:
                event.app.exit(exception=EOFError())
            elif buffer.cursor_position < len(buffer.text):
                buffer.delete(1)

        return bindings

    def prompt(self) -> str:
        """Run one composer edit cycle and return the submitted draft."""
        try:
            result = self.application.run()
            return str(result or "")
        finally:
            # Ctrl+C/EOF bypass Buffer.validate_and_handle(), so clear their
            # abandoned drafts explicitly before the next composer cycle.
            self.text_area.buffer.reset()


def render_submission(text: str) -> Text:
    """Compact literal Rich projection of one accepted (possibly multiline) draft."""
    rendered = Text()
    lines = str(text).split("\n")
    for index, line in enumerate(lines):
        if index:
            rendered.append("\n")
        rendered.append("› " if index == 0 else "  ", style="bold #00b4b4")
        rendered.append(line)
    return rendered
