# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Bare-``zeno`` PTY acceptance for the compact input composer.

No network, model call, sim, or hardware: the real interactive entry point runs
in an isolated HOME/dev world, receives the same LF ``sendline`` used by every
acceptance driver, renders /help, then exits through a second composer cycle.
"""
from __future__ import annotations

import re

from tests.harness.pty_cli import run_repl_session


def test_bare_repl_logo_compact_rail_multiline_help_and_lf_submit() -> None:
    result = run_repl_session(
        [
            (0.0, "/help\x1b\r  "),  # Alt+Enter newline, then LF submits.
            (1.0, "quit"),
        ],
        boot_sec=1.5,
        settle_sec=1.0,
        extra_env={
            "ZENO_WORLD": "dev",
            "VECTOR_WORLD": "dev",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        },
    )

    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.transcript).replace("\r", "")
    assert result.exit_code == 0
    assert "ZZZZZZZZ  EEEEEEEE" in text
    assert all(glyph not in text for glyph in ("┌", "┐", "└", "┘"))
    assert "zeno>" in text  # stable acceptance marker beside the open input rail
    assert "? 快捷键" in text
    assert "› /help" in text  # submitted rail collapsed to compact transcript
    assert "Shortcuts:" in text and "insert newline" in text
