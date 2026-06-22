#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R37 REAL-SIM probe — TRUE producer->consumer box-flow composition.

Closes D50's headline caveat: the producer-routed `detect` (grounding-dino
DetectorCapability) box now FLOWS into the grasp's 3D target — the grasp CONSUMES
the routed box (back-projects it to a world grasp point) instead of running its OWN
re-perceive. Everything real except the LLM token stream (same faked-LLM policy as
D39/D46/D48/R36):

  - REAL go2+arm MuJoCo sim + ROS2 bridge (sim_tool._start_go2(with_arm=True));
  - REAL engine wiring: VectorEngine + init_vgg(world=RobotWorld) ->
    register_capabilities registers the 'detect' DetectorCapability (grounding-dino);
  - REAL capability dispatch: vgg_decompose -> vgg_execute -> GoalExecutor ->
    StrategySelector keyword route -> _execute_capability -> grounding-dino.detect;
  - the detect step's boxes are captured on the Blackboard; the GRASP step's
    strategy_params bind ${detect_bottle.output.detections} (rule 4) -> the routed
    box flows into the grasp, which CONSUMES it (segment + grasp_point_from_rgbd)
    rather than re-perceiving;
  - REAL grasp skill + weld + holding_object oracle grades GROUNDED;
  - FAKED only: the decompose LLM call (FakeBackend returns a canned 2-step plan).

