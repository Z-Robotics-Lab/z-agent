# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Conversational input must NOT be mis-routed into VGG planning.

Regression for a live bug: "为什么一开始那么卡" (a why-question) was routed to the
VGG planner and decomposed into a measure-startup plan, because the action verb
"开始" (start) matched as a substring of the adverb "一开始" (at first). Questions
and greetings should answer directly via the tool_use path; only genuine
multi-step / action commands go to VGG.
"""
from __future__ import annotations

import pytest

from vector_os_nano.vcli.intent_router import IntentRouter


@pytest.fixture
def router() -> IntentRouter:
    return IntentRouter()


@pytest.mark.parametrize(
    "msg",
    [
        "为什么一开始那么卡",   # the reported bug: why-question with 开始 inside 一开始
        "为什么这么慢",
        "这是怎么回事",
        "如何使用",
        "是什么意思",
        "how does this work?",
        "why is it slow",
        "what can you do",
        "hello",
        "你好",
        "能做什么",
    ],
)
def test_questions_and_greetings_do_not_route_to_vgg(router, msg):
    assert router.should_use_vgg(msg) is False


@pytest.mark.parametrize(
    "msg",
    [
        "把所有东西抓一遍",        # scope -> complex
        "开始巡逻然后回家",        # multi-step command
        "navigate to the kitchen",
        "先扫描再抓取",            # sequential
    ],
)
def test_real_commands_still_route_to_vgg(router, msg):
    assert router.should_use_vgg(msg) is True


def test_action_substring_in_adverb_is_not_a_command(router):
    # The crux: "开始" as a substring of "一开始" must not trigger planning when the
    # message is plainly a question.
    assert router.should_use_vgg("为什么一开始那么卡") is False
    # But a real "开始 <action>" command still plans.
    assert router.should_use_vgg("开始巡逻然后回家") is True
