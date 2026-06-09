# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""S4-1 — FOREACH control-flow IR: model + decompose parse/validation.

Stage 4 adds an OPTIONAL ``foreach`` control-flow spec to ``SubGoal`` (a new field
LAST, default None) so a loop node can iterate the list produced by an earlier
step. S4-1 only MODELS + PARSES + VALIDATES the spec — execution-time expansion is
S4-2. These tests pin:

  - Additive safety: constructing a SubGoal WITHOUT foreach still works (positional
    AND keyword), and a no-foreach plan round-trips byte-identically through the
    decomposer (foreach stays None).
  - A GoalTree carrying a foreach node round-trips through decompose parse +
    validation: the new field is populated, body templates survive, and the
    per-item ``${var.field}`` binding is preserved AS DATA (never evaluated).
  - Body strategies are validated against the SAME world vocab: an unknown body
    strategy is cleared with a fail-loud validation note; an unknown
    ``source_step`` drops the whole foreach with a note.

Hermetic: mock backend, no LLM, no mujoco.
"""
from __future__ import annotations

import json
from typing import Any

from vector_os_nano.vcli.cognitive.goal_decomposer import GoalDecomposer
from vector_os_nano.vcli.cognitive.types import ForEachSpec, GoalTree, SubGoal


# ---------------------------------------------------------------------------
# Mock backend — returns a fixed JSON plan string.
# ---------------------------------------------------------------------------


class _MockBackend:
    def __init__(self, response: str) -> None:
        self._response = response

    def call(self, messages, tools, system, max_tokens, on_text=None):
        resp = self._response

        class _R:
            text = resp

        return _R()


# An arm-like vocab single-sourced via explicit strategy injection (no base).
_STRATEGIES = frozenset({"home_skill", "detect_skill", "pick_skill", "place_skill"})
_VERIFY_FNS = frozenset({"detect_objects", "holding_object", "placed_count", "arm_at_home"})


def _decomposer(response: str) -> GoalDecomposer:
    return GoalDecomposer(
        _MockBackend(response),
        strategies=_STRATEGIES,
        verify_functions=_VERIFY_FNS,
        fallback_verify="True",
        has_base=False,
    )


# A plan whose final step is a FOREACH loop: detect all mugs, then pick each one.
# The body's per-item binding references ``${obj.name}`` — pure path data, no eval.
def _foreach_plan() -> dict[str, Any]:
    return {
        "goal": "pick up every mug",
        "sub_goals": [
            {
                "name": "detect_all",
                "description": "detect every mug on the table",
                "verify": "len(detect_objects('mug')) > 0",
                "strategy": "detect_skill",
                "depends_on": [],
                "strategy_params": {"query": "mug"},
            },
            {
                "name": "pick_each",
                "description": "pick up each detected mug",
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
                            "description": "pick up the current mug",
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


# A no-foreach plan (must be byte-unaffected: every foreach stays None).
def _plain_plan() -> dict[str, Any]:
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


# ---------------------------------------------------------------------------
# Additive safety — the new field never breaks existing construction.
# ---------------------------------------------------------------------------


def test_subgoal_without_foreach_still_constructs_positionally() -> None:
    # Full positional construction (the pre-S4-1 constructor) is unaffected.
    sg = SubGoal(
        "grasp",
        "pick up the mug",
        "holding_object()",
        30.0,
        ("home_arm",),
        "pick_skill",
        {"object_label": "mug"},
        "",
    )
    assert sg.foreach is None
    # Minimal keyword construction also leaves foreach defaulted to None.
    sg2 = SubGoal(name="x", description="d", verify="True")
    assert sg2.foreach is None


def test_subgoal_accepts_explicit_foreach_spec() -> None:
    spec = ForEachSpec(source_step="detect_all", source_path="objects", var="obj")
    sg = SubGoal(name="loop", description="d", verify="True", foreach=spec)
    assert sg.foreach is spec
    assert sg.foreach.var == "obj"
    assert sg.foreach.body == ()  # default empty body


def test_foreachspec_is_frozen() -> None:
    spec = ForEachSpec(source_step="s", source_path="objects")
    try:
        spec.var = "nope"  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("ForEachSpec must be frozen (immutable)")
    assert spec.var == "item"  # default


# ---------------------------------------------------------------------------
# No-foreach plans are byte-unaffected.
# ---------------------------------------------------------------------------


def test_plain_plan_roundtrips_with_no_foreach() -> None:
    tree = _decomposer(json.dumps(_plain_plan())).decompose("pick up the mug", "scene")
    assert tree.validation_notes == ()
    assert [sg.name for sg in tree.sub_goals] == ["home_arm", "grasp"]
    # Every step is a plain leaf — foreach untouched (None).
    assert all(sg.foreach is None for sg in tree.sub_goals)


# ---------------------------------------------------------------------------
# A foreach node round-trips through decompose parse + validation.
# ---------------------------------------------------------------------------


def test_foreach_node_parses_and_validates() -> None:
    tree = _decomposer(json.dumps(_foreach_plan())).decompose("pick up every mug", "scene")
    assert isinstance(tree, GoalTree)
    assert [sg.name for sg in tree.sub_goals] == ["detect_all", "pick_each"]

    detect, loop = tree.sub_goals
    # The detect step is a plain leaf.
    assert detect.foreach is None
    assert detect.strategy == "detect_skill"

    # The loop step carries a populated ForEachSpec.
    spec = loop.foreach
    assert isinstance(spec, ForEachSpec)
    assert spec.source_step == "detect_all"
    assert spec.source_path == "objects"
    assert spec.var == "obj"

    # Body template survived validation; its strategy is a real arm skill.
    assert len(spec.body) == 1
    body = spec.body[0]
    assert isinstance(body, SubGoal)
    assert body.name == "grasp_one"
    assert body.strategy == "pick_skill"
    assert body.verify == "holding_object()"

    # The per-item binding is preserved AS DATA — never evaluated/formatted.
    assert body.strategy_params["object_label"] == "${obj.name}"

    # A valid foreach generates no validation notes.
    assert tree.validation_notes == ()


def test_foreach_unknown_body_strategy_cleared_with_failloud_note() -> None:
    plan = _foreach_plan()
    # Hallucinate a go2-only strategy inside the loop body.
    plan["sub_goals"][1]["foreach"]["body"][0]["strategy"] = "explore_skill"

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")
    spec = tree.sub_goals[1].foreach
    assert isinstance(spec, ForEachSpec)
    # The unknown body strategy is cleared (same rule as a top-level step).
    assert spec.body[0].strategy == ""
    # Fail-loud feedback names the offender + the valid set.
    notes = "\n".join(tree.validation_notes)
    assert any("explore_skill" in n and "not valid" in n for n in tree.validation_notes)
    assert "pick_skill" in notes  # valid set surfaced


def test_foreach_unknown_source_step_drops_loop_with_note() -> None:
    plan = _foreach_plan()
    plan["sub_goals"][1]["foreach"]["source_step"] = "no_such_step"

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")
    # The owning sub_goal SURVIVES as a plain step; only the foreach is dropped.
    loop = tree.sub_goals[1]
    assert loop.name == "pick_each"
    assert loop.foreach is None
    notes = "\n".join(tree.validation_notes)
    assert "no_such_step" in notes
    assert "not a known step" in notes


def test_foreach_malformed_block_is_ignored() -> None:
    plan = _foreach_plan()
    # foreach missing required source_path.
    plan["sub_goals"][1]["foreach"] = {"source_step": "detect_all", "var": "obj"}

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")
    assert tree.sub_goals[1].foreach is None
    assert any("foreach requires" in n for n in tree.validation_notes)


def test_foreach_non_object_is_ignored() -> None:
    plan = _foreach_plan()
    plan["sub_goals"][1]["foreach"] = "not-an-object"

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")
    assert tree.sub_goals[1].foreach is None
    assert any("foreach must be an object" in n for n in tree.validation_notes)


# ---------------------------------------------------------------------------
# H-1b — a foreach without depends_on must not be orderable before its producer.
#
# REAL BUG: the topological sort orders nodes by depends_on. A foreach node whose
# author omitted depends_on could be placed BEFORE its producing step, so the
# producer's list was not yet on the blackboard and the loop iterated ZERO times
# while the run still reported success. Fix: the decomposer auto-injects the
# foreach's source_step into depends_on. These tests pin the injection (and that a
# plan already listing it is unchanged), plus that the loop then iterates N (not 0)
# even with the producer authored AFTER the loop in the source list.
# ---------------------------------------------------------------------------


def test_foreach_missing_depends_on_gets_source_step_injected() -> None:
    plan = _foreach_plan()
    # Author OMITS the ordering edge entirely.
    plan["sub_goals"][1]["depends_on"] = []

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")
    loop = tree.sub_goals[1]
    assert loop.foreach is not None
    # source_step was injected so the loop can never precede its producer.
    assert "detect_all" in loop.depends_on


def test_foreach_existing_depends_on_unchanged() -> None:
    plan = _foreach_plan()
    # Author already lists the producer (the canonical plan does).
    plan["sub_goals"][1]["depends_on"] = ["detect_all"]

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")
    loop = tree.sub_goals[1]
    assert loop.foreach is not None
    # No duplicate injection — the edge appears exactly once.
    assert loop.depends_on == ("detect_all",)


def test_foreach_without_depends_on_iterates_n_not_zero() -> None:
    """End-to-end: even with the producer authored AFTER the loop AND no
    depends_on, the injected edge forces the producer to run first, so the loop
    iterates the real N. Without the fix the loop would precede detect and run 0x.
    """
    from vector_os_nano.vcli.cognitive.blackboard import Blackboard
    from vector_os_nano.vcli.cognitive.goal_executor import GoalExecutor
    from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier
    from vector_os_nano.vcli.cognitive.strategy_selector import StrategyResult

    plan = _foreach_plan()
    plan["sub_goals"][1]["depends_on"] = []  # omit ordering edge
    # Author the loop BEFORE its producer in the source list, so without the
    # injected edge the topo-sort would run the loop first (zero iterations).
    plan["sub_goals"] = [plan["sub_goals"][1], plan["sub_goals"][0]]

    tree = _decomposer(json.dumps(plan)).decompose("pick up every mug", "scene")

    objects = [{"name": "mug"}, {"name": "cup"}, {"name": "bowl"}]
    state: dict[str, Any] = {"picked": []}

    def detect_skill(**_: Any) -> dict[str, Any]:
        return {"objects": list(objects), "count": len(objects)}

    def pick_skill(object_label: str | None = None, **_: Any) -> dict[str, Any]:
        state["picked"].append(object_label)
        return {"picked": object_label}

    class _SkillSelector:
        def select(self, sub_goal: Any) -> StrategyResult:
            return StrategyResult(
                "primitive", sub_goal.strategy, dict(sub_goal.strategy_params)
            )

    namespace = {
        "detect_objects": lambda *a, **k: list(objects),
        "holding_object": lambda *a, **k: bool(state["picked"]),
    }
    executor = GoalExecutor(
        strategy_selector=_SkillSelector(),
        verifier=GoalVerifier(namespace),
        primitives={"detect_skill": detect_skill, "pick_skill": pick_skill},
    )
    executor.blackboard = Blackboard()

    trace = executor.execute(tree)

    assert trace.success is True
    # The loop iterated the real N (not zero) because detect ran first.
    grasp_steps = [s for s in trace.steps if ".grasp_one" in s.sub_goal_name]
    assert len(grasp_steps) == len(objects)
    assert state["picked"] == ["mug", "cup", "bowl"]
