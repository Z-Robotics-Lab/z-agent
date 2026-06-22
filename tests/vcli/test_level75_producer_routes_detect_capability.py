# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 75 — R36: the PRODUCER routes a ``detect`` sub-goal to the grounding-dino
capability via the engine's capability-dispatch path, and the composed
``detect -> perception_grasp`` plan keeps its routed shape.

The campaign-long claim "the RUNTIME routes each instruction to the right MODEL"
is only fully proven when the PRODUCER/executor routes a sub-goal to a registered
capability via the engine's capability branch — NOT when the detector is invoked
SKILL-INTERNALLY (D48: grounding-dino ran inside ``perception_grasp``). These
tests prove the orchestration-LAYER route end-to-end:

  - a producer-emitted ``strategy="detect"`` sub-goal, run through the REAL
    GoalExecutor (via VGGHarness — the same path ``vgg_execute`` drives), resolves
    to ``executor_type="capability"``, INVOKES the registered DetectorCapability,
    and the detector's BOXES are captured in the StepRecord.result_data AND on the
    run Blackboard (so a later ``${detect.output.boxes}`` binding could consume
    them — closing the loop, rule 4);
  - the composed two-step plan ``detect (capability) -> perception_grasp (skill)``
    keeps the routed shape: step 0 -> capability, step 1 -> skill.

Pure kernel logic — a FAKE detector (no torch, no GPU, no mujoco). The capability
dispatch, blackboard capture, and verify spine are all REAL; only the model
weights are stand-in (the real-weights + real-sim acceptance is the bare-cli
probe, recorded separately). Spine ``vcli/cognitive/`` is byte-unchanged.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from vector_os_nano.perception.detector_capability import DetectorCapability
from vector_os_nano.vcli.cognitive.capabilities import CapabilityRegistry
from vector_os_nano.vcli.cognitive.goal_executor import GoalExecutor
from vector_os_nano.vcli.cognitive.strategy_selector import StrategySelector
from vector_os_nano.vcli.cognitive.types import GoalTree, SubGoal
from vector_os_nano.vcli.cognitive.vgg_harness import HarnessConfig, VGGHarness


# ---------------------------------------------------------------------------
# A fake open-vocab detector — same contract GroundingDinoDetector exposes
# (``.detect(rgb, query) -> [Detection]``), so DetectorCapability wraps it
# UNCHANGED. No torch, no weights, no GPU.
# ---------------------------------------------------------------------------


class _FakeDetection:
    def __init__(self, bbox, label, confidence):
        self.bbox = bbox
        self.label = label
        self.confidence = confidence

    def to_dict(self) -> dict:
        return {"bbox": list(self.bbox), "label": self.label, "confidence": self.confidence}


class _FakeDetector:
    """Deterministic stand-in for GroundingDinoDetector — one box per call."""

    def __init__(self):
        self.calls: list[tuple[Any, str]] = []

    def detect(self, rgb, query):
        self.calls.append((rgb, query))
        # one plausible box for "the green bottle"
        return [_FakeDetection((100.0, 80.0, 160.0, 200.0), "green bottle", 0.91)]


class _FakeContextRGB:
    """SkillContext-ish object exposing get_color_frame() (DetectorCapability
    pulls the RGB from the context when the payload omits a raw ``rgb``)."""

    def get_color_frame(self):
        import numpy as np

        return np.zeros((240, 320, 3), dtype=np.uint8)


def _real_detect_capability() -> tuple[DetectorCapability, _FakeDetector]:
    det = _FakeDetector()
    return DetectorCapability(detector=det), det


def _detect_subgoal() -> SubGoal:
    # The producer emits an EXPLICIT capability strategy. verify is the honest
    # RAN-grading predicate the registry vocab teaches for a detect step:
    # len(detect_objects()) > 0 — it grades that detection HAPPENED, not causation.
    return SubGoal(
        name="detect_bottle",
        description="detect the green bottle",
        verify="len(detect_objects()) > 0",
        strategy="detect",
        strategy_params={"query": "the green bottle"},
    )


