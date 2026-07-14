# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""The interactive REPL is wired to the framed composer, not a bare prompt."""
from __future__ import annotations

import inspect

from zeno.vcli import cli
from zeno.vcli.composer import COMPOSER_PROMPT_TEXT


def test_main_uses_composer_and_persists_compact_submission() -> None:
    source = inspect.getsource(cli.main)
    assert "ZenoComposer(" in source
    assert "composer.prompt()" in source
    assert "render_submission(raw)" in source
    assert "pt_session.prompt(" not in source


def test_acceptance_prompt_marker_survives_redesign() -> None:
    assert COMPOSER_PROMPT_TEXT == "zeno> "

