# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R377 (E166): ``render_response`` must actually syntax-highlight code blocks.

The renderer's docstring promises "syntax-highlighted code blocks" and the module
imports ``rich.syntax.Syntax`` for that purpose, but the original loop captured the
fenced-block language tag (``lang``) and then DROPPED it — painting every code line
a single flat cyan regardless of language (F841 ``lang`` unused + F401 ``Syntax``
imported-but-unused). That made the docstring false on the bare-REPL acceptance face
(what the user reads when V returns code). These guards pin the language tag as
load-bearing: highlighting must differ by language, code content must survive, and
an unknown language must degrade gracefully instead of crashing the REPL.
"""
from __future__ import annotations

from rich.console import Console

from vector_os_nano.vcli.cli import render_response


def _capture(panel, *, styles: bool, width: int = 80) -> str:
    console = Console(width=width, record=True, force_terminal=True, color_system="truecolor")
    console.print(panel)
    return console.export_text(styles=styles)


def test_language_tag_drives_rendering() -> None:
    """The same code under ```python vs ```text must render DIFFERENTLY.

    If ``lang`` were dropped (the original bug) both render identically (flat cyan)
    and this assertion fails. With real Syntax highlighting, python keywords are
    coloured while plain text is not, so the styled output diverges.
    """
    code = "def f():\n    return 1\n"
    py = _capture(render_response(f"```python\n{code}```"), styles=True)
    txt = _capture(render_response(f"```text\n{code}```"), styles=True)
    assert py != txt


def test_code_content_preserved() -> None:
    """Highlighting must never drop the code text itself."""
    panel = render_response("```python\nSENTINEL_TOKEN = 42\n```")
    assert "SENTINEL_TOKEN" in _capture(panel, styles=False)
    assert "42" in _capture(panel, styles=False)


def test_prose_around_block_preserved() -> None:
    """Text before and after a fenced block still renders."""
    panel = render_response("before text\n```python\nx = 1\n```\nafter text")
    out = _capture(panel, styles=False)
    assert "before text" in out
    assert "after text" in out
    assert "x = 1" in out


def test_unknown_language_does_not_crash() -> None:
    """An unknown/garbage language tag must degrade to plain text, never raise —
    a crash here would take down the user-facing REPL render path."""
    panel = render_response("```zzznotarealang\npayload = 1\n```")
    out = _capture(panel, styles=False)
    assert "payload = 1" in out


def test_no_code_block_still_renders() -> None:
    """Plain prose with no fenced block renders unchanged."""
    panel = render_response("just a plain sentence")
    assert "just a plain sentence" in _capture(panel, styles=False)
