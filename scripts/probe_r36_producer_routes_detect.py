#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R36 REAL-SIM probe — the PRODUCER routes a `detect` sub-goal to the
grounding-dino capability via _execute_capability, composed into a GROUNDED grasp.

EVERYTHING real except the LLM token stream (same faked-LLM policy as D39/D46/D48):
  - REAL go2+arm MuJoCo sim + ROS2 bridge (sim_tool._start_go2(with_arm=True));
  - REAL engine wiring: VectorEngine + init_vgg(world=RobotWorld) ->
    register_capabilities registers the 'detect' DetectorCapability (grounding-dino);
  - REAL capability dispatch: vgg_decompose -> vgg_execute -> GoalExecutor ->
    StrategySelector keyword route -> _execute_capability -> grounding-dino.detect;
  - REAL grasp skill + weld + holding_object oracle grades GROUNDED;
  - FAKED only: the decompose LLM call (FakeBackend returns a canned 2-step plan).

The producer-realistic route is an EMPTY strategy + a detect-keyword description:
the decomposer leaves an empty strategy intact and the StrategySelector's keyword
ladder routes the 'detect' description to the registered capability. ZERO edits
under vcli/cognitive/.

Run:
  VECTOR_SIM_WITH_ARM=1 VECTOR_ENABLE_MANIPULATION=1 MUJOCO_GL=egl \
  HF_HOME=/home/yusen/.cache/huggingface \
  PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r36_producer_routes_detect.py
