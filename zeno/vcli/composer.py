# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Compact multiline input composer for the interactive Zeno REPL.

This module owns input *presentation and editing only*.  It never sees an
engine, world, tool, route, trace, or verdict.  ``ZenoComposer`` replaces the
bare one-line ``PromptSession`` surface with a coding-agent style input rail while
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

import re

from typing import Any, Callable

from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app, get_app_or_none, set_app
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
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition
from prompt_toolkit.styles import BaseStyle
from prompt_toolkit.utils import get_cwidth
from prompt_toolkit.widgets import SearchToolbar, TextArea
from rich.text import Text


COMPOSER_PROMPT_TEXT = "zeno> "
COMPOSER_PROMPT: AnyFormattedText = FormattedText(
    [
        ("", " "),
        ("class:composer.prompt.brand", "zeno"),
        ("class:composer.prompt.chevron", "> "),
    ]
)
_PROMPT_DISPLAY_WIDTH = get_cwidth(" " + COMPOSER_PROMPT_TEXT)

# P3.9 composer polish: an empty input shows a quiet usage hint (display-only;
# any keystroke replaces it — a BeforeInput processor gated on empty buffer).
PLACEHOLDER_TEXT = "给 Zeno 下指令 · Enter 发送 · Alt+Enter 换行 · / 命令"
_FOOTER_PADDING = "  "
_FOOTER_MAX_LINES = 3


def _input_line_prefix(line_number: int, wrap_count: int) -> AnyFormattedText:
    """Align explicit and soft-wrapped continuation lines below input text."""
    if line_number == 0 and wrap_count == 0:
        return FormattedText([])
    return FormattedText(
        [("class:composer.input.indent", " " * _PROMPT_DISPLAY_WIDTH)]
    )


def _split_at_cell_width(text: str, width: int) -> list[str]:
    """Split a long status field without breaking CJK terminal-cell accounting."""
    limit = max(1, width)
    chunks: list[str] = []
    current: list[str] = []
    current_width = 0
    for char in text:
        char_width = max(0, get_cwidth(char))
        if current and current_width + char_width > limit:
            chunks.append("".join(current))
            current = []
            current_width = 0
        current.append(char)
        current_width += char_width
    if current:
        chunks.append("".join(current))
    return chunks or [""]


class _ReflowAwareApplication(Application[str]):
    """Erase from the reflowed prompt origin after a terminal resize.

    Modern terminals reflow already-painted lines *before* delivering SIGWINCH.
    prompt_toolkit's non-full-screen resize handler erases from its cursor
    distance at the old width, which leaves duplicate prompt rows whenever a
    long draft gained a wrapped line. Build the current layout at the new width
    first and give the renderer that reflowed cursor distance before its normal
    erase/redraw cycle. If layout probing ever fails, the upstream behavior is
    retained.
    """

    def reflowed_cursor_position(self):  # noqa: ANN201 — prompt_toolkit Point
        with set_app(self):
            size = self.output.get_size()
            screen = Screen()
            mouse_handlers = MouseHandlers()
            last_height = (
                self.renderer._last_screen.height  # noqa: SLF001 — resize correction
                if self.renderer._last_screen is not None  # noqa: SLF001
                else 0
            )
            preferred = self.layout.container.preferred_height(
                size.columns, size.rows
            ).preferred
            height = min(
                size.rows,
                max(
                    1,
                    self.renderer._min_available_height,  # noqa: SLF001
                    last_height,
                    preferred,
                ),
            )
            self.layout.container.write_to_screen(
                screen,
                mouse_handlers,
                WritePosition(xpos=0, ypos=0, width=size.columns, height=height),
                parent_style="",
                erase_bg=False,
                z_index=None,
            )
            screen.draw_all_floats()
            return screen.get_cursor_position(self.layout.current_window)

    def _on_resize(self) -> None:
        try:
            old_size = self.renderer._last_size  # noqa: SLF001 — see class contract
            new_size = self.output.get_size()
            # Modern terminals add visual rows when shrinking, but screen rows
            # written with autowrap disabled generally stay hard-broken when the
            # terminal expands again. Correct only the shrinking direction;
            # upstream's remembered cursor is right for expansion.
            if old_size is not None and new_size.columns < old_size.columns:
                self.renderer._cursor_pos = (  # noqa: SLF001
                    self.reflowed_cursor_position()
                )
        except Exception:  # noqa: BLE001 — resizing must never break text input
            pass
        super()._on_resize()


