# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Scripted PTY acceptance for the REPL display/interaction fixes.

Drives the REAL ``zeno`` REPL under a stdlib PTY (dev world, no network/sim) and
confirms the field-reported fixes hold end-to-end at the actual entrypoint:

  5. /where is a real command (not "Unknown"), and an unknown slash suggests the
     closest command + notes that natural language works.
  1. No raw ``WARNING:zeno...`` log line is painted into the transcript — logging
     is routed to ``~/.zeno/logs/`` instead of the prompt line (花屏 fix), and the
     log file is created under the session HOME.

Bugs 2 (裸 markdown) and 3 (思考 preview) are asserted at their render seams in
tests/vcli/test_cli_display_fixes.py and tests/unit/vcli/test_chain_view.py — the
offline fake backend cannot stream a chat answer + reasoning, so those seams are
verified directly rather than through this PTY.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.harness.pty_cli import run_repl_session

_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _plain(transcript: str) -> str:
    return _ANSI.sub("", transcript).replace("\r", "")


def test_where_command_known_and_unknown_slash_suggests_closest() -> None:
    result = run_repl_session(
        [
            (0.0, "/help"),
            (0.6, "/wher"),   # typo -> closest-match suggestion
            (0.6, "/zzzqqq"), # no close match -> generic hint
            (0.6, "quit"),
        ],
        boot_sec=2.5,
        settle_sec=1.2,
        extra_env={
            "ZENO_WORLD": "dev",
            "VECTOR_WORLD": "dev",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        },
    )
    text = _plain(result.transcript)

    # /where is a REGISTERED command (shown in /help), never reported Unknown.
    assert "/where" in text
    assert "Unknown: /where" not in text and "未知命令 /where" not in text

    # Unknown /wher -> closest-match suggestion + natural-language hint.
    assert "未知命令 /wher" in text
    assert "自然语言" in text
    # The suggestion points at the real command.
    assert "/where" in text

    # No stray library WARNING corrupts the prompt line (花屏 fix).
    assert "WARNING:zeno" not in text

    assert result.exit_code == 0


def test_repl_routes_logging_to_file_not_the_prompt(tmp_path_factory) -> None:
    """The session HOME gets a ~/.zeno/logs/zeno.log; the terminal transcript
    carries no raw WARNING/ERROR log lines."""
    home = tmp_path_factory.mktemp("zeno_pty_home")
    result = run_repl_session(
        [(0.0, "quit")],
        boot_sec=2.5,
        settle_sec=1.0,
        extra_env={
            "HOME": str(home),
            "ZENO_WORLD": "dev",
            "VECTOR_WORLD": "dev",
            "PROMPT_TOOLKIT_NO_CPR": "1",
        },
    )
    text = _plain(result.transcript)
    assert "WARNING:zeno" not in text
    assert "Connection error" not in text  # library warning never on the prompt
    # The file sink was installed under the session HOME.
    assert (Path(home) / ".zeno" / "logs" / "zeno.log").is_file()