# ---------------------------------------------------------------------------
# 1) Producer routing: detect -> capability -> real DetectorCapability.invoke,
#    boxes captured. The MECHANISM (selector + executor) is real.
# ---------------------------------------------------------------------------


def test_selector_routes_producer_detect_to_capability() -> None:
    """An explicit producer ``strategy='detect'`` resolves to the capability branch
    (not a skill) once 'detect' is a registered capability name."""
    sel = StrategySelector(capability_names={"detect"})
    r = sel.select(_detect_subgoal())
    assert (r.executor_type, r.name) == ("capability", "detect")
    # the producer's params (the NL target) flow through untouched
    assert r.params == {"query": "the green bottle"}


def test_producer_empty_strategy_detect_keyword_routes_to_capability() -> None:
    """The PRODUCER-REALISTIC route, with NO cognitive/ edit.

    The decompose vocab teaches the decomposer ``<skill>_skill`` strategies +
    base primitives — NOT capability names — so a plan that names ``detect``
    EXPLICITLY would be cleared by the decomposer validator (not in
    KNOWN_STRATEGIES) and routed ``invalid``. The clean producer route is an
    EMPTY strategy + a detect-keyword description: the decomposer leaves an empty
    strategy untouched, and the StrategySelector's keyword ladder (Priority 2)
    routes a 'detect'/'检测' description to the registered capability via
    ``_route('detect', ...)``. This is how the producer reaches the capability
    branch without touching the frozen vocab/selector seam."""
    sel = StrategySelector(capability_names={"detect"}, has_base=True)
    sg = SubGoal(
        name="detect_bottle",
        description="detect the green bottle",
        verify="len(detect_objects()) > 0",
        strategy="",  # producer leaves it empty; the keyword ladder routes it
    )
    r = sel.select(sg)
    assert (r.executor_type, r.name) == ("capability", "detect")
    # the NL target is carried into the capability payload as the query
    assert r.params.get("query") == "detect the green bottle"


def test_decomposer_does_not_clear_empty_strategy_detect_step() -> None:
    """The decomposer's fail-loud validator clears a NON-EMPTY unknown strategy but
    leaves an EMPTY-strategy detect step intact — so the keyword route survives the
    producer's plan validation (the precondition for the route above)."""
    from unittest.mock import MagicMock

    from vector_os_nano.vcli.cognitive.goal_decomposer import GoalDecomposer

    skill_registry = MagicMock()
    skill_registry.list_skills.return_value = ["perception_grasp", "navigate"]
    dec = GoalDecomposer(backend=MagicMock(), skill_registry=skill_registry)
    # 'detect' is NOT a known strategy (capabilities are not in KNOWN_STRATEGIES)
    assert "detect" not in dec.KNOWN_STRATEGIES
    plan = {
        "goal": "pick up the green bottle",
        "sub_goals": [
            {
                "name": "detect_bottle",
                "description": "detect the green bottle",
                "verify": "len(detect_objects()) > 0",
                "strategy": "",  # empty -> keyword route, survives validation
                "strategy_params": {},
                "depends_on": [],
            }
        ],
    }
    import json

    tree = dec._parse_and_validate(plan["goal"], json.dumps(plan))
    sg = tree.sub_goals[0]
    assert sg.strategy == ""  # NOT cleared
    assert sg.cleared_strategy == ""  # no hallucination stamp