The NEW claim over R36: the grasp's target came FROM the routed detector's box
(composition), proven by the trace (consumed_bbox=True, reperceived=False, the
grasp's own detect/front_object NOT called this run) AND a GROUNDED weld verdict.

Run:
  VECTOR_SIM_WITH_ARM=1 VECTOR_ENABLE_MANIPULATION=1 MUJOCO_GL=egl \
  HF_HOME=/home/yusen/.cache/huggingface \
  PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r37_box_flow_composition.py
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("VECTOR_ENABLE_MANIPULATION", "1")
os.environ.setdefault("VECTOR_SIM_WITH_ARM", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

ART = "/tmp/r37_probe"
os.makedirs(ART, exist_ok=True)


def _log(msg: str) -> None:
    print(f"[R37] {msg}", flush=True)


# Canned 2-step decompose plan.
# step0 detect_bottle: EMPTY strategy + detect-keyword description -> the keyword
#       ladder routes to the 'detect' CAPABILITY (grounding-dino); its boxes land on
#       the Blackboard under the step name.
# step1 grasp_bottle: the classical grasp SKILL, BUT its strategy_params now bind
#       ${detect_bottle.output.detections} -> the routed box FLOWS in and the grasp
#       CONSUMES it (no re-perceive). verify grades GROUNDED via the real weld oracle.
_PLAN = {
    "goal": "pick up the green bottle",
    "sub_goals": [
        {
            "name": "detect_bottle",
            "description": "detect the green bottle",  # 'detect' keyword -> capability
            "verify": "len(detect_objects()) > 0",
            "strategy": "",
            "strategy_params": {},
            "depends_on": [],
            "timeout_sec": 30.0,
        },
        {
            "name": "grasp_bottle",
            "description": "拿起绿色的瓶子",
            "verify": "holding_object('pickable_bottle_green')",
            "strategy": "perception_grasp_skill",
            "strategy_params": {
                "query": "绿色的瓶子",
                # rule-4 binding: the producer detect's full detection dicts flow in.
                # The grasp colour-selects the matching box and back-projects it.
                "detections": "${detect_bottle.output.detections}",
            },
            "depends_on": ["detect_bottle"],
            "timeout_sec": 60.0,
        },
    ],
}


class _FakeBackend:
    """Minimal canned LLMBackend — returns the 2-step decompose plan text."""

    def __init__(self, plan: dict) -> None:
        self._text = json.dumps(plan, ensure_ascii=False)

    def call(self, messages, tools, system, max_tokens,
             on_text=None, on_reasoning=None):
        from vector_os_nano.vcli.backends.types import LLMResponse
        from vector_os_nano.vcli.session import TokenUsage
        if on_text is not None:
            on_text(self._text)
        return LLMResponse(text=self._text, tool_calls=[], stop_reason="end_turn",
                           usage=TokenUsage(input_tokens=0, output_tokens=0))


def main() -> int:
    FakeBackend = _FakeBackend
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.intent_router import IntentRouter
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool
    from vector_os_nano.vcli.worlds.robot import RobotWorld
    from vector_os_nano.vcli.cognitive.trace_store import verify_oracle_names

    _log("booting go2+arm sim (real MuJoCo + ROS2 bridge)...")
    agent = SimStartTool._start_go2(gui=False, with_arm=True)
    if getattr(agent, "_arm", None) is None:
        _log("FAIL: no arm on agent (manipulation not wired)")
        return 1
    _log(f"sim up: base={type(agent._base).__name__} arm={type(agent._arm).__name__}")
    time.sleep(8.0)

    backend = FakeBackend(_PLAN)
    engine = VectorEngine(backend=backend, intent_router=IntentRouter())
    world = RobotWorld()
    engine.init_vgg(
        backend=backend,
        agent=agent,
        skill_registry=getattr(agent, "_skill_registry", None),
        world=world,
        persist_dir=None,
    )
    if not engine._vgg_enabled:
        _log("FAIL: VGG not enabled")
        return 1

    reg = engine._goal_executor._capability_registry
    cap_names = sorted(reg.names()) if reg is not None else []
    _log(f"registered capabilities on live executor: {cap_names}")
    if "detect" not in cap_names:
        _log("FAIL: 'detect' capability not registered")
        return 1

    goal = "拿起绿色的瓶子"
    _log(f"decompose (producer)+execute turn: {goal!r}")
    tree = engine._goal_decomposer.decompose(goal, engine._build_world_context())
    _log(f"producer plan: {[(sg.name, sg.strategy or '<empty>') for sg in tree.sub_goals]}")
    # Confirm the binding survived decompose into the grasp step's params.
    grasp_sg = next((sg for sg in tree.sub_goals if sg.name == "grasp_bottle"), None)
    _log(f"grasp step params (pre-resolve): {getattr(grasp_sg, 'strategy_params', None)}")

    trace = engine.vgg_execute(tree)

    oracle_names = verify_oracle_names(agent, engine)
    report = {"goal": goal, "overall_success": trace.success, "steps": []}
    detect_routed_via_capability = False
    detect_boxes = None
    grasp_grounded = False
    grasp_consumed_bbox = None
    grasp_reperceived = None
    grasp_world = None

    for step in trace.steps:
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        srec = {
            "name": step.sub_goal_name,
            "strategy": step.strategy,
            "success": step.success,
            "verify_result": step.verify_result,
            "error": step.error,
            "output_keys": sorted(out.keys()) if isinstance(out, dict) else None,
        }
        if isinstance(out, dict):
            if "boxes" in out:
                srec["boxes"] = out.get("boxes")
                srec["labels"] = out.get("labels")
                srec["scores"] = out.get("scores")
            for k in ("consumed_bbox", "reperceived", "grasp_world",
                      "detection_label", "perceived"):
                if k in out:
                    srec[k] = out.get(k)
        report["steps"].append(srec)

        if step.sub_goal_name == "detect_bottle":
            if step.strategy == "detect" and isinstance(out, dict) and "boxes" in out:
                detect_routed_via_capability = True
                detect_boxes = out.get("boxes")
        if step.sub_goal_name == "grasp_bottle":
            grasp_grounded = bool(step.success and step.verify_result)
            if isinstance(out, dict):
                grasp_consumed_bbox = out.get("consumed_bbox")
                grasp_reperceived = out.get("reperceived")
                grasp_world = out.get("grasp_world")

    bb = engine._goal_executor.blackboard
    bb_detect = bb.get("detect_bottle") if bb is not None else None
    report["blackboard_detect_capture"] = (
        bb_detect.get("output", {}).get("boxes") if isinstance(bb_detect, dict) else None
    )
    report.update({
        "detect_routed_via_capability": detect_routed_via_capability,
        "detect_boxes": detect_boxes,
        "grasp_grounded": grasp_grounded,
        "grasp_consumed_bbox": grasp_consumed_bbox,
        "grasp_reperceived": grasp_reperceived,
        "grasp_world": grasp_world,
        "oracle_names_sample": sorted(oracle_names)[:12],
    })

    path = os.path.join(ART, "trace.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    _log(f"trace written: {path}")
    _log(json.dumps({
        "detect_routed_via_capability": detect_routed_via_capability,
        "detect_boxes_count": len(detect_boxes) if detect_boxes else 0,
        "grasp_consumed_bbox": grasp_consumed_bbox,
        "grasp_reperceived": grasp_reperceived,
        "grasp_grounded": grasp_grounded,
        "overall_success": trace.success,
    }, ensure_ascii=False))

    # The R37 verdict: composition (box CONSUMED, re-perceive suppressed) AND GROUNDED.
    composed = (
        detect_routed_via_capability
        and grasp_consumed_bbox is True
        and grasp_reperceived is False
    )
    verdict_ok = composed and grasp_grounded
    _log(f"VERDICT: composed(box consumed, re-perceive suppressed)={composed} "
         f"grasp GROUNDED={grasp_grounded} -> {'PASS' if verdict_ok else 'PARTIAL/FAIL'}")
    return 0 if verdict_ok else 2


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        rc = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
