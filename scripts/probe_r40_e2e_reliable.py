# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R40 ACCEPTANCE — nav+grasp RELIABLE (lift GREEN to ~3/4+, land RED honest).

Drives the REAL decompose->vgg_execute chain (FakeBackend canned plan = the only
fake per policy) for two NL goals:
  GREEN (centerline, headline) "去桌子那里把绿色的瓶子拿起来" — target ~3/4+ grasp
        holding_object('pickable_bottle_green') GROUNDED (real weld+lift+oracle).
  RED   (off-axis, honest)     "去桌子那里把红色的罐子拿起来" — honest N/M; red is
        ~75% reach (y=3.22), a reach miss grades RAN not a fake.

R40 fixes under test (all NON-cognitive): (1) colour query routes through the proven
D47 HSV resolver (reliable hue selection among 3 close cans); (2) low-z back-projection
FAIL-LOUD (kills the z-collapse); (3) tighter, repeatable dock convergence (head-on +X,
y re-centered to the centerline).

PERCEIVE-MOMENT FRAME (R39 bug fix): R39 saved the camera frame AFTER the chain finished
(dog back at the doorway). Here we WRAP the perception backend so the RGB + dog pose are
captured at the EXACT perceive moment (the first front_object_mask/get_color_frame during
the grasp), framing the cans — not the post-approach doorway.

Per-trial: after_far / after_dock (heading+y — confirm repeatable head-on); the
perceive-moment frame (PNG, frames the cans); grasp_world (+ z) vs GT; holding_object
(weld+lift+oracle). nav-RAN vs grasp-GROUNDED reported separately. Retries pinned 0.
os._exit at end. ONE serialized sim.
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

ART = "/tmp/r40_e2e"
os.makedirs(ART, exist_ok=True)

_DOCK_X, _DOCK_Y, _DOCK_HD = 10.0, 3.0, 0.0
# Scene GT (scene_room_piper.xml). Used ONLY for the honest grasp-vs-GT report.
_GT = {
    "green": ("pickable_bottle_green", "绿色的瓶子", (10.88, 3.00, 0.320)),
    "red": ("pickable_can_red", "红色的罐子", (10.90, 3.22, 0.320)),
}