def test_executor_dispatches_detect_capability_and_captures_boxes() -> None:
    """The REAL GoalExecutor routes a producer ``detect`` sub-goal through
    _execute_capability to a registered DetectorCapability and captures its
    boxes — proving the orchestration-layer route, not a skill-internal call."""
    cap, det = _real_detect_capability()
    reg = CapabilityRegistry()
    reg.register(cap)
    assert "detect" in reg.names()

    selector = StrategySelector(capability_names=reg.names())

    # verify namespace: detect_objects() reads the box COUNT the capability just
    # produced would be a deeper wire; here the honest RAN predicate is provided
    # directly so the step grades success when the detector RAN and found a box.
    verifier = MagicMock()
    verifier.verify.return_value = True  # len(detect_objects())>0 holds when boxes found

    ex = GoalExecutor(
        strategy_selector=selector,
        verifier=verifier,
        capability_registry=reg,
        # the context supplies the RGB frame the detector reads
        build_context=_FakeContextRGB,
    )

    # Run through the REAL harness so a fresh Blackboard is attached and capture
    # happens exactly as on a live vgg_execute run.
    harness = VGGHarness(
        decomposer=MagicMock(),
        executor=ex,
        selector=selector,
        config=HarnessConfig(max_step_retries=0, max_redecompose=0, max_pipeline_retries=0),
    )
    tree = GoalTree(goal="detect the green bottle", sub_goals=(_detect_subgoal(),))
    trace = harness.run(task=tree.goal, world_context="", goal_tree=tree)

    # the detector actually ran (the model family was invoked)
    assert det.calls, "DetectorCapability.invoke never called the detector"
    assert det.calls[0][1] == "the green bottle"

    step = trace.steps[0]
    # ROUTED VIA THE CAPABILITY BRANCH — the strategy name is the capability name
    assert step.strategy == "detect"
    assert step.success is True

    # BOXES CAPTURED in the step's structured output (Stage 1a) ...
    out = step.result_data.get("output", {})
    assert out.get("boxes"), f"no boxes captured in result_data: {step.result_data}"
    assert out["boxes"][0] == [100.0, 80.0, 160.0, 200.0]
    assert out.get("labels") == ["green bottle"]

    # ... AND on the run Blackboard, so ${detect_bottle.output.boxes} could flow
    # to a later step (rule 4: the observation is not discarded).
    bb = ex.blackboard
    captured = bb.get("detect_bottle")
    assert captured is not None
    assert captured["output"]["boxes"][0] == [100.0, 80.0, 160.0, 200.0]


def test_capability_cannot_self_certify_around_verify() -> None:
    """The moat invariant on the producer route: detector RAN (success=True) but a
    FALSE verify predicate still fails the step — the capability never grades
    itself (rule 5)."""
    cap, _det = _real_detect_capability()
    reg = CapabilityRegistry()
    reg.register(cap)
    selector = StrategySelector(capability_names=reg.names())
    verifier = MagicMock()
    verifier.verify.return_value = False  # predicate says NO

    ex = GoalExecutor(
        strategy_selector=selector, verifier=verifier,
        capability_registry=reg, build_context=_FakeContextRGB,
    )
    trace = ex.execute(GoalTree("g", (_detect_subgoal(),)))
    assert trace.success is False
    assert trace.steps[0].verify_result is False


# ---------------------------------------------------------------------------
# 2) Composed plan shape: detect (capability) -> perception_grasp (skill).
# ---------------------------------------------------------------------------


def _composed_plan() -> GoalTree:
    detect = _detect_subgoal()
    grasp = SubGoal(
        name="grasp_bottle",
        description="pick up the green bottle",
        verify="holding_object('pickable_bottle_green')",
        strategy="perception_grasp",
        strategy_params={"query": "the green bottle"},
        depends_on=("detect_bottle",),
    )
    return GoalTree(goal="pick up the green bottle", sub_goals=(detect, grasp))


def test_composed_plan_routes_detect_capability_then_grasp_skill() -> None:
    """The two-step composed plan keeps its routed shape: the producer's first step
    routes to the detector CAPABILITY (orchestration-layer model route) and the
    second to the grasp SKILL — distinct executor types from ONE plan."""
    # detect is a registered capability; perception_grasp is a registered skill.
    skill_registry = MagicMock()
    skill_registry.list_skills.return_value = ["perception_grasp"]
    skill_registry.match.return_value = None  # explicit strategies only

    sel = StrategySelector(
        skill_registry=skill_registry,
        capability_names={"detect"},
    )
    plan = _composed_plan()
    detect_sg, grasp_sg = plan.sub_goals

    r_detect = sel.select(detect_sg)
    r_grasp = sel.select(grasp_sg)

    assert (r_detect.executor_type, r_detect.name) == ("capability", "detect")
    # perception_grasp is a registered skill -> skill branch (the classical route)
    assert (r_grasp.executor_type, r_grasp.name) == ("skill", "perception_grasp")
