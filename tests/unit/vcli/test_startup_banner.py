# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Responsive startup wordmark — presentation only, no world/model/hardware."""
from __future__ import annotations

import os

from zeno.vcli import cli
from zeno.vcli.banner import (
    COMPACT_ZENO_LOGO,
    WIDE_ZENO_LOGO,
    centered_logo_lines,
    logo_reveal_width,
    logo_lines_for_width,
    reveal_logo_lines,
    styled_logo_line,
)


REFERENCE_ZENO_LOGO = (
    "███████╗ ███████╗ ███╗   ██╗  ██████╗ ",
    "╚══███╔╝ ██╔════╝ ████╗  ██║ ██╔═══██╗",
    "  ███╔╝  █████╗   ██╔██╗ ██║ ██║   ██║",
    " ███╔╝   ██╔══╝   ██║╚██╗██║ ██║   ██║",
    "███████╗ ███████╗ ██║ ╚████║ ╚██████╔╝",
    "╚══════╝ ╚══════╝ ╚═╝  ╚═══╝  ╚═════╝ ",
)


def test_wide_logo_matches_the_owner_supplied_terminal_wordmark() -> None:
    assert WIDE_ZENO_LOGO == REFERENCE_ZENO_LOGO
    assert len(WIDE_ZENO_LOGO) == 6
    assert {len(line) for line in WIDE_ZENO_LOGO} == {38}


def test_wide_logo_preserves_the_reference_light_and_graphite_layers() -> None:
    rendered = styled_logo_line(WIDE_ZENO_LOGO[0], 0)

    assert rendered.plain == WIDE_ZENO_LOGO[0]
    assert rendered.style == "italic #5a5e65"
    assert rendered.spans[0].start == 0
    assert rendered.spans[0].end == 7
    assert rendered.spans[0].style == "bold italic #e0eafc"


def test_logo_switches_complete_variants_instead_of_slicing_art() -> None:
    assert logo_lines_for_width(60) == WIDE_ZENO_LOGO
    assert logo_lines_for_width(40) == WIDE_ZENO_LOGO
    assert logo_lines_for_width(38) == WIDE_ZENO_LOGO
    assert logo_lines_for_width(37) == COMPACT_ZENO_LOGO
    assert logo_lines_for_width(24) == COMPACT_ZENO_LOGO
    assert logo_lines_for_width(8) == ("ZENO",)

    for width in (100, 60, 40, 38, 37, 24, 8, 4):
        rendered = centered_logo_lines(width)
        assert rendered
        assert max(map(len, rendered)) <= width
        indent = len(rendered[0]) - len(rendered[0].lstrip())
        assert tuple(line[indent:] for line in rendered) == logo_lines_for_width(width)


def test_logo_reveal_sweeps_left_to_right_without_layout_jitter() -> None:
    lines = ("  ABCD", "   EFG")

    assert logo_reveal_width(lines) == 4
    assert reveal_logo_lines(lines, 0) == ("      ", "      ")
    assert reveal_logo_lines(lines, 2) == ("  AB  ", "   E  ")
    assert reveal_logo_lines(lines, 4) == lines

    # Every frame occupies exactly the final geometry, so the metadata below
    # the logo never jumps while the mark emerges.
    for visible in range(5):
        frame = reveal_logo_lines(lines, visible)
        assert tuple(map(len, frame)) == tuple(map(len, lines))


def test_print_banner_uses_wordmark_and_keeps_session_metadata(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda: os.terminal_size((60, 24)),
    )
    sleeps: list[float] = []
    monkeypatch.setattr(cli.time, "sleep", sleeps.append)

    with cli.console.capture() as captured:
        cli.print_banner("deepseek-v4-pro", "DeepSeek")

    output = captured.get()
    assert WIDE_ZENO_LOGO[0] in output
    assert WIDE_ZENO_LOGO[-1] in output
    assert "v0.1.0" in output
    assert "Model: deepseek-v4-pro | Provider: DeepSeek" in output
    assert "Type / for commands, quit to exit" in output
    assert sleeps == []  # captures/pipes receive one clean final frame instantly


def test_interactive_banner_reveals_logo_in_under_one_second(monkeypatch) -> None:
    from io import StringIO

    from rich.console import Console

    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda: os.terminal_size((60, 24)),
    )
    now = [10.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(cli.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    output = StringIO()
    monkeypatch.setattr(
        cli,
        "console",
        Console(file=output, force_terminal=True, color_system=None, width=60),
    )

    cli.print_banner("deepseek-v4-pro", "DeepSeek")

    assert sleeps
    assert sum(sleeps) <= 1.0
    assert WIDE_ZENO_LOGO[-1] in output.getvalue()


def test_narrow_banner_wraps_metadata_at_fields_and_keeps_indent(monkeypatch) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda: os.terminal_size((40, 24)),
    )

    with cli.console.capture() as captured:
        cli.print_banner("claude-haiku-4-5", "Anthropic")

    lines = [line.rstrip() for line in captured.get().splitlines()]
    assert "  Model: claude-haiku-4-5" in lines
    assert "  Provider: Anthropic" in lines
    assert "Anthropic" not in lines
