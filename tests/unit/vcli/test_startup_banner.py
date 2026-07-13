# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Responsive startup wordmark — presentation only, no world/model/hardware."""
from __future__ import annotations

import os
import string

from zeno.vcli import cli
from zeno.vcli.banner import (
    COMPACT_ZENO_LOGO,
    WIDE_ZENO_LOGO,
    centered_logo_lines,
    logo_lines_for_width,
)


def test_wide_logo_is_a_large_literal_ascii_zeno_wordmark() -> None:
    assert len(WIDE_ZENO_LOGO) == 6
    assert max(map(len, WIDE_ZENO_LOGO)) >= 36
    assert all(set(line) <= set(string.printable) for line in WIDE_ZENO_LOGO)
    assert WIDE_ZENO_LOGO[0].startswith("ZZZZZZZZ  EEEEEEEE")
    assert "NN     NN" in WIDE_ZENO_LOGO[0]
    assert "OOOOOO" in WIDE_ZENO_LOGO[0]


def test_logo_switches_complete_variants_instead_of_slicing_art() -> None:
    assert logo_lines_for_width(60) == WIDE_ZENO_LOGO
    assert logo_lines_for_width(40) == COMPACT_ZENO_LOGO
    assert logo_lines_for_width(24) == COMPACT_ZENO_LOGO
    assert logo_lines_for_width(8) == ("ZENO",)

    for width in (100, 60, 40, 24, 8, 4):
        rendered = centered_logo_lines(width)
        assert rendered
        assert max(map(len, rendered)) <= width
        indent = len(rendered[0]) - len(rendered[0].lstrip())
        assert tuple(line[indent:] for line in rendered) == logo_lines_for_width(width)


def test_print_banner_uses_wordmark_and_keeps_session_metadata(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cli.shutil,
        "get_terminal_size",
        lambda: os.terminal_size((60, 24)),
    )
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    with cli.console.capture() as captured:
        cli.print_banner("deepseek-v4-pro", "DeepSeek")

    output = captured.get()
    assert WIDE_ZENO_LOGO[0] in output
    assert WIDE_ZENO_LOGO[-1] in output
    assert "v0.1.0" in output
    assert "Model: deepseek-v4-pro | Provider: DeepSeek" in output
    assert "Type / for commands, quit to exit" in output
