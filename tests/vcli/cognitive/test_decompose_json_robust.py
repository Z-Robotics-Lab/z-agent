# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Bug B — robust decompose JSON extraction for a REASONING model.

deepseek-v4-flash emits a hidden reasoning trace then the final ``content``; with a
too-small ``max_tokens`` the final JSON truncates, and the model habitually wraps the
JSON in code fences and/or surrounds it with reasoning preamble + trailing prose. The
old extractor (non-greedy fence regex + greedy ``{.*}``) silently dropped to a fallback
plan on any of these. These tests pin the hardened behaviour:

  - JSON wrapped in ```json``` fences (with prose before/after) parses.
  - JSON with a reasoning preamble AND trailing prose (incl. a stray ``{brace}`` in the
    prose) parses to the REAL plan — never over-captured.
  - A truncated / garbled response triggers a BOUNDED retry (one re-ask), then if still
    bad FAILS LOUD to the single-step fallback — never a phantom multi-step plan.
  - The decompose call uses a reasoning-model-sized token budget (configurable).
  - The validated plan SHAPE + validation are unchanged (a clean plan round-trips with
    no validation notes; an unknown strategy is still cleared loudly).

Hermetic: mock backend, no LLM, no mujoco.
"""
from __future__ import annotations

import json
from typing import Any

from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer
from zeno.vcli.cognitive.types import GoalTree


# ---------------------------------------------------------------------------
# Mock backends
# ---------------------------------------------------------------------------


class _MockBackend:
    """Returns a fixed response; records the max_tokens it was called with."""

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0
        self.last_max_tokens: int | None = None

    def call(self, messages, tools, system, max_tokens, on_text=None):
        self.calls += 1
        self.last_max_tokens = max_tokens
        self.last_messages = messages
        resp = self._response

        class _R:
            text = resp

        return _R()


class _SeqMockBackend:
    """Returns a sequence of responses across successive calls (then repeats last)."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.last_max_tokens: int | None = None
        self.seen_messages: list[Any] = []

    def call(self, messages, tools, system, max_tokens, on_text=None):
        self.last_max_tokens = max_tokens
        self.seen_messages.append(messages)
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1

        class _R:
            text = resp

        return _R()


# An arm-like vocab single-sourced via explicit strategy injection (no base).
_STRATEGIES = frozenset({"home_skill", "detect_skill", "pick_skill", "place_skill"})
_VERIFY_FNS = frozenset({"detect_objects", "holding_object", "arm_at_home"})


def _decomposer(backend: Any) -> GoalDecomposer:
    return GoalDecomposer(
        backend,
        strategies=_STRATEGIES,
        verify_functions=_VERIFY_FNS,
        fallback_verify="True",
        has_base=False,
    )


def _valid_plan() -> dict[str, Any]:
    return {
        "goal": "pick up the mug",
        "sub_goals": [
            {
                "name": "home_arm",
                "description": "home the arm",
                "verify": "arm_at_home()",
                "strategy": "home_skill",
                "depends_on": [],
                "strategy_params": {},
            },
            {
                "name": "grasp",
                "description": "pick up the mug",
                "verify": "holding_object()",
                "strategy": "pick_skill",
                "depends_on": ["home_arm"],
                "strategy_params": {"object_label": "mug"},
            },
        ],
        "context_snapshot": "",
    }


def _valid_plan_json() -> str:
    return json.dumps(_valid_plan())


# ---------------------------------------------------------------------------
# Token budget — reasoning model needs headroom so the FINAL JSON isn't truncated.
# ---------------------------------------------------------------------------


def test_decompose_uses_reasoning_sized_token_budget() -> None:
    backend = _MockBackend(_valid_plan_json())
    _decomposer(backend).decompose("pick up the mug", "scene")
    # Far above the old 2048 — leaves room for a reasoning trace + a full plan.
    assert backend.last_max_tokens is not None
    assert backend.last_max_tokens >= 4096
    assert backend.last_max_tokens == GoalDecomposer.DEFAULT_DECOMPOSE_MAX_TOKENS


def test_decompose_max_tokens_is_configurable() -> None:
    backend = _MockBackend(_valid_plan_json())
    d = GoalDecomposer(
        backend,
        strategies=_STRATEGIES,
        verify_functions=_VERIFY_FNS,
        fallback_verify="True",
        has_base=False,
        decompose_max_tokens=12345,
    )
    d.decompose("pick up the mug", "scene")
    assert backend.last_max_tokens == 12345


