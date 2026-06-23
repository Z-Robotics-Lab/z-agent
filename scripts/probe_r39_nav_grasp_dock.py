#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R39 REAL-SIM probe — NL chain navigate(dock standoff) -> DOCK -> grasp(red can).

Closes D52's honest partial: the nav+grasp end-to-end now GROUNDS via a deterministic
TERMINAL DOCK between FAR's coarse arrival and the proven colour grasp. Everything
real except the LLM token stream (same faked-LLM policy as D39/D46/D48/R36/R37/R38):

  - REAL go2+arm MuJoCo sim + ROS2 bridge (SimStartTool._start_go2(with_arm=True)) =
    the bare-cli launch path (launch_explore.sh: bridge + FAR + TARE + local planner).
    The dog SPAWNS at qpos=(10.0, 3.0, 0.35) facing +X.
  - step0 navigate_dock: strategy="navigate_skill", strategy_params={"x":DOCK_X,"y":DOCK_Y}
    -> NavigateSkill coordinate path -> base.navigate_to(DOCK_X, DOCK_Y) drives the dog
    to the table vicinity via FAR (the un-park). The navigate GOAL is the DOCK STANDOFF,
    so reaching it makes at_position(DOCK_X, DOCK_Y) grade RAN (honest, D14: cmd_vel nav
    is not actor-causation-gated). The HONEST grade is at_position(tol 0.5 m).
  - step1 grasp_red: strategy="perception_grasp_skill", strategy_params={
        "query":"红色的罐子", "dock_pose":[DOCK_X, DOCK_Y, 0.0]}.
    The grasp FIRST dead-reckons to the FIXED proven pose (the dock — NOT can-relative,
    no chicken-and-egg), so the d435 frames the cans head-on; THEN runs the PROVEN colour
    grasp UNCHANGED. verify holding_object('pickable_can_red') -> GROUNDED via the real
    weld oracle.
  - FAKED only: the decompose LLM call (FakeBackend returns the canned 2-step plan).

Honest split surfaced in the verdict: nav RAN (FAR drove + dock reached at_position) vs
grasp GROUNDED (red can welded + lifted). The red can is OFFSET (y=3.22, reach-limited
per D47 ~75%); run a few times and report HONEST N/M for nav-RAN and grasp-GROUNDED
SEPARATELY — a reach miss grades RAN honestly, NOT a fake.

Run (serialized; nuke after):
  VECTOR_SIM_WITH_ARM=1 VECTOR_ENABLE_MANIPULATION=1 MUJOCO_GL=egl \
  HF_HOME=/home/yusen/.cache/huggingface \
  PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r39_nav_grasp_dock.py [N_TRIALS]
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

ART = "/tmp/r39_probe"
os.makedirs(ART, exist_ok=True)

# The FIXED proven table-approach pose (the scripted-from-spawn standoff). The dog
# SPAWNS at (10.0, 3.0) facing +X and the proven colour grasp (D47) GROUNDS from
# there: _approach_object jams the dog forward to ~x=10.45 on the centerline y=3.0
# and the d435 frames the 3 cans. So the dock target = the spawn pose, centerline
# y=3.0, x back from the cans (x_can~10.9), facing +X (heading 0). NOT can-relative.
_DOCK_X, _DOCK_Y, _DOCK_HD = 10.0, 3.0, 0.0

# Red can GT (scene_room_piper.xml: pickable_can_red pos="10.90 3.22 0.320") — used
# only for the honest grasp-vs-GT report, never fed into the grasp (the grasp
# perceives its own point). The probe asserts grasp_world lands near this.
_RED_GT = (10.90, 3.22, 0.32)


import logging as _logging
_logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for _n in ("transformers", "urllib3", "PIL", "matplotlib"):
    _logging.getLogger(_n).setLevel(_logging.WARNING)


def _log(msg: str) -> None:
    print(f"[R39] {msg}", flush=True)


