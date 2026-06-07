# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""S4-4 — observation-driven mid-tree replan.

Today the VGGHarness re-decomposes only when a step FAILS (Layer 3 pipeline
retry on ``trace.success is False``). S4-4 adds a complementary trigger: even a
FULLY-VERIFIED run may observe live state the plan never assumed — e.g. a detect
step finds a different object set, or a post-pick re-detect changes the remaining
set. When an ``observation_divergence`` detector is wired and reports divergence,
the harness re-decomposes against the CURRENT world_context/Blackboard (not the
stale T=0 context) and re-executes — once, bounded by ``max_obs_replan``.

These tests pin (deterministic, no LLM, no MuJoCo):

  - With NO detector wired the run path is byte-identical (no extra decompose).
  - A detector that reports divergence on the FIRST verified run fires exactly one
    re-decompose against a FRESH context, then returns the re-executed trace.
  - The bound (``max_obs_replan``) caps re-decomposes — a detector that always
    reports divergence cannot loop forever.
  - The re-decompose context is FRESH (rebuilt via context_provider) and carries
    the divergence reason — never the stale T=0 string.
  - A detector that raises never aborts a verified run (fail-safe).
  - End-to-end: a real GoalExecutor + GoalVerifier where the live detect set
    differs from the plan's assumption flips the detector, the harness re-plans
    around the CURRENT observed set, and the second run verifies.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from vector_os_nano.vcli.cognitive.blackboard import Blackboard
from vector_os_nano.vcli.cognitive.goal_executor import GoalExecutor
from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier
from vector_os_nano.vcli.cognitive.strategy_selector import StrategyResult
from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from vector_os_nano.vcli.cognitive.vgg_harness import HarnessConfig, VGGHarness


# ---------------------------------------------------------------------------
# Helpers (mirror the Level-56 harness test doubles).
# ---------------------------------------------------------------------------


def _tree(name: str = "step_0") -> GoalTree:
    return GoalTree(
        goal="t", sub_goals=(SubGoal(name=name, description=name, verify="True"),)
    )


def _ok_step(name: str = "step_0", data: dict | None = None) -> StepRecord:
    return StepRecord(
        sub_goal_name=name,
        strategy="s",
        success=True,
        verify_result=True,
        duration_sec=0.01,
        result_data=data or {},
    )


def _verified_executor(step: StepRecord, tree: GoalTree) -> MagicMock:
    ex = MagicMock()
    ex._stats = None
    ex._topological_sort.return_value = list(tree.sub_goals)
    ex._execute_sub_goal.return_value = step
    return ex


# ---------------------------------------------------------------------------
# No detector -> byte-identical (no extra decompose, no extra execute).
# ---------------------------------------------------------------------------


def test_no_detector_means_no_obs_replan() -> None:
    tree = _tree()
    ex = _verified_executor(_ok_step(), tree)
    dec = MagicMock()
    dec.decompose.return_value = tree

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=1),
        # observation_divergence not supplied -> loop entirely skipped
    )
    trace = harness.run("t", "ctx")

    assert trace.success is True
    assert dec.decompose.call_count == 1  # no extra re-decompose
    assert ex._execute_sub_goal.call_count == 1  # no extra execute


# ---------------------------------------------------------------------------
# Divergence on the first verified run -> exactly one re-decompose + re-execute.
# ---------------------------------------------------------------------------


def test_divergence_fires_one_obs_replan() -> None:
    tree1, tree2 = _tree("a"), _tree("b")
    dec = MagicMock()
    dec.decompose.side_effect = [tree1, tree2]

    ex = MagicMock()
    ex._stats = None
    ex._topological_sort.side_effect = [list(tree1.sub_goals), list(tree2.sub_goals)]
    # First run: a verified step whose observation diverges; second run: clean.
    ex._execute_sub_goal.side_effect = [
        _ok_step("a", {"output": {"objects": ["mug", "EXTRA"]}}),
        _ok_step("b", {"output": {"objects": ["mug"]}}),
    ]

    seen: list[ExecutionTrace] = []

    def detector(trace: ExecutionTrace) -> str | None:
        seen.append(trace)
        # Diverge only on the first run (the one carrying the EXTRA object).
        objs = trace.steps[0].result_data.get("output", {}).get("objects", [])
        return "set changed" if "EXTRA" in objs else None

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=1, max_obs_replan=1),
        observation_divergence=detector,
    )
    trace = harness.run("t", "ctx")

    assert trace.success is True
    assert trace.steps[0].sub_goal_name == "b"  # returned the re-planned run
    assert dec.decompose.call_count == 2  # original + one obs replan
    assert ex._execute_sub_goal.call_count == 2  # both runs executed
    # The detector was consulted (on the first verified run, which diverged). The
    # budget (max_obs_replan=1) is then spent, so it is not consulted a 2nd time.
    assert len(seen) >= 1
    assert "EXTRA" in seen[0].steps[0].result_data["output"]["objects"]