# Spawn poses for ALL pickable free-body objects (from scene_room_piper.xml).
# Each entry: body_name -> (x, y, z); identity quaternion (1,0,0,0) is assumed.
_SPAWN_POSES: dict[str, tuple[float, float, float]] = {
    "pickable_bottle_blue":  (10.90, 2.78, 0.320),
    "pickable_bottle_green": (10.88, 3.00, 0.320),
    "pickable_can_red":      (10.90, 3.22, 0.320),
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


class _PerceiveSpy:
    """Wrap the perception backend; capture the RGB + dog pose at the FIRST perceive
    call during a grasp (front_object_mask / detect / get_color_frame). This is the
    REAL perceive-moment framing — not the post-approach doorway frame R39 saved.

    Delegates EVERY attribute to the wrapped backend (so the skill's _REQUIRED_PERCEPTION
    surface is intact); only intercepts the frame-acquiring methods to snapshot once.
    """

    def __init__(self, inner, base, art_path):
        self._inner = inner
        self._base = base
        self._art = art_path
        self._captured = False
        self.perceive_rgb = None
        self.perceive_pose = None

    def _snapshot(self, rgb):
        if self._captured or rgb is None:
            return
        try:
            import cv2
            import numpy as np
            cv2.imwrite(self._art, rgb[:, :, ::-1])
            self.perceive_rgb = self._art
            pos = self._base.get_position()
            hd = float(self._base.get_heading())
            self.perceive_pose = [round(float(pos[0]), 2), round(float(pos[1]), 2),
                                  round(hd, 2)]
            self._captured = True
        except Exception as exc:  # noqa: BLE001
            _log(f"perceive snapshot failed: {exc}")

    def reset(self):
        self._captured = False
        self.perceive_rgb = None
        self.perceive_pose = None

    def get_color_frame(self):
        rgb = self._inner.get_color_frame()
        self._snapshot(rgb)
        return rgb

    def front_object_mask(self, rgb=None, depth=None, *, color=None):
        # Snapshot the frame the resolver actually sees at the perceive moment.
        if rgb is None:
            rgb = self._inner.get_color_frame()
        self._snapshot(rgb)
        return self._inner.front_object_mask(rgb, depth, color=color)

    def detect(self, query):
        # If the named/detector route is taken, still snapshot the live frame.
        self._snapshot(self._inner.get_color_frame())
        return self._inner.detect(query)

    def __getattr__(self, name):
        return getattr(self._inner, name)


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


def _reset_scene_objects(agent) -> None:
    """Release any active weld, reset _held_object, and teleport pickable free-body
    objects back to their spawn poses so trial N cannot inherit trial N-1's state.

    Pause physics around the qpos/qvel write (mirrors _try_grasp in
    mujoco_piper_gripper.py). Degrades gracefully on any surface mismatch — logs
    a WARNING but never crashes the trial.
    """
    # 1. Release the gripper weld + clear held-object.
    try:
        gripper = getattr(agent, "_gripper", None)
        if gripper is not None and callable(getattr(gripper, "open", None)):
            gripper.open()
    except Exception as exc:  # noqa: BLE001
        _log(f"WARNING: gripper.open() failed during reset: {exc}")

    # 2. Teleport pickable free-body objects back to their spawn poses.
    try:
        gripper = getattr(agent, "_gripper", None)
        if gripper is None:
            _log("WARNING: _reset_scene_objects: no agent._gripper — skipping body reset")
            return
        go2 = getattr(gripper, "_go2", None)
        if go2 is None:
            _log("WARNING: _reset_scene_objects: no gripper._go2 — skipping body reset")
            return
        mj_handle = getattr(go2, "_mj", None)
        if mj_handle is None:
            _log("WARNING: _reset_scene_objects: no go2._mj — skipping body reset")
            return

        import mujoco as _mujoco_mod  # noqa: PLC0415
        import numpy as _np  # noqa: PLC0415
        model = mj_handle.model
        data = mj_handle.data

        pause = getattr(go2, "_pause_physics", None)
        resume = getattr(go2, "_resume_physics", None)
        if pause:
            pause()
        try:
            for body_name, (sx, sy, sz) in _SPAWN_POSES.items():
                bid = _mujoco_mod.mj_name2id(model, _mujoco_mod.mjtObj.mjOBJ_BODY, body_name)
                if bid < 0:
                    _log(f"WARNING: _reset_scene_objects: body '{body_name}' not in model")
                    continue
                jadr = int(model.body_jntadr[bid])
                if jadr < 0:
                    _log(f"WARNING: _reset_scene_objects: body '{body_name}' has no joint")
                    continue
                if model.jnt_type[jadr] != _mujoco_mod.mjtJoint.mjJNT_FREE:
                    _log(f"WARNING: _reset_scene_objects: body '{body_name}' joint is not FREE")
                    continue
                qpos_adr = int(model.jnt_qposadr[jadr])
                dof_adr = int(model.jnt_dofadr[jadr])
                # 7-float free-joint qpos: x y z qw qx qy qz
                data.qpos[qpos_adr:qpos_adr + 3] = [sx, sy, sz]
                data.qpos[qpos_adr + 3] = 1.0  # qw
                data.qpos[qpos_adr + 4] = 0.0  # qx
                data.qpos[qpos_adr + 5] = 0.0  # qy
                data.qpos[qpos_adr + 6] = 0.0  # qz
                # 6-float free-joint qvel: vx vy vz wx wy wz
                data.qvel[dof_adr:dof_adr + 6] = _np.zeros(6)
                _log(f"reset '{body_name}' -> ({sx},{sy},{sz})")
        finally:
            if resume:
                resume()
    except Exception as exc:  # noqa: BLE001
        _log(f"WARNING: _reset_scene_objects body reset failed: {exc}")


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


def _run_once(engine, agent, world, spy, label: str, trial: int) -> dict:
    scene_name, query, gt = _GT[label]
    goal = f"去桌子那里把{query}拿起来"
    base = agent._base
    rec = {"label": label, "trial": trial, "query": query, "gt": list(gt)}
    spy.reset()

    # TRIAL ISOLATION: release any weld + reset all pickable objects to spawn
    # poses BEFORE the pre-drive so trial N cannot inherit trial N-1's hold.
    _reset_scene_objects(agent)

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
    holding_oracle = _holding(world, agent, scene_name)
    after_far = grasp_world = diagnosis = None
    for step in trace.steps:
        out = step.result_data.get("output", {}) if isinstance(step.result_data, dict) else {}
        if not isinstance(out, dict):
            continue
        if step.sub_goal_name == "navigate_dock" and "position" in out:
            after_far = out.get("position")
        if step.sub_goal_name == "grasp_obj":
            grasp_world = out.get("grasp_world") or grasp_world
            diagnosis = out.get("diagnosis") or diagnosis

    end = base.get_position()
    after_dock = [round(float(end[0]), 2), round(float(end[1]), 2),
                  round(float(base.get_heading()), 2)]

    # HONEST grounded: requires BOTH a real perceived grasp point THIS trial AND
    # the oracle confirming weld+lift+near-EE.  grasp_world=None (no perception
    # ran / failed) with a stale oracle=True is NOT grounded.
    grounded = bool(grasp_world) and holding_oracle

    d = gz = None
    if grasp_world:
        d = round(math.hypot(grasp_world[0] - gt[0], grasp_world[1] - gt[1]), 3)
        gz = round(float(grasp_world[2]), 3)
    rec.update({"nav_ran": nav_ran,
                "holding_oracle": holding_oracle,
                "grasp_grounded": grounded,
                "after_far": after_far, "after_dock": after_dock,
                "perceive_pose": spy.perceive_pose,
                "perceive_frame": spy.perceive_rgb,
                "grasp_world": grasp_world, "grasp_z": gz, "grasp_vs_gt_m": d,
                "diagnosis": diagnosis, "overall": trace.success})
    _log(f"{label} t{trial}: nav_RAN={nav_ran} holding_oracle={holding_oracle} "
         f"grasp_GROUNDED={grounded} "
         f"after_dock(hd,y)={after_dock} perceive_pose={spy.perceive_pose} "
         f"grasp_world={grasp_world} z={gz} vs_gt={d}m diag={diagnosis}")
    return rec


def main() -> int:
    trials_green = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    trials_red = int(sys.argv[2]) if len(sys.argv) > 2 else 3

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

    try:
        import timm
        _log(f"timm present {timm.__version__} (EdgeTAM segmenter enabled)")
    except Exception as exc:  # noqa: BLE001
        _log(f"WARNING: timm import failed ({exc}) — EdgeTAM will box-rect-degrade")

    # WRAP the perception backend so the perceive-moment frame+pose are captured.
    inner_perc = getattr(agent, "_perception", None)
    spy = None
    if inner_perc is not None:
        spy = _PerceiveSpy(inner_perc, agent._base, os.path.join(ART, "_perceive.png"))
        agent._perception = spy
        _log(f"wrapped perception {type(inner_perc).__name__} with perceive-moment spy")
    else:
        _log("WARNING: no agent._perception to wrap — perceive frame unavailable")

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
    plan = (("green", trials_green), ("red", trials_red))
    for label, trials in plan:
        scene_name, query, _ = _GT[label]
        backend._text = json.dumps(_plan(query, scene_name), ensure_ascii=False)
        results = []
        for t in range(1, trials + 1):
            try:
                rec = _run_once(engine, agent, world, spy, label, t)
                # per-trial frame: copy the captured perceive frame to a named file
                if rec.get("perceive_frame") and os.path.exists(rec["perceive_frame"]):
                    import shutil
                    named = os.path.join(ART, f"{label}_t{t}_perceive.png")
                    shutil.copy(rec["perceive_frame"], named)
                    rec["perceive_frame"] = named
                results.append(rec)
            except Exception as exc:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                results.append({"label": label, "trial": t, "error": str(exc)})

            # INCREMENTAL WRITE — flush completed-trial data immediately so a
            # timeout never loses it.  Update the running fractions too.
            ran_so_far = sum(1 for r in results if r.get("nav_ran"))
            grd_so_far = sum(1 for r in results if r.get("grasp_grounded"))
            report["trials"][label] = {
                "results": results,
                "nav_ran": f"{ran_so_far}/{trials}",
                "grasp_grounded": f"{grd_so_far}/{trials}",
            }
            try:
                with open(os.path.join(ART, "e2e.json"), "w") as _fh:
                    json.dump(report, _fh, indent=2)
            except Exception as _exc:  # noqa: BLE001
                _log(f"WARNING: incremental e2e.json write failed: {_exc}")

            time.sleep(2.0)
        ran = sum(1 for r in results if r.get("nav_ran"))
        grd = sum(1 for r in results if r.get("grasp_grounded"))
        # Final update for this label with the definitive fractions.
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
