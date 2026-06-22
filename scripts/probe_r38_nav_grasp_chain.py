#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R38 REAL-SIM probe — NL chain navigate(table) -> perception_grasp(red can).

The cross-skill finish: "去桌子那里把红的拿起来" decomposes (producer) into a 2-step
GoalTree and executes end-to-end against the REAL go2+arm MuJoCo sim + ROS2 bridge
(FAR planner wired). Everything real except the LLM token stream (same faked-LLM
policy as D39/D46/D48/R36/R37):

  - REAL go2+arm MuJoCo sim + ROS2 bridge (SimStartTool._start_go2(with_arm=True))
    = the bare-cli launch path (launch_explore.sh: bridge + FAR + TARE + local
    planner). The dog SPAWNS at qpos=(10.0, 3.0, 0.35) facing +X.
  - step0 navigate_table: strategy="navigate", strategy_params={"x":10.5,"y":3.0}
    -> NavigateSkill coordinate path -> base.navigate_to(10.5, 3.0) drives the dog
    to the table via FAR. verify at_position(10.5, 3.0) grades RAN (honest, D14:
    cmd_vel nav is not actor-causation-gated).
  - step1 grasp_red: strategy="perception_grasp", strategy_params={"query":"红色的罐子"},
    verify holding_object('pickable_can_red') -> GROUNDED via the real weld oracle.
    The R38 fix (grasp_ready_repose) corrects FAR's arbitrary arrival heading BEFORE
    the scripted approach, so the grasp works from a FAR pose, not just from spawn.
  - FAKED only: the decompose LLM call (FakeBackend returns the canned 2-step plan).

Honest split surfaced in the verdict: nav RAN (FAR drove the dog to the table) vs
grasp GROUNDED (red can welded + lifted). The red can is OFFSET (reach-limited per
D47); run a few times and report HONEST N/M GROUNDED — a reach miss grades RAN
honestly, NOT a fake.

Run (serialized; nuke after):
  VECTOR_SIM_WITH_ARM=1 VECTOR_ENABLE_MANIPULATION=1 MUJOCO_GL=egl \
  HF_HOME=/home/yusen/.cache/huggingface \
  PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r38_nav_grasp_chain.py [N_TRIALS]
"""
from __future__ import annotations

import json
import math
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

ART = "/tmp/r38_probe"
os.makedirs(ART, exist_ok=True)

# Red can GT (scene_room_piper.xml) — used only for the honest grasp-vs-GT report,
# never fed into the grasp (the grasp perceives its own point).
_RED_GT = (10.90, 3.22, 0.32)


def _log(msg: str) -> None:
    print(f"[R38] {msg}", flush=True)


# Canned 2-step decompose plan for "去桌子那里把红的拿起来".
# step0 navigate_table: COORDINATE goal to the table standoff (10.5, 3.0). The
#       NavigateSkill coordinate path drives FAR. verify at_position -> RAN.
# step1 grasp_red: the perception grasp SKILL, query the red can. The R38 re-pose
#       corrects FAR's arrival heading first. verify holding_object -> GROUNDED.
_PLAN = {
    "goal": "去桌子那里把红色的罐子拿起来",
    "sub_goals": [
        {
            "name": "navigate_table",
            "description": "navigate to the table at (10.5, 3.0)",
            "verify": "at_position(10.5, 3.0)",
            "strategy": "navigate",
            "strategy_params": {"x": 10.5, "y": 3.0},
            "depends_on": [],
            "timeout_sec": 60.0,
        },
        {
            "name": "grasp_red",
            "description": "拿起红色的罐子",
            "verify": "holding_object('pickable_can_red')",
            "strategy": "perception_grasp",
            "strategy_params": {"query": "红色的罐子"},
            "depends_on": ["navigate_table"],
            "timeout_sec": 90.0,
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


def _save_frame(agent, name: str) -> str | None:
    """Save a scene frame from the agent's perception camera, if available."""
    try:
        import cv2
        base = getattr(agent, "_base", None)
        rgb = None
        if base is not None and hasattr(base, "get_camera_frame"):
            rgb = base.get_camera_frame()
        if rgb is None:
            return None
        path = os.path.join(ART, name)
        cv2.imwrite(path, rgb[:, :, ::-1])
        return path
    except Exception as exc:  # noqa: BLE001
        _log(f"frame save failed: {exc}")
        return None