# ---------------------------------------------------------------------------
# Bound: a detector that ALWAYS diverges still terminates (no infinite loop).
# ---------------------------------------------------------------------------


def test_obs_replan_is_bounded() -> None:
    tree = _tree()
    dec = MagicMock()
    dec.decompose.return_value = tree

    ex = MagicMock()
    ex._stats = None
    ex._topological_sort.return_value = list(tree.sub_goals)
    ex._execute_sub_goal.return_value = _ok_step()

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        # Allow up to 2 observation replans; detector always diverges.
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=0, max_obs_replan=2),
        observation_divergence=lambda _t: "always diverges",
    )
    trace = harness.run("t", "ctx")

    assert trace.success is True  # still returns a verified trace
    # original decompose + exactly max_obs_replan (2) re-decomposes = 3 total.
    assert dec.decompose.call_count == 3


def test_obs_replan_zero_budget_never_fires() -> None:
    tree = _tree()
    dec = MagicMock()
    dec.decompose.return_value = tree
    ex = _verified_executor(_ok_step(), tree)

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=0, max_obs_replan=0),
        observation_divergence=lambda _t: "would diverge but no budget",
    )
    trace = harness.run("t", "ctx")

    assert trace.success is True
    assert dec.decompose.call_count == 1  # budget 0 -> no obs replan


# ---------------------------------------------------------------------------
# The obs-replan re-decompose uses a FRESH context carrying the divergence reason.
# ---------------------------------------------------------------------------


def test_obs_replan_uses_fresh_context_with_reason() -> None:
    tree1, tree2 = _tree("a"), _tree("b")
    dec = MagicMock()
    dec.decompose.side_effect = [tree1, tree2]

    ex = MagicMock()
    ex._stats = None
    ex._topological_sort.side_effect = [list(tree1.sub_goals), list(tree2.sub_goals)]
    ex._execute_sub_goal.side_effect = [_ok_step("a"), _ok_step("b")]

    diverged = {"fired": False}

    def detector(_t: ExecutionTrace) -> str | None:
        if not diverged["fired"]:
            diverged["fired"] = True
            return "tray now has a NEW object"
        return None

    # context_provider returns the CURRENT (fresh) state, not the static arg.
    def context_provider() -> str:
        return "FRESH-LIVE-STATE"

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=0, max_obs_replan=1),
        observation_divergence=detector,
    )
    harness.run("t", "STALE-T0-CONTEXT", context_provider=context_provider)

    # The first decompose saw the fresh context (Stage 1b context_provider).
    first_ctx = dec.decompose.call_args_list[0][0][1]
    assert "FRESH-LIVE-STATE" in first_ctx
    # The obs-replan decompose ALSO rebuilt the fresh context and appended the
    # divergence reason — never the stale T=0 string.
    second_ctx = dec.decompose.call_args_list[1][0][1]
    assert "FRESH-LIVE-STATE" in second_ctx
    assert "STALE-T0-CONTEXT" not in second_ctx
    assert "tray now has a NEW object" in second_ctx
    assert "Observation diverged" in second_ctx


def test_obs_replan_fires_on_replan_callback() -> None:
    tree1, tree2 = _tree("a"), _tree("b")
    dec = MagicMock()
    dec.decompose.side_effect = [tree1, tree2]
    ex = MagicMock()
    ex._stats = None
    ex._topological_sort.side_effect = [list(tree1.sub_goals), list(tree2.sub_goals)]
    ex._execute_sub_goal.side_effect = [_ok_step("a"), _ok_step("b")]

    fired = {"n": 0}
    msgs: list[str] = []

    def detector(_t: ExecutionTrace) -> str | None:
        fired["n"] += 1
        return "obj set changed" if fired["n"] == 1 else None

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=0, max_obs_replan=1),
        on_replan=msgs.append,
        observation_divergence=detector,
    )
    harness.run("t", "ctx")

    assert any("observed divergence" in m for m in msgs)
    assert any("obj set changed" in m for m in msgs)


# ---------------------------------------------------------------------------
# Fail-safe: a detector that RAISES never aborts a verified run.
# ---------------------------------------------------------------------------


