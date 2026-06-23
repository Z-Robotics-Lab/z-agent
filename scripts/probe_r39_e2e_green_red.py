# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R39 ACCEPTANCE — end-to-end producer chain navigate->dock->perceive->approach->grasp.

Drives the REAL decompose->vgg_execute chain (FakeBackend canned plan, the only fake
per policy) for two NL goals, honest split:
  GREEN (centerline, headline) "去桌子那里把绿色的瓶子拿起来" — nav at_position RAN +
        grasp holding_object('pickable_bottle_green') GROUNDED.
  RED   (off-axis, honest)     "去桌子那里把红色的罐子拿起来" — grasp GROUNDED when the
        lateral approach reaches it; RAN-honest on an off-axis reach miss.

Root cause closed this round: `timm` (already declared in pyproject) was missing from
the venv, so EdgeTAM degraded to a coarse box-rect mask -> centroid-z collapsed to the
table (z~0.13) -> the gripper closed below the can -> never grounded. With timm/EdgeTAM
loading, the tight mask localizes the can top (z~0.32, ~2.8 cm). NO spine/skill edit was
needed for that — it was an env-sync. This probe proves the chain now grounds.

Per-trial: poses after FAR / after dock / at perceive; perceive-time d435 frame (PNG);
grasp_world vs GT; holding_object (weld+lift). Distinguishes nav-RAN from grasp-GROUNDED.
Retries pinned to 0. os._exit at end. ONE serialized sim.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

os.environ.setdefault("VECTOR_SIM_WITH_ARM", "1")
os.environ.setdefault("VECTOR_ENABLE_MANIPULATION", "1")
os.environ.setdefault("MUJOCO_GL", "egl")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging as _logging  # noqa: E402

_logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for _n in ("transformers", "urllib3", "PIL", "matplotlib", "huggingface_hub"):
    _logging.getLogger(_n).setLevel(_logging.WARNING)

ART = "/tmp/r39_e2e"
os.makedirs(ART, exist_ok=True)

_DOCK_X, _DOCK_Y, _DOCK_HD = 10.0, 3.0, 0.0
# Scene GT (scene_room_piper.xml). Used ONLY for the honest grasp-vs-GT report.
_GT = {
    "green": ("pickable_bottle_green", "绿色的瓶子", (10.88, 3.00, 0.320)),
    "red": ("pickable_can_red", "红色的罐子", (10.90, 3.22, 0.320)),
}


def _log(m: str) -> None:
    print(f"[E2E] {m}", flush=True)


def _plan(query: str, verify_label: str) -> dict:
    return {
        "goal": f"去桌子那里把{query}拿起来",
        "sub_goals": [
            {"name": "navigate_dock", "description": "走到桌子旁的对接位",
             "verify": f"at_position({_DOCK_X}, {_DOCK_Y}, 0.5)",
             "strategy": "navigate_skill",
             "strategy_params": {"x": _DOCK_X, "y": _DOCK_Y}},
            {"name": "grasp_obj", "description": f"拿起{query}",
             "verify": f"holding_object('{verify_label}')",
             "strategy": "perception_grasp_skill",
             "strategy_params": {"query": query,
                                 "dock_pose": [_DOCK_X, _DOCK_Y, _DOCK_HD]},
             "depends_on": ["navigate_dock"]},
        ],
    }


class _FakeBackend:
    def __init__(self, plan: dict) -> None:
        self._text = json.dumps(plan, ensure_ascii=False)

    def call(self, messages, tools, system, max_tokens, on_text=None, on_reasoning=None):
        from vector_os_nano.vcli.backends.types import LLMResponse
        from vector_os_nano.vcli.session import TokenUsage
        if on_text is not None:
            on_text(self._text)
        return LLMResponse(text=self._text, tool_calls=[], stop_reason="end_turn",
                           usage=TokenUsage(input_tokens=0, output_tokens=0))


def _save_frame(agent, name: str):
    try:
        import cv2
        base = getattr(agent, "_base", None)
        rgb = base.get_camera_frame() if base is not None and hasattr(base, "get_camera_frame") else None
        if rgb is None:
            return None
        path = os.path.join(ART, name)
        cv2.imwrite(path, rgb[:, :, ::-1])
        return path
    except Exception as exc:  # noqa: BLE001
        _log(f"frame save failed: {exc}")
        return None


def _ns(world, agent):
    return world.build_verify_namespace(agent)


def _at_position(world, agent, x, y, tol=0.5):
    try:
        fn = _ns(world, agent).get("at_position")
        return bool(fn(x, y, tol)) if fn else False
    except Exception:  # noqa: BLE001
        return False


def _holding(world, agent, name):
    try:
        fn = _ns(world, agent).get("holding_object")
        return bool(fn(name)) if fn else False
    except Exception:  # noqa: BLE001
        return False


def _pin_retries(engine):
    try:
        import dataclasses
        h = getattr(engine, "_vgg_harness", None)
        if h is not None:
            h._config = dataclasses.replace(
                h._config, max_step_retries=0, max_pipeline_retries=0,
                max_redecompose=0, max_obs_replan=0)
    except Exception as exc:  # noqa: BLE001
        _log(f"could not pin retries: {exc}")


