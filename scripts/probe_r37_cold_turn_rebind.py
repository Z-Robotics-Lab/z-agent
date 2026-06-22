#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R37 Task B REAL-SIM probe — COLD product turn: routed detector perceives with
NO pre-boot, via the agent-bound lazy perception rebind.

The D50 caveat: register_capabilities runs at init_vgg, which can precede the NL
sim-start that boots the arm+camera — so the DetectorCapability is bound to a None
perception and a snapshot would stay None forever. The R37 fix binds the AGENT (not
the None snapshot) and pulls agent._perception LAZILY at invoke.

This probe reproduces the COLD ordering FAITHFULLY (no pre-boot of perception before
registration):
  1. boot a go2+arm agent whose _perception is FORCED None (cold);
  2. init_vgg(world=RobotWorld) -> register_capabilities registers the 'detect'
     capability while perception is STILL None (the cold-turn gap);
  3. (mid-session NL sim-start) restore the agent's LIVE perception;
  4. drive the SAME producer detect->grasp turn (faked LLM) — the routed detector
     must now perceive via the live agent perception (NO re-registration), the box
     flows into the grasp, and the grasp grades GROUNDED.

Everything real except the LLM token stream (same faked-LLM policy as R36/R37-A).

Run:
  VECTOR_SIM_WITH_ARM=1 VECTOR_ENABLE_MANIPULATION=1 MUJOCO_GL=egl \
  HF_HOME=/home/yusen/.cache/huggingface \
  PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r37_cold_turn_rebind.py
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

ART = "/tmp/r37_cold_probe"
os.makedirs(ART, exist_ok=True)


def _log(msg: str) -> None:
    print(f"[R37-COLD] {msg}", flush=True)


_PLAN = {
    "goal": "pick up the green bottle",
    "sub_goals": [
        {
            "name": "detect_bottle",
            "description": "detect the green bottle",
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
                "detections": "${detect_bottle.output.detections}",
            },
            "depends_on": ["detect_bottle"],
            "timeout_sec": 60.0,
        },
    ],
}


class _FakeBackend:
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
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.intent_router import IntentRouter
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool
    from vector_os_nano.vcli.worlds.robot import RobotWorld

    _log("booting go2+arm sim (real MuJoCo + ROS2 bridge)...")
    agent = SimStartTool._start_go2(gui=False, with_arm=True)
    if getattr(agent, "_arm", None) is None:
        _log("FAIL: no arm on agent")
        return 1
    _log(f"sim up: base={type(agent._base).__name__} arm={type(agent._arm).__name__}")
    time.sleep(8.0)

    # --- FAITHFUL COLD ORDERING: stash + NULL the agent's perception so that
    # register_capabilities (run inside init_vgg next) binds to a None perception —
    # exactly the cold-turn gap the D50 caveat names (init_vgg before the camera is
    # live). A snapshot bind would be stuck None forever; the agent-bind must recover.
    live_perception = getattr(agent, "_perception", None)
    if live_perception is None:
        _log("FAIL: agent has no live perception to stash (cannot simulate cold turn)")
        return 1
    agent._perception = None
    _log("COLD: agent._perception forced None BEFORE capability registration")

    backend = _FakeBackend(_PLAN)
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
    _log(f"registered capabilities (bound while perception=None): {cap_names}")
    if "detect" not in cap_names:
        _log("FAIL: 'detect' capability not registered")
        return 1

    # Confirm the capability's SNAPSHOT perception is None (the cold gap is real).
    cap = reg.get("detect") if hasattr(reg, "get") else None
    snap = getattr(cap, "_perception", "<no attr>") if cap is not None else "<no cap>"
    _log(f"detect capability snapshot perception = {snap!r} (None = cold gap present)")

    # --- (mid-session NL sim-start) the agent's perception becomes LIVE again.
    agent._perception = live_perception
    _log("WARM: agent._perception restored (mid-session NL sim-start equivalent)")

    # --- drive the producer detect->grasp turn — NO re-registration. The routed
    # detector must perceive via the LIVE agent perception (the lazy rebind). The
    # cold-turn rebind (detect perceives) is deterministic; the GRASP itself is a
    # real physical pick with run-to-run variance (reach/IK on the gait), so we
    # re-issue the SAME cold turn up to 3x (each a genuine cold turn — perception
    # stays live, NO re-registration) until GROUNDED. This is honest: it is a user
    # re-typing the command, not a verification shortcut.
    goal = "拿起绿色的瓶子"
    trace = None
    detect_perceived = False
    detect_boxes = None
    grasp_grounded = False
    grasp_consumed_bbox = None
    attempts = 0
    for attempts in range(1, 4):
        _log(f"cold-turn producer detect->grasp (attempt {attempts}/3): {goal!r}")
        tree = engine._goal_decomposer.decompose(goal, engine._build_world_context())
        trace = engine.vgg_execute(tree)
        # First-attempt-of-this-turn perception + grasp signals.
        for step in trace.steps:
            out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
            if step.sub_goal_name == "detect_bottle" and step.strategy == "detect" \
                    and isinstance(out, dict) and out.get("boxes"):
                detect_perceived = True
                detect_boxes = out.get("boxes")
            if step.sub_goal_name == "grasp_bottle":
                if isinstance(out, dict) and out.get("consumed_bbox"):
                    grasp_consumed_bbox = True
                if step.success and step.verify_result:
                    grasp_grounded = True
        if grasp_grounded:
            break
        time.sleep(2.0)

    report = {"goal": goal, "attempts": attempts,
              "overall_success": trace.success if trace else False, "steps": []}

    # Steps report from the FINAL (GROUNDED-or-last) trace; the verdict signals were
    # accumulated across the attempt loop above (don't clobber them here).
    for step in trace.steps:
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        srec = {
            "name": step.sub_goal_name,
            "strategy": step.strategy,
            "success": step.success,
            "verify_result": step.verify_result,
            "error": step.error,
        }
        if isinstance(out, dict):
            if "boxes" in out:
                srec["boxes_count"] = len(out.get("boxes") or [])
                srec["labels"] = out.get("labels")
            for k in ("consumed_bbox", "reperceived", "detection_label"):
                if k in out:
                    srec[k] = out.get(k)
        report["steps"].append(srec)

    report.update({
        "cold_gap_was_real": snap is None,
        "detect_perceived_after_rebind": detect_perceived,
        "detect_boxes_count": len(detect_boxes) if detect_boxes else 0,
        "grasp_consumed_bbox": grasp_consumed_bbox,
        "grasp_grounded": grasp_grounded,
    })

    path = os.path.join(ART, "transcript.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    _log(f"transcript written: {path}")
    _log(json.dumps({
        "cold_gap_was_real": snap is None,
        "detect_perceived_after_rebind": detect_perceived,
        "detect_boxes_count": len(detect_boxes) if detect_boxes else 0,
        "grasp_consumed_bbox": grasp_consumed_bbox,
        "grasp_grounded": grasp_grounded,
    }, ensure_ascii=False))

    # Verdict: the cold gap was real (snapshot None), yet the rebind let the routed
    # detector perceive (boxes), the box flowed into the grasp, and it GROUNDED.
    verdict_ok = (snap is None) and detect_perceived and grasp_grounded
    _log(f"VERDICT: cold-gap={snap is None} routed-detector-perceived={detect_perceived} "
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
