# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for build_decompose_vocab — single-sourced decompose vocabulary.

The arm is the touchstone: an arm-only agent (has_base=False) must get a vocab
whose strategies are exactly the ``<name>_skill`` set with NO base primitives,
and whose verify allowlist is exactly the verify-signature keys. A mobile robot
(has_base=True) additionally gets walk_forward/turn/scan_360.
"""

from __future__ import annotations

from vector_os_nano.vcli.cognitive.vocab_from_registry import build_decompose_vocab
from vector_os_nano.vcli.worlds.base import DecomposeVocab

# Arm-like skill registry (pick/place/scan/detect/home/wave), mirroring the
# shape of skill_registry.to_schemas().
_ARM_SCHEMAS = [
    {
        "name": "pick",
        "description": "Pick up an object with the arm. Gripper closes around it.",
        "parameters": {
            "object_label": {"type": "string", "required": True},
            "approach": {"type": "string", "required": False},
        },
    },
    {
        "name": "place",
        "description": "Place the held object at a target pose.",
        "parameters": {"target": {"type": "string", "required": True}},
    },
    {
        "name": "scan",
        "description": "Sweep the camera across the workspace.",
        "parameters": {},
    },
    {
        "name": "detect",
        "description": "Detect objects matching a query.",
        "parameters": {"query": {"type": "string", "required": False}},
    },
    {"name": "home", "description": "Return the arm to its home pose.", "parameters": {}},
    {"name": "wave", "description": "Wave the arm.", "parameters": {}},
]

_VERIFY_SIGS = {
    "detect_objects": "detect_objects(query='') -> list[dict]  # object detections",
    "gripper_holding": "gripper_holding() -> bool  # True if gripper holds an object",
    "arm_at_home": "arm_at_home() -> bool  # True if arm is at home pose",
}

_EXPECTED_SKILL_STRATEGIES = frozenset(
    {"pick_skill", "place_skill", "scan_skill", "detect_skill", "home_skill", "wave_skill"}
)

_BASE_PRIMITIVES = frozenset({"walk_forward", "turn", "scan_360"})


def test_returns_decompose_vocab() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    assert isinstance(vocab, DecomposeVocab)


def test_arm_strategies_are_exactly_skill_set_no_base() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    assert vocab.strategies == _EXPECTED_SKILL_STRATEGIES
    # No base primitives leak into an arm-only vocab.
    assert not (_BASE_PRIMITIVES & vocab.strategies)
    for prim in _BASE_PRIMITIVES:
        assert prim not in vocab.strategy_descriptions


def test_descriptions_derived_from_schemas() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    assert vocab.strategy_descriptions["pick_skill"] == _ARM_SCHEMAS[0]["description"]
    assert vocab.strategy_descriptions["wave_skill"] == "Wave the arm."
    assert set(vocab.strategy_descriptions.keys()) == _EXPECTED_SKILL_STRATEGIES


def test_params_help_derived_from_parameters() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    help_text = vocab.strategy_params_help
    # Every skill appears as a strategy entry.
    for strat in _EXPECTED_SKILL_STRATEGIES:
        assert strat in help_text
    # Param names + required/optional flags surface.
    assert "object_label" in help_text
    assert "required" in help_text
    assert "optional" in help_text
    # A no-param skill renders an explicit empty object.
    assert "- home_skill: {}" in help_text


def test_verify_functions_equal_signature_keys() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    assert vocab.verify_functions == frozenset(_VERIFY_SIGS.keys())
    assert vocab.verify_fn_signatures == _VERIFY_SIGS
    # verify_fn_signatures is a copy, not the caller's dict.
    assert vocab.verify_fn_signatures is not _VERIFY_SIGS


def test_has_base_adds_base_primitives() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=True)
    assert _BASE_PRIMITIVES <= vocab.strategies
    assert vocab.strategies == _EXPECTED_SKILL_STRATEGIES | _BASE_PRIMITIVES
    for prim in _BASE_PRIMITIVES:
        assert prim in vocab.strategy_descriptions


def test_examples_use_real_skills_and_verify_fn_no_go2() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    ex = vocab.examples
    assert ex  # non-empty
    # Uses a real registry skill strategy, not GO2 hardcoding.
    assert "pick_skill" in ex
    assert "navigate_skill" not in ex
    assert "去厨房" not in ex
    # Uses an actual verify function from the signatures (alphabetically first).
    assert "arm_at_home()" in ex


def test_default_planner_intro_is_neutral() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    assert "去厨房" not in vocab.planner_intro
    assert vocab.planner_intro  # non-empty default


def test_custom_planner_intro_passthrough() -> None:
    vocab = build_decompose_vocab(
        _ARM_SCHEMAS, _VERIFY_SIGS, has_base=False, planner_intro="CUSTOM INTRO"
    )
    assert vocab.planner_intro == "CUSTOM INTRO"


def test_fallback_verify_is_true_literal() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    assert vocab.fallback_verify == "True"


def test_empty_schemas_no_strategies_no_example() -> None:
    vocab = build_decompose_vocab([], _VERIFY_SIGS, has_base=False)
    assert vocab.strategies == frozenset()
    assert vocab.examples == ""
    # Verify allowlist still comes from signatures even with no skills.
    assert vocab.verify_functions == frozenset(_VERIFY_SIGS.keys())


def test_empty_schemas_with_base_keeps_base_primitives() -> None:
    vocab = build_decompose_vocab([], _VERIFY_SIGS, has_base=True)
    assert vocab.strategies == _BASE_PRIMITIVES


def test_as_kwargs_roundtrips() -> None:
    vocab = build_decompose_vocab(_ARM_SCHEMAS, _VERIFY_SIGS, has_base=False)
    kw = vocab.as_kwargs()
    assert kw["strategies"] == _EXPECTED_SKILL_STRATEGIES
    assert kw["verify_functions"] == frozenset(_VERIFY_SIGS.keys())
    assert kw["fallback_verify"] == "True"