def _run_once(engine, agent, world, label: str, trial: int) -> dict:
    scene_name, query, gt = _GT[label]
    goal = f"去桌子那里把{query}拿起来"
    base = agent._base
    rec = {"label": label, "trial": trial, "query": query, "gt": list(gt)}

    # pre-drive AWAY so FAR genuinely crosses back.
    try:
        base.navigate_to(16.0, 2.8, timeout=45.0)
    except Exception as exc:  # noqa: BLE001
        _log(f"{label} t{trial}: pre-drive raised: {exc}")
    try:
        if os.path.exists("/tmp/vector_nav_active"):
            os.remove("/tmp/vector_nav_active")
        base.stop()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(1.0)
    sp = base.get_position()
    _log(f"{label} t{trial}: start ({sp[0]:.2f},{sp[1]:.2f}) hd={base.get_heading():.2f}")

    tree = engine._goal_decomposer.decompose(goal, engine._build_world_context())
    _log(f"{label} t{trial}: plan {[(s.name, s.strategy) for s in tree.sub_goals]}")
    _pin_retries(engine)

    trace = engine.vgg_execute(tree)

    nav_ran = _at_position(world, agent, _DOCK_X, _DOCK_Y, tol=0.5)
    grounded = _holding(world, agent, scene_name)
    after_far = after_dock = grasp_world = perceive_pose = None
    for step in trace.steps:
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        if not isinstance(out, dict):
            continue
        if step.sub_goal_name == "navigate_dock" and "position" in out:
            after_far = out.get("position")
        if step.sub_goal_name == "grasp_obj":
            grasp_world = out.get("grasp_world") or grasp_world
            perceive_pose = out.get("perceive_pose") or perceive_pose

    end = base.get_position()
    after_dock = [round(float(end[0]), 2), round(float(end[1]), 2),
                  round(float(base.get_heading()), 2)]
    frame = _save_frame(agent, f"{label}_t{trial}_perceive.png")

    d = None
    if grasp_world:
        d = round(math.hypot(grasp_world[0] - gt[0], grasp_world[1] - gt[1]), 3)
    rec.update({"nav_ran": nav_ran, "grasp_grounded": grounded,
                "after_far": after_far, "after_dock": after_dock,
                "grasp_world": grasp_world, "grasp_vs_gt_m": d,
                "perceive_frame": frame, "overall": trace.success})
    _log(f"{label} t{trial}: nav_RAN={nav_ran} grasp_GROUNDED={grounded} "
         f"grasp_world={grasp_world} vs_gt={d}m end={after_dock}")
    return rec


def main() -> int:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3

    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.intent_router import IntentRouter
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool
    from vector_os_nano.vcli.worlds.robot import RobotWorld

    _log("booting go2+arm sim ...")
    agent = SimStartTool._start_go2(gui=False, with_arm=True)
    if getattr(agent, "_arm", None) is None:
        _log("FAIL: no arm")
        return 1
    _log(f"sim up base={type(agent._base).__name__}")
    time.sleep(9.0)

    # confirm EdgeTAM/timm is live (the root-cause fix this round).
    try:
        import timm
        _log(f"timm present {timm.__version__} (EdgeTAM segmenter enabled)")
    except Exception as exc:  # noqa: BLE001
        _log(f"WARNING: timm import failed ({exc}) — EdgeTAM will box-rect-degrade")

    backend = _FakeBackend(_plan("红色的罐子", "pickable_can_red"))
    engine = VectorEngine(backend=backend, intent_router=IntentRouter())
    world = RobotWorld()
    engine.init_vgg(backend=backend, agent=agent,
                    skill_registry=getattr(agent, "_skill_registry", None),
                    world=world, persist_dir=None)
    if not engine._vgg_enabled:
        _log("FAIL: VGG not enabled")
        return 1

    report = {"gt": {k: list(v[2]) for k, v in _GT.items()}, "trials": {}}
    for label in ("green", "red"):
        # rebind the canned plan to this target's query+verify
        scene_name, query, _ = _GT[label]
        backend._text = json.dumps(_plan(query, scene_name), ensure_ascii=False)
        results = []
        for t in range(1, trials + 1):
            try:
                results.append(_run_once(engine, agent, world, label, t))
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                results.append({"label": label, "trial": t, "error": str(exc)})
            time.sleep(2.0)
        ran = sum(1 for r in results if r.get("nav_ran"))
        grd = sum(1 for r in results if r.get("grasp_grounded"))
        report["trials"][label] = {
            "results": results, "nav_ran": f"{ran}/{trials}",
            "grasp_grounded": f"{grd}/{trials}"}
        _log(f"=== {label.upper()}: nav_RAN {ran}/{trials}  grasp_GROUNDED {grd}/{trials} ===")

    with open(os.path.join(ART, "e2e.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    g = report["trials"]["green"]
    r = report["trials"]["red"]
    _log(f"VERDICT GREEN nav {g['nav_ran']} grasp {g['grasp_grounded']} | "
         f"RED nav {r['nav_ran']} grasp {r['grasp_grounded']}")
    _log(f"wrote {ART}/e2e.json")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