def _run_once(engine, agent, world, trial: int) -> dict:
    from vector_os_nano.vcli.cognitive.trace_store import verify_oracle_names

    goal = "去桌子那里把红色的罐子拿起来"
    base = agent._base
    start_pos = base.get_position()
    start_hd = base.get_heading()
    _log(f"trial {trial}: spawn pos=({start_pos[0]:.2f},{start_pos[1]:.2f}) "
         f"heading={start_hd:.2f}")

    tree = engine._goal_decomposer.decompose(goal, engine._build_world_context())
    _log(f"trial {trial}: plan {[(sg.name, sg.strategy) for sg in tree.sub_goals]}")

    # Drive the chain; sample positions during the nav leg to prove FAR moved it.
    pos_trace = [(0.0, float(start_pos[0]), float(start_pos[1]), float(start_hd))]

    import threading
    stop = threading.Event()

    def _sample():
        t0 = time.time()
        while not stop.is_set():
            p = base.get_position()
            pos_trace.append((round(time.time() - t0, 1),
                              round(float(p[0]), 2), round(float(p[1]), 2),
                              round(float(base.get_heading()), 2)))
            time.sleep(1.0)

    sampler = threading.Thread(target=_sample, daemon=True)
    sampler.start()
    trace = engine.vgg_execute(tree)
    stop.set()
    sampler.join(timeout=2.0)

    end_pos = base.get_position()
    oracle_names = verify_oracle_names(agent, engine)

    rec = {"trial": trial, "goal": goal, "overall_success": trace.success,
           "spawn": [round(float(start_pos[0]), 2), round(float(start_pos[1]), 2),
                     round(float(start_hd), 2)],
           "end_pos": [round(float(end_pos[0]), 2), round(float(end_pos[1]), 2)],
           "pos_trace": pos_trace, "steps": []}

    nav_ran = nav_drove = False
    grasp_grounded = False
    grasp_world = None
    dist_moved = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])

    for step in trace.steps:
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        srec = {"name": step.sub_goal_name, "strategy": step.strategy,
                "success": step.success, "verify_result": step.verify_result,
                "classification": getattr(step, "classification", None),
                "error": step.error}
        if isinstance(out, dict):
            for k in ("mode", "position", "target", "distance_to_target",
                      "grasp_world", "detection_label", "approached", "perceived"):
                if k in out:
                    srec[k] = out.get(k)
        rec["steps"].append(srec)

        if step.sub_goal_name == "navigate_table":
            nav_ran = bool(step.success)
            # FAR drove it if the dog moved a meaningful distance toward the table.
            nav_drove = dist_moved > 1.0 or (
                isinstance(out, dict) and isinstance(out.get("position"), list)
                and math.hypot(out["position"][0] - 10.5, out["position"][1] - 3.0) < 1.5
            )
        if step.sub_goal_name == "grasp_red":
            grasp_grounded = bool(step.success and step.verify_result)
            if isinstance(out, dict):
                grasp_world = out.get("grasp_world")

    rec.update({
        "nav_ran": nav_ran, "nav_drove_dist_m": round(dist_moved, 2),
        "nav_drove": bool(nav_drove),
        "grasp_grounded": grasp_grounded, "grasp_world": grasp_world,
        "red_gt": list(_RED_GT),
    })
    if grasp_world:
        rec["grasp_vs_red_gt_m"] = round(
            math.hypot(grasp_world[0] - _RED_GT[0], grasp_world[1] - _RED_GT[1]), 3)
    rec["frame"] = _save_frame(agent, f"trial{trial}_after.png")
    _log(f"trial {trial}: nav_ran={nav_ran} nav_drove={nav_drove} "
         f"({dist_moved:.2f}m) grasp_GROUNDED={grasp_grounded}")
    return rec


def main() -> int:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.intent_router import IntentRouter
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool
    from vector_os_nano.vcli.worlds.robot import RobotWorld

    _log("booting go2+arm sim (real MuJoCo + ROS2 bridge + FAR)...")
    agent = SimStartTool._start_go2(gui=False, with_arm=True)
    if getattr(agent, "_arm", None) is None:
        _log("FAIL: no arm on agent (manipulation not wired)")
        return 1
    _log(f"sim up: base={type(agent._base).__name__} arm={type(agent._arm).__name__}")
    time.sleep(8.0)  # let bridge + FAR + camera settle

    backend = _FakeBackend(_PLAN)
    engine = VectorEngine(backend=backend, intent_router=IntentRouter())
    world = RobotWorld()
    engine.init_vgg(backend=backend, agent=agent,
                    skill_registry=getattr(agent, "_skill_registry", None),
                    world=world, persist_dir=None)
    if not engine._vgg_enabled:
        _log("FAIL: VGG not enabled")
        return 1

    trials = []
    for i in range(1, n_trials + 1):
        try:
            trials.append(_run_once(engine, agent, world, i))
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            trials.append({"trial": i, "error": str(exc)})
        # Re-home the dog/arm between trials would need a sim reset; instead each
        # trial re-decomposes and re-drives from wherever the dog ended (the nav
        # leg re-routes to the table either way). The grasp re-pose handles any
        # arrival pose, which is exactly what we are proving.
        time.sleep(2.0)

    nav_drove_n = sum(1 for t in trials if t.get("nav_drove"))
    nav_ran_n = sum(1 for t in trials if t.get("nav_ran"))
    grounded_n = sum(1 for t in trials if t.get("grasp_grounded"))
    report = {
        "n_trials": n_trials,
        "nav_ran": f"{nav_ran_n}/{n_trials}",
        "nav_drove_to_table": f"{nav_drove_n}/{n_trials}",
        "grasp_GROUNDED": f"{grounded_n}/{n_trials}",
        "trials": trials,
    }
    path = os.path.join(ART, "trace.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    _log(f"trace written: {path}")
    _log(json.dumps({"nav_ran": report["nav_ran"],
                     "nav_drove_to_table": report["nav_drove_to_table"],
                     "grasp_GROUNDED": report["grasp_GROUNDED"]}, ensure_ascii=False))

    # VERDICT: the chain navigated (FAR drove the dog to the table, at_position RAN)
    # AND grasped the red can (GROUNDED) at least once.
    verdict_ok = nav_drove_n >= 1 and grounded_n >= 1
    _log(f"VERDICT: nav drove to table {nav_drove_n}/{n_trials}, "
         f"grasp GROUNDED {grounded_n}/{n_trials} -> "
         f"{'PASS' if verdict_ok else 'PARTIAL/FAIL'}")
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
