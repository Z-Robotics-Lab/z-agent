# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Responsive, dependency-free Zeno startup wordmark.

The old banner depended on an optional ``logo_braille.txt`` asset and degraded
to a single ``Zeno`` word when that file was absent. The product entry now owns
the owner's six-line terminal wordmark plus complete narrow variants in code,
so startup branding is deterministic in every checkout and no terminal width
ever receives a sliced, illegible logo.

This module is presentation-only. It imports no engine, world, hardware, or
verification code.
"""
from __future__ import annotations

from rich.cells import cell_len, chop_cells
from rich.text import Text


WIDE_ZENO_LOGO: tuple[str, ...] = (
    "███████╗ ███████╗ ███╗   ██╗  ██████╗ ",
    "╚══███╔╝ ██╔════╝ ████╗  ██║ ██╔═══██╗",
    "  ███╔╝  █████╗   ██╔██╗ ██║ ██║   ██║",
    " ███╔╝   ██╔══╝   ██║╚██╗██║ ██║   ██║",
    "███████╗ ███████╗ ██║ ╚████║ ╚██████╔╝",
    "╚══════╝ ╚══════╝ ╚═╝  ╚═══╝  ╚═════╝ ",
)

COMPACT_ZENO_LOGO: tuple[str, ...] = (
    "ZZZZ EEEE N  N  OOO",
    "  Z  E    NN N O   O",
    " Z   EEE  N NN O   O",
    "Z    E    N  N O   O",
    "ZZZZ EEEE N  N  OOO",
)

_PLAIN_ZENO_LOGO = ("ZENO",)
# The supplied mark already carries its own whitespace and is only 38 cells
# wide. Keep it intact down to that exact width; centering adds room whenever
# the terminal has any to spare.
_HORIZONTAL_GUTTER = 0
_MAX_BRAND_CANVAS = 80
_TERMINAL_BRAND = "#00b4b4"
_WIDE_PRIMARY = (
    "#e0eafc",
    "#dde8fa",
    "#d9e5f8",
    "#d6e3f7",
    "#d2e0f5",
    "#cfdcf3",
)
_WIDE_SECONDARY = (
    "#5a5e65",
    "#585d64",
    "#575c63",
    "#565b63",
    "#545a62",
    "#535961",
)


def _logo_width(lines: tuple[str, ...]) -> int:
    return max((len(line) for line in lines), default=0)


def logo_lines_for_width(terminal_width: int) -> tuple[str, ...]:
    """Return the largest *complete* wordmark that fits ``terminal_width``."""
    width = max(1, int(terminal_width))
    usable = max(0, width - _HORIZONTAL_GUTTER)
    if _logo_width(WIDE_ZENO_LOGO) <= usable:
        return WIDE_ZENO_LOGO
    if _logo_width(COMPACT_ZENO_LOGO) <= usable:
        return COMPACT_ZENO_LOGO
    if width >= len(_PLAIN_ZENO_LOGO[0]):
        return _PLAIN_ZENO_LOGO
    return (_PLAIN_ZENO_LOGO[0][:width],)


def centered_logo_lines(terminal_width: int) -> tuple[str, ...]:
    """Lay out the selected logo on a restrained Claude-style brand canvas."""
    width = max(1, int(terminal_width))
    logo = logo_lines_for_width(width)
    canvas_width = min(width, _MAX_BRAND_CANVAS)
    indent = max(0, (canvas_width - _logo_width(logo)) // 2)
    return tuple((" " * indent) + line for line in logo)


def _shared_left_indent(lines: tuple[str, ...]) -> int:
    """Return layout indentation shared by every non-blank logo row."""
    indents = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    return min(indents, default=0)


def logo_reveal_width(lines: tuple[str, ...]) -> int:
    """Cell width swept by the reveal, excluding the centering indentation."""
    origin = _shared_left_indent(lines)
    return max((cell_len(line[origin:]) for line in lines), default=0)


def reveal_logo_lines(
    lines: tuple[str, ...], visible_cells: int
) -> tuple[str, ...]:
    """Reveal a fixed-geometry logo frame from left to right.

    Hidden cells are replaced with spaces instead of removed. The six-row live
    region therefore never changes size and metadata below it cannot jump while
    the wordmark emerges.
    """
    if not lines:
        return ()
    origin = _shared_left_indent(lines)
    visible = max(0, int(visible_cells))
    if visible >= logo_reveal_width(lines):
        return lines

    frame: list[str] = []
    for line in lines:
        prefix = line[:origin]
        body = line[origin:]
        if visible <= 0 or not body:
            shown = ""
        else:
            chunks = chop_cells(body, visible)
            shown = chunks[0] if chunks else ""
        hidden_width = max(0, cell_len(body) - cell_len(shown))
        frame.append(prefix + shown + (" " * hidden_width))
    return tuple(frame)


def styled_logo_line(line: str, row: int) -> Text:
    """Recreate the supplied logo's light faces and graphite construction lines."""
    if "█" not in line and not any(char in line for char in "╗╚═╔╝║"):
        return Text(line, style=f"bold {_TERMINAL_BRAND}")

    palette_row = max(0, min(int(row), len(_WIDE_SECONDARY) - 1))
    # SGR italic is the cell-safe approximation of the reference HTML's
    # skewX(-18deg): capable terminals shear the glyphs, while others degrade
    # to the same complete fixed-width mark without changing layout.
    text = Text(line, style=f"italic {_WIDE_SECONDARY[palette_row]}")
    start: int | None = None
    for offset, char in enumerate(line + " "):
        if char == "█" and start is None:
            start = offset
        elif char != "█" and start is not None:
            text.stylize(
                f"bold italic {_WIDE_PRIMARY[palette_row]}", start, offset
            )
            start = None
    return text


def metadata_lines_for_width(
    parts: list[str], terminal_width: int
) -> tuple[str, ...]:
    """Pack complete metadata fields; never wrap halfway through a label."""
    available = max(1, int(terminal_width) - 4)
    lines: list[str] = []
    current = ""
    for part in parts:
        if cell_len(part) > available:
            if current:
                lines.append(current)
                current = ""
            chunk = ""
            for char in part:
                if chunk and cell_len(chunk + char) > available:
                    lines.append(chunk)
                    chunk = ""
                chunk += char
            if chunk:
                lines.append(chunk)
            continue
        candidate = part if not current else f"{current} | {part}"
        if current and cell_len(candidate) > available:
            lines.append(current)
            current = part
        else:
            current = candidate
    if current:
        lines.append(current)
    return tuple(lines)