"""
from __future__ import annotations

import json
import os
import sys
import time

# Force offline grounding-dino (weights are cached) and a headless GL.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("VECTOR_ENABLE_MANIPULATION", "1")
os.environ.setdefault("VECTOR_SIM_WITH_ARM", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

ART = "/tmp/r36_probe"
os.makedirs(ART, exist_ok=True)


def _log(msg: str) -> None:
    print(f"[R36] {msg}", flush=True)


# The canned 2-step decompose plan the FakeBackend returns for the grasp turn.
# step0: detect — EMPTY strategy + detect-keyword description -> keyword ladder
#        routes to the 'detect' CAPABILITY (grounding-dino). verify grades that
#        detection RAN (honest: not causation-gated).
# step1: perception_grasp — the classical grasp SKILL; verify grades GROUNDED via
#        the real weld oracle holding_object('pickable_bottle_green').
_PLAN = {
    "goal": "pick up the green bottle",
    "sub_goals": [
        {
            "name": "detect_bottle",
            "description": "detect the green bottle",  # 'detect' keyword -> capability
            "verify": "len(detect_objects()) > 0",
            "strategy": "",  # empty -> keyword route survives decomposer validation
            "strategy_params": {},
            "depends_on": [],
            "timeout_sec": 30.0,
        },
        {
            "name": "grasp_bottle",
            "description": "拿起绿色的瓶子",
            "verify": "holding_object('pickable_bottle_green')",
            "strategy": "perception_grasp_skill",
            "strategy_params": {"query": "绿色的瓶子"},
            "depends_on": ["detect_bottle"],
            "timeout_sec": 60.0,
        },
    ],
}


class _FakeBackend:
    """Minimal canned LLMBackend — returns the 2-step decompose plan as response
    text (the decomposer's single LLM call). Same seam as tests' FakeBackend; no
    test-package import. Only the LLM token stream is faked; the spine is real."""

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
    # Let the bridge settle (weld topics, camera frames).
    time.sleep(8.0)

    backend = FakeBackend(_PLAN)
    engine = VectorEngine(backend=backend, intent_router=IntentRouter())
    world = RobotWorld()
    engine.init_vgg(
        backend=backend,
        agent=agent,
        skill_registry=getattr(agent, "_skill_registry", None),
        world=world,
        persist_dir=None,  # no template short-circuit
    )
    if not engine._vgg_enabled:
        _log("FAIL: VGG not enabled")
        return 1

    # Confirm the detector capability is REGISTERED on the live executor.
    reg = engine._goal_executor._capability_registry
    cap_names = sorted(reg.names()) if reg is not None else []
    _log(f"registered capabilities on live executor: {cap_names}")
    if "detect" not in cap_names:
        _log("FAIL: 'detect' capability not registered (no cross-model route possible)")
        return 1

    # --- Drive the PRODUCER path: decompose (faked LLM) -> execute (all real) ---
    # Force the LLM DECOMPOSER (the multi-step producer), not the single-skill
    # fast path. vgg_decompose() short-circuits a 1-skill match ("拿起..." ->
    # perception_grasp) before ever calling the decomposer, which would skip the
    # detect step entirely. The decomposer IS the producer here (faked token
    # stream); calling it directly is the honest 2-step producer turn.
    goal = "拿起绿色的瓶子"
    _log(f"decompose (producer)+execute turn: {goal!r}")
    tree = engine._goal_decomposer.decompose(goal, engine._build_world_context())
    _log(f"producer plan: {[ (sg.name, sg.strategy or '<empty>') for sg in tree.sub_goals ]}")

    trace = engine.vgg_execute(tree)

    # --- Inspect the trace: routing evidence + boxes + GROUNDED ---
    oracle_names = verify_oracle_names(agent, engine)
    report = {
        "goal": goal,
        "overall_success": trace.success,
        "steps": [],
    }
    detect_routed_via_capability = False
    detect_boxes = None
    grasp_grounded = False

    for sg, step in zip(tree.sub_goals, trace.steps):
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        srec = {
            "name": step.sub_goal_name,
            "strategy": step.strategy,
            "success": step.success,
            "verify_result": step.verify_result,
            "actor_caused": str(getattr(step, "actor_caused", None)),
            "error": step.error,
            "output_keys": sorted(out.keys()) if isinstance(out, dict) else None,
        }
        if isinstance(out, dict) and "boxes" in out:
            srec["boxes"] = out.get("boxes")
            srec["labels"] = out.get("labels")
            srec["scores"] = out.get("scores")
        report["steps"].append(srec)

        # The detect step routes via the capability branch when its resolved
        # strategy name is the capability name 'detect' (the selector stamps the
        # capability name as the step strategy).
        if step.sub_goal_name == "detect_bottle":
            if step.strategy == "detect" and isinstance(out, dict) and "boxes" in out:
                detect_routed_via_capability = True
                detect_boxes = out.get("boxes")
        if step.sub_goal_name == "grasp_bottle":
            grasp_grounded = bool(step.success and step.verify_result)

    # Also read the blackboard capture (closes the loop, rule 4).
    bb = engine._goal_executor.blackboard
    bb_detect = bb.get("detect_bottle") if bb is not None else None
    report["blackboard_detect_capture"] = (
        bb_detect.get("output", {}).get("boxes") if isinstance(bb_detect, dict) else None
    )

    report["detect_routed_via_capability"] = detect_routed_via_capability
    report["detect_boxes"] = detect_boxes
    report["grasp_grounded"] = grasp_grounded
    report["oracle_names_sample"] = sorted(oracle_names)[:12]

    path = os.path.join(ART, "trace.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    _log(f"trace written: {path}")
    _log(json.dumps({
        "detect_routed_via_capability": detect_routed_via_capability,
        "detect_step_strategy": report["steps"][0]["strategy"] if report["steps"] else None,
        "detect_boxes_count": len(detect_boxes) if detect_boxes else 0,
        "grasp_grounded": grasp_grounded,
        "overall_success": trace.success,
    }, ensure_ascii=False))

    verdict_ok = detect_routed_via_capability and grasp_grounded
    _log(f"VERDICT: producer routed detect->capability={detect_routed_via_capability} "
         f"grasp GROUNDED={grasp_grounded} -> {'PASS' if verdict_ok else 'PARTIAL/FAIL'}")
    return 0 if verdict_ok else 2


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        rc = 1
    # Hard-exit so a lingering sim/GL daemon thread can't hang the probe.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
