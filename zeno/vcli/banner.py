# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Responsive, dependency-free Zeno startup wordmark.

The old banner depended on an optional ``logo_braille.txt`` asset and degraded
to a single ``Zeno`` word when that file was absent. The product entry now owns
three complete variants in code so startup branding is deterministic in every
checkout and no terminal width ever receives a sliced, illegible logo.

This module is presentation-only. It imports no engine, world, hardware, or
verification code.
"""
from __future__ import annotations


WIDE_ZENO_LOGO: tuple[str, ...] = (
    "ZZZZZZZZ  EEEEEEEE  NN     NN   OOOOOO",
    "     ZZ   EE        NNN    NN  OO    OO",
    "    ZZ    EEEEEE    NN N   NN  OO    OO",
    "   ZZ     EE        NN  N  NN  OO    OO",
    "  ZZ      EE        NN   N NN  OO    OO",
    "ZZZZZZZZ  EEEEEEEE  NN    NNN   OOOOOO",
)

COMPACT_ZENO_LOGO: tuple[str, ...] = (
    "ZZZZ EEEE N  N  OOO",
    "  Z  E    NN N O   O",
    " Z   EEE  N NN O   O",
    "Z    E    N  N O   O",
    "ZZZZ EEEE N  N  OOO",
)

_PLAIN_ZENO_LOGO = ("ZENO",)
_HORIZONTAL_GUTTER = 4
_MAX_BRAND_CANVAS = 80


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