def test_detector_exception_keeps_verified_run() -> None:
    tree = _tree()
    dec = MagicMock()
    dec.decompose.return_value = tree
    ex = _verified_executor(_ok_step(), tree)

    def boom(_t: ExecutionTrace) -> str | None:
        raise RuntimeError("detector blew up")

    harness = VGGHarness(
        decomposer=dec,
        executor=ex,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=0, max_obs_replan=1),
        observation_divergence=boom,
    )
    trace = harness.run("t", "ctx")

    assert trace.success is True
    assert dec.decompose.call_count == 1  # detector error -> no replan


# ---------------------------------------------------------------------------
# End-to-end: a real executor/verifier where the LIVE detect set differs from
# the plan's assumption, the detector flips, and the re-plan verifies.
# ---------------------------------------------------------------------------


class _DirectSelector:
    def select(self, sub_goal: SubGoal) -> StrategyResult:
        return StrategyResult(
            "primitive", sub_goal.strategy, dict(sub_goal.strategy_params)
        )


def test_end_to_end_obs_replan_around_live_set() -> None:
    # Ground truth the live detect reads. The FIRST plan assumed only {mug};
    # the live world actually has {mug, can}. After the first verified pass the
    # detector sees the divergence and we re-plan around the CURRENT set.
    live_objects = ["mug", "can"]
    state: dict[str, Any] = {"detected": [], "picked": []}

    def detect(**_: Any) -> dict[str, Any]:
        state["detected"] = list(live_objects)
        return {"objects": list(live_objects), "count": len(live_objects)}

    def pick(object_label: str | None = None, **_: Any) -> dict[str, Any]:
        state["picked"].append(object_label)
        return {"picked": object_label}

    def noop(**_: Any) -> dict[str, Any]:
        # A pure-check step: it does nothing; its verify() decides success.
        return {"checked": True}

    primitives = {"detect": detect, "pick": pick, "noop": noop}
    namespace = {
        "detected": lambda: len(state["detected"]) > 0,
        # all-picked succeeds once every live object has been picked
        "all_picked": lambda: set(state["picked"]) >= set(live_objects),
        "picked": lambda label: label in state["picked"],
    }
    verifier = GoalVerifier(namespace)
    executor = GoalExecutor(
        strategy_selector=_DirectSelector(),
        verifier=verifier,
        primitives=primitives,
    )

    # Plan 1: a detect + a single pick of "mug" (assumes the stale set {mug}).
    # It verifies True deterministically but leaves "can" un-picked.
    plan1 = GoalTree(
        goal="grab everything",
        sub_goals=(
            SubGoal(name="detect", description="detect", verify="detected()",
                    strategy="detect"),
            SubGoal(name="pick_mug", description="pick mug", verify="picked('mug')",
                    strategy="pick", depends_on=("detect",),
                    strategy_params={"object_label": "mug"}),
        ),
    )
    # Plan 2 (re-plan): detect + pick BOTH live objects -> all_picked() verifies.
    plan2 = GoalTree(
        goal="grab everything",
        sub_goals=(
            SubGoal(name="detect", description="detect", verify="detected()",
                    strategy="detect"),
            SubGoal(name="pick_mug", description="pick mug", verify="picked('mug')",
                    strategy="pick", depends_on=("detect",),
                    strategy_params={"object_label": "mug"}),
            SubGoal(name="pick_can", description="pick can", verify="picked('can')",
                    strategy="pick", depends_on=("detect",),
                    strategy_params={"object_label": "can"}),
            SubGoal(name="done", description="all grabbed", verify="all_picked()",
                    strategy="noop", depends_on=("pick_mug", "pick_can")),
        ),
    )

    dec = MagicMock()
    dec.decompose.side_effect = [plan1, plan2]

    def detector(trace: ExecutionTrace) -> str | None:
        # PURE read over the verified trace: the live detect set vs what we picked.
        # Diverge when an object was detected but never picked this run.
        detected: list[str] = []
        for s in trace.steps:
            objs = s.result_data.get("output", {}).get("objects")
            if isinstance(objs, list):
                detected = [o for o in objs if isinstance(o, str)]
        unhandled = [o for o in detected if o not in state["picked"]]
        return f"detected {unhandled} were not handled" if unhandled else None

    harness = VGGHarness(
        decomposer=dec,
        executor=executor,
        config=HarnessConfig(max_step_retries=0, max_pipeline_retries=0, max_obs_replan=1),
        observation_divergence=detector,
    )
    trace = harness.run("grab everything", "tabletop")

    # The re-planned run verified end-to-end and grabbed the FULL live set.
    assert trace.success is True
    assert dec.decompose.call_count == 2  # original + obs replan
    assert set(state["picked"]) >= set(live_objects)
    # The returned trace is the re-plan (it contains the 'done' step).
    assert any(s.sub_goal_name == "done" for s in trace.steps)