class ZenoComposer:
    """Reusable non-full-screen prompt_toolkit composer.

    ``input``/``output`` are injectable prompt_toolkit endpoints so every key
    contract can be tested without a real TTY.  ``toolbar`` is a dynamic,
    display-only formatted-text callback (model/world/live-status in cli.py).
    A broken callback is swallowed and leaves the display-only footer empty.
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
            get_line_prefix=_input_line_prefix,
            focus_on_click=True,
            height=Dimension(min=1, max=6),
            dont_extend_height=True,
            style="class:composer.input",
            name="zeno-composer",
        )

        def _rail_fragments() -> FormattedText:
            width = max(4, self._terminal_width())
            if self.placeholder_visible():
                hint = f" {PLACEHOLDER_TEXT} "
                pad = max(2, width - get_cwidth(hint) - 2)
                return FormattedText([
                    ("class:composer.rail", "──"),
                    ("class:composer.placeholder", hint),
                    ("class:composer.rail", "─" * pad),
                ])
            return FormattedText([("class:composer.rail", "─" * width)])

        def _subrail_fragments() -> FormattedText:
            return FormattedText(
                [("class:composer.rail.close", "─" * max(4, self._terminal_width()))]
            )

        self.rail = Window(
            content=FormattedTextControl(_rail_fragments, show_cursor=False),
            height=1,
            dont_extend_height=True,
            style="class:composer.rail",
        )
        self.subrail = Window(
            content=FormattedTextControl(_subrail_fragments, show_cursor=False),
            height=1,
            dont_extend_height=True,
            style="class:composer.rail.close",
        )
        self.footer = Window(
            content=FormattedTextControl(self.footer_fragments, show_cursor=False),
            height=Dimension(min=1, max=_FOOTER_MAX_LINES),
            dont_extend_height=True,
            style="class:composer.footer",
        )
        self.container = HSplit(
            [self.rail, self.text_area, self.search_toolbar, self.subrail, self.footer]
        )
        root = FloatContainer(
            content=self.container,
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
        self.application: Application[str] = _ReflowAwareApplication(
            layout=Layout(root, focused_element=self.text_area),
            key_bindings=bindings,
            style=style,
            full_screen=False,
            erase_when_done=True,
            refresh_interval=0.5,
            mouse_support=False,
            **kwargs,
        )

    def placeholder_visible(self) -> bool:
        """True iff the input is empty (the usage hint shows). Display-only."""
        try:
            return not bool(self.text_area.text)
        except Exception:  # noqa: BLE001
            return False

    def _terminal_width(self) -> int:
        app = get_app_or_none()
        if app is not None:
            try:
                return max(4, int(app.output.get_size().columns))
            except Exception:  # noqa: BLE001 — layout fallback is display-only
                pass
        return 80

    def _status_parts(self) -> list[str]:
        if self._toolbar is None:
            return []
        try:
            dynamic = self._toolbar()
            dynamic_fragments = list(to_formatted_text(dynamic)) if dynamic else []
        except Exception:  # noqa: BLE001 — status is display-only, never fatal
            dynamic_fragments = []
        plain = "".join(item[1] for item in dynamic_fragments)
        # The CLI toolbar uses pipes; accept middle dots too so callers can
        # migrate independently. Each part remains atomic during normal reflow.
        normalized = plain.replace(" · ", " | ")
        return [part.strip() for part in normalized.split(" | ") if part.strip()]

    _STALE_ODOM_S = 3.0  # odom older than this reads as a warning (display-only)

    def _part_style(self, part: str) -> str:
        """P3.8 footer typography: one style class per part FAMILY.

        ⚙ activity (what Zeno is doing now) · ⌖ pose truth (with an amber
        stale flag when the odometry read is old — the operator must see a
        dead feed at a glance) · quiet identity/counters. Display-only.
        """
        if part.startswith("⚙"):
            return "class:composer.footer.activity"
        if part.startswith("⌖") or "pose" in part or "odom" in part:
            m = re.search(r"odom age\s*=?\s*(\d+(?:\.\d+)?)s", part)
            if m:
                try:
                    if float(m.group(1)) > self._STALE_ODOM_S:
                        return "class:composer.footer.pose.stale"
                except ValueError:
                    pass
            return "class:composer.footer.pose"
        if re.match(r"^(base|arm|world|model|tools|msgs):", part):
            return "class:composer.footer.meta"
        return "class:composer.footer.status"

    def _footer_fragment_lines(self, width: int) -> list[list[tuple[str, str]]]:
        """Wrap styled footer parts (same width discipline as before P3.8)."""
        available = max(1, int(width) - get_cwidth(_FOOTER_PADDING))
        styled = [(self._part_style(p), p) for p in self._status_parts()]
        sep = ("class:composer.footer.sep", " · ")
        sep_w = get_cwidth(sep[1])
        lines: list[list[tuple[str, str]]] = []
        cur: list[tuple[str, str]] = []
        cur_w = 0
        for style, part in styled:
            part_w = get_cwidth(part)
            if cur and cur_w + sep_w + part_w <= available:
                cur.extend((sep, (style, part)))
                cur_w += sep_w + part_w
                continue
            if not cur and part_w <= available:
                cur, cur_w = [(style, part)], part_w
                continue
            if cur:
                lines.append(cur)
                cur, cur_w = [], 0
                if len(lines) >= _FOOTER_MAX_LINES:
                    break
                if part_w <= available:
                    cur, cur_w = [(style, part)], part_w
                    continue
            chunks = _split_at_cell_width(part, available)
            for chunk in chunks[:-1]:
                lines.append([(style, chunk)])
                if len(lines) >= _FOOTER_MAX_LINES:
                    break
            if len(lines) >= _FOOTER_MAX_LINES:
                break
            cur, cur_w = [(style, chunks[-1])], get_cwidth(chunks[-1])
        if cur and len(lines) < _FOOTER_MAX_LINES:
            lines.append(cur)
        return lines

    def _footer_lines(self, width: int) -> list[str]:
        """Plain-text view of the wrapped footer (compat: content unchanged)."""
        return [
            "".join(text for _style, text in line)
            for line in self._footer_fragment_lines(width)
        ]

    def footer_fragments(self, width: int | None = None) -> list[tuple[str, str]]:
        """Responsive, priority-ordered live status — now with per-part styling."""
        fragment_lines = self._footer_fragment_lines(width or self._terminal_width())
        fragments: list[tuple[str, str]] = []
        for index, line in enumerate(fragment_lines):
            if index:
                fragments.append(("", "\n"))
            fragments.append(("class:composer.footer.indent", _FOOTER_PADDING))
            fragments.extend(line)
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
