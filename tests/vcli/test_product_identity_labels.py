# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""User-visible product-identity labels must read 'Zeno', not the legacy 'V'.

Covers the high-frequency REPL surfaces the audit flagged:
- V_LABEL: the brand glyph reused as the title of every response Panel.
- The startup ASCII wordmark.
- The /export markdown assistant-line prefix.
- The /agent slash-command description shown in /help and the completer.

Pure-offline: no sim, no network. Reads the module constants and drives
_handle_slash_command with a capturing console.
"""
from __future__ import annotations

from typing import Any

import zeno.vcli.cli as cli


class _DummyRegistry:
    def list_tools(self) -> list[Any]:
        return []

    def get(self, _name: str) -> Any:
        return None


def test_response_panel_brand_label_is_zeno() -> None:
    """V_LABEL titles every reply Panel — it must render Zeno, not the braille V."""
    # The old value was the braille dot-art "V" (⠣⡠⠃).
    assert "⠣⡠⠃" not in cli.V_LABEL, cli.V_LABEL
    assert "Zeno" in cli.V_LABEL, cli.V_LABEL


def test_slash_agent_description_names_zeno() -> None:
    """The /agent command description (shown in /help + completer) must say Zeno."""
    descs = {name: desc for name, desc, _ in cli.SLASH_COMMANDS}
    assert "agent" in descs
    assert "Zeno" in descs["agent"], descs["agent"]
    assert "V's identity" not in descs["agent"], descs["agent"]


def test_export_assistant_prefix_is_zeno() -> None:
    """/export writes each assistant turn under a Zeno-named prefix, not '**V:**'."""

    class _Session:
        session_id = "unit-test-export"

        def __init__(self) -> None:
            self._entries = [
                {"type": "user", "content": "hello"},
                {"type": "assistant", "text": "hi there"},
            ]

    sess = _Session()
    # Drive /export and read back the file it wrote.
    with cli.console.capture():
        cli._handle_slash_command(
            "export", [], registry=_DummyRegistry(), session=sess, app_state={}
        )
    export_path = cli._persist_dir() / "exports" / f"{sess.session_id}.md"
    text = export_path.read_text(encoding="utf-8")
    assert "**Zeno:**" in text, text
    assert "**V:**" not in text, text


def test_login_help_names_zeno_not_v() -> None:
    """The /login help line must credit Zeno, not the legacy short name 'V'.

    Old copy: "/login claude gives V its own rate limit pool ...". Reachable by
    typing bare /login in the REPL (no provider argument).
    """
    with cli.console.capture() as cap:
        cli._handle_slash_command(
            "login", [], registry=_DummyRegistry(), app_state={}
        )
    text = cap.get()
    assert "gives Zeno its own rate limit pool" in text, text
    assert "gives V its own" not in text, text


def test_startup_ascii_wordmark_is_zeno() -> None:
    """Brand belongs to startup, not repeated as input chrome every keystroke."""
    from zeno.vcli.banner import WIDE_ZENO_LOGO

    assert WIDE_ZENO_LOGO[0].startswith("ZZZZZZZZ  EEEEEEEE")
    assert any("NN     NN" in line for line in WIDE_ZENO_LOGO)
    assert any("OOOOOO" in line for line in WIDE_ZENO_LOGO)
