# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""OSC 8 clickable links in reply/status render (cli-ux report §4-2).

Reply and status lines carry addresses the operator wants to click — chiefly the
manip UI ``http://127.0.0.1:8766``. On a hyperlink-capable terminal the renderer must
wrap the URL in an OSC 8 escape (``ESC ] 8 ; ; <url> ESC \\`` … ``ESC ] 8 ; ; ESC \\``)
so it is one click; on everything else it MUST degrade to plain styled text with no
escape (a raw OSC 8 on a non-supporting terminal is garbage). These guards pin both
branches of ``_append_highlighted_text`` — the single choke point every reply URL
flows through (render_response, streamed answer lines) — plus the capability gate.
"""
from __future__ import annotations

import io

from rich.console import Console
from rich.text import Text

from zeno.vcli.cli import _append_highlighted_text, _hyperlinks_enabled

OSC8_START = "\x1b]8;"  # start (and the id-carrying open) of an OSC 8 hyperlink
UI_URL = "http://127.0.0.1:8766"


def _render(raw: str, *, terminal: bool) -> str:
    """Run raw prose through the production highlight path and render to bytes."""
    body = Text()
    _append_highlighted_text(body, raw)
    console = Console(
        file=io.StringIO(),
        force_terminal=terminal or None,
        color_system="truecolor" if terminal else None,
        width=120,
    )
    console.print(body)
    return console.file.getvalue()


def test_url_wrapped_in_osc8_when_supported(monkeypatch) -> None:
    """A supported terminal emits an OSC 8 hyperlink around the manip UI address."""
    monkeypatch.setenv("ZENO_HYPERLINKS", "1")
    out = _render(f"manip UI -> {UI_URL} (ready)", terminal=True)
    assert OSC8_START in out, "expected an OSC 8 escape wrapping the URL"
    # The URL appears as the hyperlink target AND remains visible as the label.
    assert UI_URL in out
    # Proper close: OSC 8 with an empty target terminates the link.
    assert "\x1b]8;;\x1b\\" in out


def test_url_plain_when_disabled(monkeypatch) -> None:
    """When hyperlinks are gated off, the URL prints plainly with NO OSC 8 escape."""
    monkeypatch.setenv("ZENO_HYPERLINKS", "0")
    out = _render(f"manip UI -> {UI_URL} (ready)", terminal=True)
    assert OSC8_START not in out, "URL must degrade to plain text, no OSC 8 escape"
    assert UI_URL in out, "the address itself must still be visible/copyable"


def test_url_plain_on_non_terminal(monkeypatch) -> None:
    """Even 'enabled', a non-terminal sink (pipe/file) carries no escape — rich only
    emits OSC 8 to a real terminal, so redirected output stays clean."""
    monkeypatch.setenv("ZENO_HYPERLINKS", "1")
    out = _render(f"open {UI_URL}", terminal=False)
    assert OSC8_START not in out
    assert UI_URL in out


def test_trailing_period_not_swallowed(monkeypatch) -> None:
    """'see http://x:8766.' — the sentence period must not become part of the link."""
    monkeypatch.setenv("ZENO_HYPERLINKS", "1")
    out = _render(f"see {UI_URL}.", terminal=True)
    # The visible text still ends with the period, and the link target excludes it.
    assert out.rstrip().endswith(".")
    assert f"{UI_URL}." not in out.replace("\x1b]8;;", "")  # url+'.' never a link target


def test_capability_gate_env_overrides(monkeypatch) -> None:
    """The capability gate honours explicit overrides and degrades on dumb/unset TERM."""
    monkeypatch.setenv("ZENO_HYPERLINKS", "1")
    assert _hyperlinks_enabled() is True
    monkeypatch.setenv("ZENO_HYPERLINKS", "0")
    assert _hyperlinks_enabled() is False

    monkeypatch.delenv("ZENO_HYPERLINKS", raising=False)
    monkeypatch.delenv("NO_HYPERLINKS", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    assert _hyperlinks_enabled() is False
    monkeypatch.setenv("TERM", "")
    assert _hyperlinks_enabled() is False

    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("NO_HYPERLINKS", "1")
    assert _hyperlinks_enabled() is False


def test_non_url_prose_unaffected(monkeypatch) -> None:
    """Paths and inline code still render; the URL change is additive, not a regression."""
    monkeypatch.setenv("ZENO_HYPERLINKS", "1")
    out = _render("edit /home/z/foo.py then run `zeno`", terminal=True)
    assert "/home/z/foo.py" in out
    assert "zeno" in out
    assert OSC8_START not in out  # no URL present -> no hyperlink escape
