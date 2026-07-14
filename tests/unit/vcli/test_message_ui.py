# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Minimal conversational message hierarchy — presentation-only contracts."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from zeno.vcli import cli


def test_answer_only_vgg_scaffold_is_hidden_but_action_steps_remain() -> None:
    assert cli._is_answer_only_display_step(
        SimpleNamespace(sub_goal_name="answer", strategy="answer")
    )
    assert cli._is_answer_only_display_step(
        {"sub_goal_name": "answer", "strategy": "answer"}
    )
    assert not cli._is_answer_only_display_step(
        SimpleNamespace(sub_goal_name="navigate", strategy="navigate")
    )
    assert not cli._is_answer_only_display_step(
        {"sub_goal_name": "write", "strategy": "tool_call"}
    )


def test_both_vgg_display_callbacks_apply_the_answer_only_filter() -> None:
    source = inspect.getsource(cli.main)

    assert "_is_answer_only_display_step(step)" in source
    assert "_is_answer_only_display_step(view)" in source


def test_chat_footer_omits_context_already_visible_in_composer() -> None:
    footer = cli.render_chat_footer(in_tokens=0, out_tokens=0, wall_sec=2.4)

    assert "2.4s" in footer
    assert "route=" not in footer
    assert "model=" not in footer