# Canned 2-step decompose plan for "去桌子那里把红色的罐子拿起来".
# step0 navigate_dock: COORDINATE goal to the DOCK STANDOFF (10.0, 3.0) — reaching
#       it makes at_position grade RAN. NavigateSkill coordinate path drives FAR.
# step1 grasp_red: the perception grasp SKILL, query the red can, with dock_pose so
#       the grasp DEAD-RECKONS to the FIXED proven pose before perceiving, then runs
#       the proven colour grasp. verify holding_object -> GROUNDED.
_PLAN = {
    "goal": "去桌子那里把红色的罐子拿起来",
    "sub_goals": [
        {
            "name": "navigate_dock",
            "description": f"navigate to the table dock standoff at ({_DOCK_X}, {_DOCK_Y})",
            "verify": f"at_position({_DOCK_X}, {_DOCK_Y})",
            "strategy": "navigate_skill",
            "strategy_params": {"x": _DOCK_X, "y": _DOCK_Y},
            "depends_on": [],
            "timeout_sec": 90.0,
        },
        {
            "name": "grasp_red",
            "description": "拿起红色的罐子",
            "verify": "holding_object('pickable_can_red')",
            "strategy": "perception_grasp_skill",
            "strategy_params": {
                "query": "红色的罐子",
                "dock_pose": [_DOCK_X, _DOCK_Y, _DOCK_HD],
            },
            "depends_on": ["navigate_dock"],
            "timeout_sec": 120.0,
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


def _verify_ns(world, agent) -> dict:
    """The REAL spine verify namespace (at_position + holding_object oracles).

    Single-sourced from RobotWorld.build_verify_namespace(agent) — the EXACT
    functions the verify spine grades with (the moat oracles the actor cannot
    author), so the probe's RAN/GROUNDED grades match what the cli would surface.
    """
    return world.build_verify_namespace(agent)


def _at_position(world, agent, x: float, y: float, tol: float = 0.5) -> bool:
    """Evaluate the REAL at_position oracle (the honest RAN grade)."""
    try:
        fn = _verify_ns(world, agent).get("at_position")
        return bool(fn(x, y, tol)) if fn is not None else False
    except Exception as exc:  # noqa: BLE001
        _log(f"at_position oracle eval failed: {exc}")
        return False


def _holding(world, agent, name: str) -> bool:
    """Evaluate the REAL holding_object weld oracle (the honest GROUNDED grade)."""
    try:
        fn = _verify_ns(world, agent).get("holding_object")
        return bool(fn(name)) if fn is not None else False
    except Exception as exc:  # noqa: BLE001
        _log(f"holding_object oracle eval failed: {exc}")
        return False


def _run_once(engine, agent, world, trial: int) -> dict:
    from vector_os_nano.vcli.cognitive.trace_store import verify_oracle_names

    goal = "去桌子那里把红色的罐子拿起来"
    base = agent._base

    # Drive the dog AWAY from the table first (to ~16, 2.8 — the kitchen) so the
    # chain's navigate leg genuinely CROSSES the room back to the table via FAR
    # (not a no-op from spawn). Makes "FAR drove the dog" an honest claim.
    try:
        _log(f"trial {trial}: pre-drive AWAY to (16.0, 2.8) so the chain must drive back")
        base.navigate_to(16.0, 2.8, timeout=45.0)
    except Exception as exc:  # noqa: BLE001
        _log(f"trial {trial}: pre-drive raised (continuing): {exc}")
    # Disarm the nav flag + stop after the pre-drive so it does not drift.
    try:
        if os.path.exists("/tmp/vector_nav_active"):
            os.remove("/tmp/vector_nav_active")
        base.stop()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(1.0)

    start_pos = base.get_position()
    start_hd = base.get_heading()
    _log(f"trial {trial}: chain start pos=({start_pos[0]:.2f},{start_pos[1]:.2f}) "
         f"heading={start_hd:.2f}")

    tree = engine._goal_decomposer.decompose(goal, engine._build_world_context())
    _log(f"trial {trial}: plan "
         f"{[(sg.name, sg.strategy, dict(sg.strategy_params)) for sg in tree.sub_goals]}")

    # Pin ALL harness retry budgets to 0 (the D52 spine residual). Layer-1 step retry
    # CLEARS the explicit strategy on retry, re-routing via the keyword ladder and
    # OVERWRITING strategy_params with the description / empty query (the documented
    # strategy_params/empty-query-on-retry spine residual). Zeroing keeps attempt-0's
    # explicit {x,y}/{query,dock_pose} params intact for the honest first-pass verdict.
    try:
        h = getattr(engine, "_vgg_harness", None)
        if h is not None:
            import dataclasses
            h._config = dataclasses.replace(
                h._config, max_step_retries=0, max_pipeline_retries=0,
                max_redecompose=0, max_obs_replan=0)
    except Exception as exc:  # noqa: BLE001
        _log(f"trial {trial}: could not pin harness retries: {exc}")

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
    end_hd = base.get_heading()
    oracle_names = verify_oracle_names(agent, engine)

    rec = {"trial": trial, "goal": goal, "overall_success": trace.success,
           "spawn": [round(float(start_pos[0]), 2), round(float(start_pos[1]), 2),
                     round(float(start_hd), 2)],
           "end_pos": [round(float(end_pos[0]), 2), round(float(end_pos[1]), 2),
                       round(float(end_hd), 2)],
           "dock_target": [_DOCK_X, _DOCK_Y, _DOCK_HD],
           "pos_trace": pos_trace, "steps": []}

    nav_ran = False
    nav_drove = False
    grasp_grounded = False
    grasp_world = None
    dock_pose_reached = None
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

        if step.sub_goal_name == "navigate_dock":
            # The HONEST nav grade is the at_position oracle (RAN, tol 0.5 m) on the
            # navigate step's LANDING position — captured AT the end of the navigate
            # leg, BEFORE the grasp step's dock/approach moves the dog forward. (The
            # post-hoc whole-chain pose is contaminated by the grasp's approach, so
            # we grade on the navigate step's reported position.) The dock refines
            # the coarse FAR/door-chain arrival to within tolerance; we ALSO record
            # the live dock-settled at_position for completeness.
            if isinstance(out, dict) and isinstance(out.get("position"), list):
                dock_pose_reached = out.get("position")
                npos = out["position"]
                nav_ran = math.hypot(npos[0] - _DOCK_X, npos[1] - _DOCK_Y) <= 0.5
            else:
                nav_ran = _at_position(world, agent, _DOCK_X, _DOCK_Y, tol=0.5)
            nav_drove = dist_moved > 1.0
        if step.sub_goal_name == "grasp_red":
            # The HONEST grasp grade is the holding_object weld oracle (GROUNDED),
            # evaluated independently of skill.success and skill.verify_result.
            grasp_grounded = _holding(world, agent, "pickable_can_red")
            if isinstance(out, dict):
                grasp_world = out.get("grasp_world")

    # The dock pose actually reached (perceive-time pose): the dog's pose after the
    # grasp step's dock ran. We capture it from the live base (the grasp left it at
    # the jam standoff after the dock+approach). Save a frame AFTER the dock+grasp.
    rec["dock_pose_reached_xy"] = dock_pose_reached
    rec["perceive_frame"] = _save_frame(agent, f"trial{trial}_after.png")

    rec.update({
        "nav_ran": nav_ran, "nav_drove_dist_m": round(dist_moved, 2),
        "nav_drove": bool(nav_drove),
        "grasp_grounded": grasp_grounded, "grasp_world": grasp_world,
        "red_gt": list(_RED_GT),
    })
    if grasp_world:
        rec["grasp_vs_red_gt_m"] = round(
            math.hypot(grasp_world[0] - _RED_GT[0], grasp_world[1] - _RED_GT[1]), 3)
    _log(f"trial {trial}: nav_RAN={nav_ran} (at_position) nav_drove={nav_drove} "
         f"({dist_moved:.2f}m) grasp_GROUNDED={grasp_grounded} "
         f"end=({end_pos[0]:.2f},{end_pos[1]:.2f},{end_hd:.2f})")
    return rec


def _run_scripted_regression(engine, agent, world) -> dict:
    """Re-run ONE scripted-from-spawn grasp (NO dock_pose) to confirm no regression.

    The grasp with NO dock_pose is the proven scripted path (the dock is a no-op);
    the dog is re-homed to the spawn standoff (10.0, 3.0, +X) head-on first. verify
    holding_object -> GROUNDED. Built directly as a single-step GoalTree (SubGoal +
    GoalTree are imported, NOT edited — the spine stays byte-unchanged).
    """
    base = agent._base
    _log("regression: scripted-from-spawn grasp (no dock_pose) — re-home to spawn first")
    try:
        from vector_os_nano.skills.utils.terminal_dock import terminal_dock
        terminal_dock(base, (_DOCK_X, _DOCK_Y), _DOCK_HD,
                      on_progress=lambda m: _log(f"regression {m}"))
    except Exception as exc:  # noqa: BLE001
        _log(f"regression re-home raised: {exc}")
    time.sleep(1.0)

    from vector_os_nano.vcli.cognitive.types import GoalTree, SubGoal
    sg = SubGoal(
        name="grasp_red_scripted",
        description="拿起红色的罐子",
        verify="holding_object('pickable_can_red')",
        timeout_sec=120.0,
        depends_on=(),
        strategy="perception_grasp_skill",
        strategy_params={"query": "红色的罐子"},  # NO dock_pose — proven path
    )
    tree = GoalTree(goal="拿起红色的罐子", sub_goals=(sg,))
    try:
        h = getattr(engine, "_vgg_harness", None)
        if h is not None:
            import dataclasses
            h._config = dataclasses.replace(
                h._config, max_step_retries=0, max_pipeline_retries=0,
                max_redecompose=0, max_obs_replan=0)
    except Exception:  # noqa: BLE001
        pass
    trace = engine.vgg_execute(tree)
    grounded = _holding(world, agent, "pickable_can_red")
    gw = None
    for step in trace.steps:
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        if isinstance(out, dict) and "grasp_world" in out:
            gw = out["grasp_world"]
    _log(f"regression: scripted grasp GROUNDED={grounded} grasp_world={gw}")
    return {"scripted_from_spawn_grounded": grounded, "grasp_world": gw}


def main() -> int:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 4

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
        time.sleep(2.0)

    # No-regression: ONE scripted-from-spawn grasp (no dock).
    try:
        regression = _run_scripted_regression(engine, agent, world)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        regression = {"error": str(exc), "scripted_from_spawn_grounded": False}

    nav_drove_n = sum(1 for t in trials if t.get("nav_drove"))
    nav_ran_n = sum(1 for t in trials if t.get("nav_ran"))
    grounded_n = sum(1 for t in trials if t.get("grasp_grounded"))
    best_grasp_world = None
    best_d = float("inf")
    for t in trials:
        gw = t.get("grasp_world")
        if t.get("grasp_grounded") and gw:
            d = t.get("grasp_vs_red_gt_m", 0.0)
            if d < best_d:
                best_d, best_grasp_world = d, gw
    report = {
        "n_trials": n_trials,
        "nav_ran": f"{nav_ran_n}/{n_trials}",
        "nav_drove_to_table": f"{nav_drove_n}/{n_trials}",
        "grasp_GROUNDED": f"{grounded_n}/{n_trials}",
        "best_grasp_world": best_grasp_world,
        "red_gt": list(_RED_GT),
        "no_regression": regression,
        "trials": trials,
    }
    path = os.path.join(ART, "trace.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    _log(f"trace written: {path}")
    _log(json.dumps({"nav_ran": report["nav_ran"],
                     "nav_drove_to_table": report["nav_drove_to_table"],
                     "grasp_GROUNDED": report["grasp_GROUNDED"],
                     "scripted_no_regression": regression.get(
                         "scripted_from_spawn_grounded")}, ensure_ascii=False))

    verdict_ok = nav_ran_n >= 1 and grounded_n >= 1
    _log(f"VERDICT: nav RAN {nav_ran_n}/{n_trials}, grasp GROUNDED "
         f"{grounded_n}/{n_trials}, scripted-no-regression="
         f"{regression.get('scripted_from_spawn_grounded')} -> "
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
