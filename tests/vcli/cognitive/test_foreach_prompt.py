# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""F-1 — the live decomposer prompt TEACHES the foreach loop JSON.

S4-1 made the decomposer PARSE + VALIDATE a foreach node, but the system prompt
the LLM reads never documented the loop shape, so a real model could not emit one
(foreach was only ever proven with a hand-written / mock plan). F-1 closes that
gap: the rendered schema + a world-neutral worked example now document the loop.

These tests pin:
  - The rendered system prompt documents the foreach node — the key fields
    (source_step / source_path / var / body) AND the per-item "${var.field}"
    reference form the executor resolves by safe path lookup.
  - The loop documentation is world-NEUTRAL: it stays present on an arm-only world
    whose own example is overridden, and never leaks go2 base vocabulary.
  - A mock backend returning a foreach plan still validates + round-trips (the
    documentation change did not break parsing).

Hermetic: mock backend, no LLM, no mujoco. An opt-in live-LLM smoke is deselected
by default.
"""
from __future__ import annotations

import json
import os
from typing import Any

import pytest

from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer
from zeno.vcli.cognitive.vocab_from_registry import build_decompose_vocab


# ---------------------------------------------------------------------------
# Mock backend — returns a fixed JSON plan string.
# ---------------------------------------------------------------------------


class _MockBackend:
    def __init__(self, response: str = "{}") -> None:
        self._response = response

    def call(self, messages, tools, system, max_tokens, on_text=None):  # noqa: ANN001
        resp = self._response

        class _R:
            text = resp

        return _R()


# Arm-like vocab (no base), single-sourced through the SAME vocab builder the
# real arm world uses — so its WHOLE prompt (strategies, params-help, example) is
# arm-only. The loop docs must survive this world and never leak go2 base vocab.
_ARM_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "detect",
        "description": "Detect objects matching a query.",
        "parameters": {"query": {"type": "string", "required": False}},
    },
    {
        "name": "pick",
        "description": "Pick up an object with the arm gripper.",
        "parameters": {"object_label": {"type": "string", "required": True}},
    },
    {
        "name": "place",
        "description": "Place the held object at a target pose.",
        "parameters": {"target": {"type": "string", "required": True}},
    },
]
_ARM_VERIFY_SIGS = {
    "detect_objects": "detect_objects(query='') -> list[dict]  # object detections",
    "holding_object": "holding_object() -> bool  # True if the gripper holds an object",
    "placed_count": "placed_count() -> int  # objects resting in the tray",
}
_ARM_STRATEGIES = frozenset({"detect_skill", "pick_skill", "place_skill"})
_ARM_VERIFY_FNS = frozenset(_ARM_VERIFY_SIGS.keys())

_GO2_FORBIDDEN = ("navigate_skill", "look_skill", "explore_skill", "scan_360",
                  "去厨房", "nearest_room")


def _robot_decomposer(response: str = "{}") -> GoalDecomposer:
    """Default (robot-world) decomposer — uses the class-default vocab."""
    return GoalDecomposer(_MockBackend(response))


def _arm_decomposer(response: str = "{}") -> GoalDecomposer:
    """Arm-only decomposer with the FULL arm vocab single-sourced from schemas."""
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _ARM_VERIFY_SIGS, has_base=False)
    return GoalDecomposer(
        _MockBackend(response),
        has_base=False,
        **vocab.as_kwargs(),
    )


def _foreach_plan() -> dict[str, Any]:
    """detect_all -> foreach(obj in detected): pick(obj)."""
    return {
        "goal": "pick up every object",
        "sub_goals": [
            {
                "name": "detect_all",
                "description": "detect every object",
                "verify": "len(detect_objects()) > 0",
                "strategy": "detect_skill",
                "depends_on": [],
                "strategy_params": {},
            },
            {
                "name": "pick_each",
                "description": "pick up each detected object, one by one",
                "verify": "True",
                "strategy": "",
                "depends_on": ["detect_all"],
                "strategy_params": {},
                "foreach": {
                    "source_step": "detect_all",
                    "source_path": "objects",
                    "var": "obj",
                    "body": [
                        {
                            "name": "grasp_one",
                            "description": "pick up the current object",
                            "verify": "holding_object()",
                            "strategy": "pick_skill",
                            "depends_on": [],
                            "strategy_params": {"object_label": "${obj.name}"},
                        }
                    ],
                },
            },
        ],
        "context_snapshot": "",
    }


# ---------------------------------------------------------------------------
# The prompt documents the foreach loop shape.
# ---------------------------------------------------------------------------


def test_prompt_documents_foreach_node() -> None:
    text = _robot_decomposer()._build_system_prompt()[0]["text"]

    # The loop block and its key fields are taught.
    assert "foreach" in text
    for field in ("source_step", "source_path", "var", "body"):
        assert field in text, f"foreach prompt missing field {field!r}"

    # The per-item reference form the executor resolves by safe path lookup.
    assert "${item.name}" in text
    # And it is explicitly described as a non-eval, path-lookup binding.
    assert "${" in text and "eval" in text.lower()

    # A worked loop example actually appears (a detect -> foreach(act) plan).
    assert "## Loop Example" in text


def test_foreach_docs_are_world_neutral_on_arm() -> None:
    # An arm-only world whose ``_EXAMPLE`` is overridden STILL teaches the loop —
    # the foreach documentation is shared, not part of the per-world example.
    text = _arm_decomposer()._build_system_prompt()[0]["text"]

    assert "foreach" in text
    assert "source_step" in text
    assert "${item.name}" in text
    # Its own generated arm example is present (the robot default is NOT).
    assert "detect_skill" in text
    assert "pick_skill" in text
    # No go2 base vocabulary leaked via the new loop docs.
    for banned in _GO2_FORBIDDEN:
        assert banned not in text, f"loop docs leaked go2 vocab: {banned!r}"


# ---------------------------------------------------------------------------
# The documentation change did not break parsing: a mock foreach plan validates.
# ---------------------------------------------------------------------------


def test_mock_foreach_plan_still_validates_after_prompt_change() -> None:
    decomposer = _arm_decomposer(json.dumps(_foreach_plan()))
    tree = decomposer.decompose("pick up every object", "tabletop scene")

    assert [sg.name for sg in tree.sub_goals] == ["detect_all", "pick_each"]
    # A clean plan generates no validator complaints.
    assert tree.validation_notes == ()

    loop = tree.sub_goals[1]
    assert loop.foreach is not None
    assert loop.foreach.source_step == "detect_all"
    assert loop.foreach.source_path == "objects"
    assert loop.foreach.var == "obj"
    # The loop auto-depends on its producer (H-1b), even though the body and
    # binding survive AS DATA — the per-item ref is never evaluated at decompose.
    assert "detect_all" in loop.depends_on
    assert [t.strategy for t in loop.foreach.body] == ["pick_skill"]
    assert loop.foreach.body[0].strategy_params["object_label"] == "${obj.name}"


# ---------------------------------------------------------------------------
# R2-3 — Singular-vs-ALL guidance is present and foreach docs are intact.
# ---------------------------------------------------------------------------


def test_singular_guidance_in_prompt() -> None:
    """R2-3 Part A: the rendered prompt teaches singular-vs-ALL intent.

    The guidance must appear in the text the LLM reads (the system prompt), so
    a singular-grab task is NOT mapped to a foreach loop.  We check for key
    phrases that are meaningful to the LLM but do NOT constitute a keyword
    table in code — the text lives entirely inside a prompt string (the LLM
    layer), not in any branching logic.
    """
    text = _robot_decomposer()._build_system_prompt()[0]["text"]

    # The singular-vs-ALL guidance block must be present.
    assert "Singular vs. ALL" in text or "SINGULAR" in text.upper(), (
        "singular-vs-ALL guidance missing from prompt"
    )
    # The guidance must distinguish ALL/EACH from a single unspecified item.
    assert "foreach" in text                    # loop construct still taught
    assert "NO foreach" in text or "no foreach" in text.lower(), (
        "prompt must say NO foreach for singular intent"
    )
    # Object target left blank for singular — skill resolves nearest.
    assert "blank" in text.lower() or "BLANK" in text, (
        "prompt must instruct leaving target blank for singular intent"
    )


def test_singular_guidance_present_on_arm_decomposer() -> None:
    """The singular guidance is world-neutral — it survives an arm-only world."""
    text = _arm_decomposer()._build_system_prompt()[0]["text"]
    assert "NO foreach" in text or "no foreach" in text.lower(), (
        "singular guidance must be present on arm decomposer too"
    )
    # Foreach docs must still be there (guidance adds to, not replaces, foreach).
    assert "source_step" in text
    assert "${item.name}" in text


def test_foreach_docs_still_intact_after_singular_guidance() -> None:
    """Adding singular guidance must not disturb the existing foreach docs."""
    text = _robot_decomposer()._build_system_prompt()[0]["text"]
    # All original foreach fields must remain.
    for field in ("source_step", "source_path", "var", "body"):
        assert field in text, f"foreach field {field!r} missing after singular guidance"
    assert "${item.name}" in text
    assert "## Loop Example" in text


# ---------------------------------------------------------------------------
# Optional live-LLM smoke (deselected from the canonical gate).
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("VECTOR_LIVE_LLM") != "1",
    reason="live-LLM smoke: set VECTOR_LIVE_LLM=1 to run (deselected by default)",
)
def test_prompt_teaches_foreach_live_llm_smoke() -> None:  # pragma: no cover - opt-in
    """Smoke: with the foreach-teaching prompt, a live backend CAN emit a loop.

    Opt-in only. Asserts on STRUCTURE (a foreach loop emerges), never on exact
    wording. Skipped by default so the canonical suite stays hermetic and free.
    The key comes from VECTOR_LLM_API_KEY (never hardcoded).
    """
    from zeno.vcli.backends import create_backend

    api_key = os.environ.get("VECTOR_LLM_API_KEY")
    if not api_key:
        pytest.skip("live-LLM smoke needs VECTOR_LLM_API_KEY")
    backend = create_backend(
        provider=os.environ.get("VECTOR_LLM_PROVIDER", "openrouter"),
        api_key=api_key,
        model=os.environ.get("VECTOR_LLM_MODEL", "google/gemini-2.5-flash"),
    )
    decomposer = GoalDecomposer(
        backend,
        strategies=_ARM_STRATEGIES,
        verify_functions=_ARM_VERIFY_FNS,
        fallback_verify="True",
        has_base=False,
    )
    tree = decomposer.decompose(
        "pick up every object on the table, one by one",
        "tabletop scene with several objects",
    )
    assert any(sg.foreach is not None for sg in tree.sub_goals)
