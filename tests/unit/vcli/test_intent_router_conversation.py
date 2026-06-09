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


# ---------------------------------------------------------------------------
# Meta / first-person-request input (bug A): "我希望你去打开终端" is a meta request
# ABOUT the agent's own actions, not a robot-actionable command. It only trips the
# action-verb hint via "去"/"打开" as substrings, so it was forced into a VGG
# decompose that fails (no skill maps) → 'unmatched'. It must ANSWER instead.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "msg",
    [
        "我希望你去打开终端",       # the reported bug: meta request, 去/打开 incidental
        "我想让你帮我看看这段代码",  # first-person directive at the agent
        "请你打开浏览器",           # polite directive, no robot skill
        "你能不能快一点",           # meta ask about the agent's behaviour
        "I want you to open a terminal",
        "please open the terminal",
        "今天天气不错",             # bare statement, no action
    ],
)
def test_meta_requests_do_not_route_to_vgg(router, msg):
    # No skill registry → the meta guard redirects otherwise-unmappable meta input
    # to the answer path instead of a failing decompose.
    assert router.should_use_vgg(msg) is False


@pytest.mark.parametrize(
    "msg",
    [
        # The exact regressed class: a polite / first-person REAL motor command with
        # NO registry. SkillRegistry.match is PREFIX-only, so a polite prefix
        # ("请你"/"我希望你"/"please ") defeats startswith and these do NOT skill-match —
        # the meta-request guard must NOT suppress them. They carry a genuine motor
        # signal in the marker residual and must still PLAN.
        "请你巡逻",
        "please patrol",
        "我希望你巡逻",
        "请你去客厅",
        "I want you to go to the kitchen",
        "请你导航到厨房",
        "我希望你去厨房",
    ],
)
def test_meta_phrased_real_motor_command_still_plans(router, msg):
    # No registry: the residual-motor check (not a skill match) keeps the politely
    # phrased motor command on the planning path. This is the live-regressed case.
    assert router.should_use_vgg(msg) is True


def test_meta_phrased_real_command_still_plans_with_skill_match(router):
    """A genuine command phrased as a request still plans when a skill matches.

    The skill-match check runs BEFORE the meta guard, so a request-phrased command
    that the registry can map routes to VGG. This uses a PREFIX-matching fake that
    mirrors the real SkillRegistry.match contract (exact-or-startswith), not a
    substring match — so it does not over-claim production behaviour.
    """

    class _PrefixNavRegistry:
        # Mirrors SkillRegistry.match: exact-or-prefix (startswith) only.
        _aliases = ("去厨房", "navigate to the kitchen")

        def match(self, msg):  # noqa: ANN001
            low = msg.strip().lower()
            for alias in self._aliases:
                if low == alias or low.startswith(alias):
                    class _M:
                        skill_name = "navigate"

                    return _M()
            return None

    # Bare command (no polite prefix) prefix-matches the skill → plans via skill match.
    assert router.should_use_vgg("去厨房看看", skill_registry=_PrefixNavRegistry()) is True
    # A meta request the registry cannot map → answer path (no motor residual).
    assert router.should_use_vgg("我希望你去打开终端", skill_registry=_PrefixNavRegistry()) is False


def test_action_substring_in_adverb_is_not_a_command(router):
    # The crux: "开始" as a substring of "一开始" must not trigger planning when the
    # message is plainly a question.
    assert router.should_use_vgg("为什么一开始那么卡") is False
    # But a real "开始 <action>" command still plans.
    assert router.should_use_vgg("开始巡逻然后回家") is True
