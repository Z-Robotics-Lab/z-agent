# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""dashboard — the info-density TUI (P4, owner chose the monitoring panel).

A full-screen prompt_toolkit Application with three persistent regions:

    ┌ ZENO ───────────────── go2w_hw · deepseek-v4-pro · auto ┐  status panel
    │ ⌖ pose … · course … · odom … · estop OK · stack UP      │  (top, always on)
    ├─────────────────────────────────────────────────────────┤
    │ #3 14:22 规划…                              native · 54s │  turn region
    │   ◇ move_relative  forward 2m   verify at(…)  ✓ 5.6s     │  (middle, scroll)
    │   ✓ verified 5/5 grounded                               │
    ├─────────────────────────────────────────────────────────┤
    │ › 回到充电桩_                                            │  input (bottom)
    │ ⚙ navigate 执行中… · round 2 · 3.1s                     │
    └─────────────────────────────────────────────────────────┘

DISPLAY-ONLY (CLAUDE.md Inv-1): the panel reads the SAME ``live_status_line``
world hook and consumes the SAME ``NativeEvent`` stream the model plans from;
it never feeds routing/execution/verification. The ``-p`` machine path is
untouched — the dashboard is purely the interactive REPL's shape.

Stage 1 (this file): the pure status renderer + the three-region layout
construction + input→submit plumbing. Turn-region event consumption and
worker execution are stage 2. Colors come from ``zeno.vcli.palette`` (P3.12).
"""
from __future__ import annotations

import re
from typing import Any, Callable

from prompt_toolkit.formatted_text import StyleAndTextTuples

from zeno.vcli import palette as _p

# Fragment style classes (mapped to concrete colors in the Style built at run).
_S_BRAND = "class:dash.brand"
_S_META = "class:dash.meta"
_S_SEP = "class:dash.sep"
_S_POSE = "class:dash.pose"
_S_POSE_STALE = "class:dash.pose.stale"
_S_OK = "class:dash.ok"
_S_DANGER = "class:dash.danger"
_S_LABEL = "class:dash.label"

_STALE_ODOM_S = 3.0


def dashboard_style_rules() -> dict[str, str]:
    """prompt_toolkit style rules for the dashboard, sourced from the palette."""
    return {
        "dash.brand": f"bold {_p.BRAND}",
        "dash.meta": _p.TEXT_FAINT,
        "dash.sep": _p.HAIRLINE,
        "dash.pose": _p.POSE,
        "dash.pose.stale": "bold #d97706",
        "dash.ok": _p.OK,
        "dash.danger": f"bold {_p.BAD}",
        "dash.label": _p.TEXT_DIM,
        "dash.status.bg": f"bg:#0f141c {_p.TEXT_DIM}",
        "dash.turn.bg": _p.TEXT,
        "dash.input.bg": f"bg:#0f141c {_p.TEXT}",
    }


def _odom_is_stale(live_status: str) -> bool:
    m = re.search(r"odom age\s*=?\s*(\d+(?:\.\d+)?)s", live_status or "")
    if not m:
        return False
    try:
        return float(m.group(1)) > _STALE_ODOM_S
    except ValueError:
        return False


def render_status_panel(status: dict[str, Any]) -> StyleAndTextTuples:
    """Pure projection of display-only status into a fragment list (2 lines).

    Never raises, never parses markup from ``live_status`` (it is inserted as a
    literal fragment, so a spoofed ``[bold]`` / ``<b>`` renders verbatim).
    """
    live = str(status.get("live_status", "") or "")
    model = str(status.get("model", "?") or "?").split("/")[-1]
    base = str(status.get("base", "") or "")
    tools = status.get("tools", 0)
    msgs = status.get("msgs", 0)
    perms = str(status.get("permissions", "") or "")
    estop = bool(status.get("estop", False))

    frags: StyleAndTextTuples = []
    # Line 1 — brand + identity.
    frags.append((_S_BRAND, "ZENO"))
    frags.append((_S_META, "   "))
    ident = []
    if base:
        ident.append(base)
    ident.append(model)
    if perms:
        ident.append(perms)
    for i, part in enumerate(ident):
        if i:
            frags.append((_S_SEP, " · "))
        frags.append((_S_META, part))
    if estop:
        frags.append((_S_SEP, "   "))
        frags.append((_S_DANGER, "● ESTOP LATCHED"))
    frags.append(("", "\n"))

    # Line 2 — the live pose/course/odom truth (literal, escaped by construction).
    pose_style = _S_POSE_STALE if _odom_is_stale(live) else _S_POSE
    frags.append((_S_LABEL, "⌖ "))
    frags.append((pose_style, live or "(no odometry)"))
    frags.append((_S_SEP, "   ·   "))
    frags.append((_S_LABEL, f"tools {tools} · msgs {msgs}"))
    return frags


class Dashboard:
    """The three-region full-screen REPL (stage 1: layout + input plumbing)."""

    def __init__(
        self,
        *,
        status_provider: Callable[[], dict[str, Any]],
        identity_provider: Callable[[], dict[str, Any]],
        on_submit: Callable[[str], None],
        completer: Any = None,
        style: Any = None,
    ) -> None:
        self._status_provider = status_provider
        self._identity_provider = identity_provider
        self._on_submit = on_submit
        self._completer = completer
        self._style = style
        self._turn_lines: list[str] = []
        self._activity = ""
        self._app: Any = None
        self._text_area: Any = None

    # -- pure-ish render sources (testable without a TTY) ----------------

    def _status_fragments(self) -> StyleAndTextTuples:
        try:
            merged = {**self._identity_provider(), **self._status_provider()}
        except Exception:  # noqa: BLE001 — status is display-only, never fatal
            merged = {}
        return render_status_panel(merged)

    def _turn_text(self) -> str:
        return "\n".join(self._turn_lines)

    def _turn_fragments(self) -> StyleAndTextTuples:
        from prompt_toolkit.formatted_text import to_formatted_text
        from prompt_toolkit.formatted_text import HTML  # noqa: F401 — parity import

        out: StyleAndTextTuples = []
        for i, line in enumerate(self._turn_lines):
            if i:
                out.append(("", "\n"))
            # Rich markup -> plain text for the buffer (stage 2 maps to PT styles).
            out.extend(to_formatted_text(_rich_to_plain(line)))
        return out

    # -- mutation (called by the worker / REPL) --------------------------

    def append_turn_line(self, line: str) -> None:
        self._turn_lines.append(line)
        self._invalidate()

    def set_activity(self, text: str) -> None:
        self._activity = str(text or "")
        self._invalidate()

    def submit(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        try:
            self._on_submit(text)
        except Exception:  # noqa: BLE001 — a submit handler bug must not wedge input
            pass

    def _invalidate(self) -> None:
        if self._app is not None:
            try:
                self._app.invalidate()
            except Exception:  # noqa: BLE001
                pass

    # -- layout construction (testable) ----------------------------------

    def build_layout(self) -> Any:
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.widgets import TextArea

        status = Window(
            content=FormattedTextControl(self._status_fragments),
            height=Dimension(min=2, max=3),
            style="class:dash.status.bg",
        )
        turn = Window(
            content=FormattedTextControl(self._turn_fragments),
            style="class:dash.turn.bg",
            wrap_lines=True,
        )
        self._text_area = TextArea(
            height=Dimension(min=1, max=6),
            multiline=True,
            completer=self._completer,
            prompt="› ",
            style="class:dash.input.bg",
            accept_handler=self._accept,
        )
        footer = Window(
            content=FormattedTextControl(self._footer_fragments),
            height=1,
            style="class:dash.status.bg",
        )
        root = HSplit([
            status,
            Window(height=1, char="─", style="class:dash.sep"),
            turn,
            Window(height=1, char="─", style="class:dash.sep"),
            self._text_area,
            footer,
        ])
        layout = Layout(root, focused_element=self._text_area)
        self._layout = layout
        return layout

    def _accept(self, buffer: Any) -> bool:
        text = buffer.text
        # Clear the input for the next line (returns False to keep the buffer
        # in the standard TextArea accept protocol; we reset text ourselves).
        buffer.text = ""
        self.submit(text)
        return False

    def _footer_fragments(self) -> StyleAndTextTuples:
        out: StyleAndTextTuples = []
        if self._activity:
            out.append((_S_BRAND, f"⚙ {self._activity}"))
            out.append((_S_SEP, "   ·   "))
        out.append((_S_META, "Enter 发送 · /help · quit 退出"))
        return out

    # -- run (thin; not unit-tested — needs a TTY) -----------------------

    def run(self) -> None:  # pragma: no cover — interactive
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings

        kb = KeyBindings()

        @kb.add("c-c")
        @kb.add("c-d")
        def _exit(event: Any) -> None:
            event.app.exit()

        self._app = Application(
            layout=self.build_layout(),
            key_bindings=kb,
            style=self._style,
            full_screen=True,
            mouse_support=False,
            refresh_interval=0.5,
        )
        self._app.run()


def _rich_to_plain(markup: str) -> str:
    """Strip Rich markup tags to plain text (stage 1 turn-region buffer).

    Stage 2 will map evidence colors to prompt_toolkit style fragments; for now
    the skeleton shows the structure without color in the turn region.
    """
    return re.sub(r"\[/?[^\]]*\]", "", str(markup))