# ---------------------------------------------------------------------------
# Code fences — the model wraps JSON in ```json``` even when told not to.
# ---------------------------------------------------------------------------


def test_json_wrapped_in_code_fences_parses() -> None:
    fenced = (
        "Sure, here is the plan you asked for:\n"
        "```json\n" + _valid_plan_json() + "\n```\n"
        "Let me know if you need changes."
    )
    backend = _MockBackend(fenced)
    tree = _decomposer(backend).decompose("pick up the mug", "scene")
    assert isinstance(tree, GoalTree)
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]
    assert tree.validation_notes == ()
    assert backend.calls == 1  # parsed on the first try — no retry needed


def test_json_in_bare_fence_without_language_tag_parses() -> None:
    fenced = "```\n" + _valid_plan_json() + "\n```"
    tree = _decomposer(_MockBackend(fenced)).decompose("pick up the mug", "scene")
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]


# ---------------------------------------------------------------------------
# Reasoning preamble + trailing prose (incl. a stray brace) — the old greedy
# extractor over-captured and produced "Extra data" / "Expecting ','" failures.
# ---------------------------------------------------------------------------


def test_reasoning_preamble_and_trailing_prose_parses() -> None:
    noisy = (
        "Let me reason about this. The user wants the arm to grab the mug, so I "
        "should home first, then grasp. Here is the JSON:\n"
        + _valid_plan_json()
        + "\n\nNote: remember to keep the {gripper} clear afterwards."
    )
    backend = _MockBackend(noisy)
    tree = _decomposer(backend).decompose("pick up the mug", "scene")
    # The REAL plan was extracted (not over-captured into the trailing {gripper}).
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]
    assert tree.validation_notes == ()
    assert backend.calls == 1


def test_brace_inside_string_value_does_not_miscount() -> None:
    plan = _valid_plan()
    plan["goal"] = "open the {door} carefully"
    noisy = "Thinking... " + json.dumps(plan) + " done."
    tree = _decomposer(_MockBackend(noisy)).decompose("open the door", "scene")
    assert tree.goal == "open the {door} carefully"
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]


# ---------------------------------------------------------------------------
# Bounded retry — one re-ask on a parse miss, then fail loud to fallback.
# ---------------------------------------------------------------------------


def test_truncated_response_triggers_retry_then_succeeds() -> None:
    truncated = '{"goal": "pick up the mug", "sub_goals": [{"name": "home_arm",'
    backend = _SeqMockBackend([truncated, _valid_plan_json()])
    tree = _decomposer(backend).decompose("pick up the mug", "scene")
    # The re-ask recovered a real plan.
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]
    assert backend.calls == 2  # exactly one bounded retry
    # The retry message carried a JSON-only nudge (additive, not a new schema).
    retry_msgs = backend.seen_messages[1]
    last_user = retry_msgs[-1]["content"]
    assert "ONLY" in last_user and "JSON" in last_user


def test_total_failure_fails_loud_no_phantom_plan() -> None:
    # Garbage on BOTH the first call and the retry.
    backend = _SeqMockBackend(["I cannot help with that.", "Still no JSON here."])
    tree = _decomposer(backend).decompose("pick up the mug", "scene")
    assert backend.calls == 2  # original + one bounded retry, then give up
    # FAIL LOUD -> single-step fallback. NEVER a fabricated multi-step plan.
    assert len(tree.sub_goals) == 1
    assert tree.sub_goals[0].name == "execute_task"


def test_valid_first_response_does_not_retry() -> None:
    backend = _SeqMockBackend([_valid_plan_json(), "should-not-be-used"])
    tree = _decomposer(backend).decompose("pick up the mug", "scene")
    assert backend.calls == 1
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]


# ---------------------------------------------------------------------------
# Validation is unchanged — the hardened extractor does not weaken the gate.
# ---------------------------------------------------------------------------


def test_validation_still_clears_unknown_strategy_loudly() -> None:
    plan = _valid_plan()
    plan["sub_goals"][1]["strategy"] = "scan_to_look"  # hallucinated skill
    noisy = "```json\n" + json.dumps(plan) + "\n```"
    tree = _decomposer(_MockBackend(noisy)).decompose("pick up the mug", "scene")
    # Strategy cleared; fail-loud note surfaced (validation unchanged by extractor).
    assert tree.sub_goals[1].strategy == ""
    notes = "\n".join(tree.validation_notes)
    assert "scan_to_look" in notes and "not valid" in notes
    assert "pick_skill" in notes  # valid set surfaced
