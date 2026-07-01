"""Perception-only probe: what does grounding-dino return for the can query?

Root cause under test (D168): a colourless named query "罐子" grasps the WRONG object
(eyes: blue bottle grasped, red can knocked to floor) because _select_detection with
color=None takes plain max-confidence, ignoring the object NOUN. This probe builds the
REAL in-process go2+Piper perception, stows the arm out of view, and prints grounding-dino
boxes (label, score, bbox) for a battery of prompts so we can design a noun-aware selection
+ contrastive prompt WITHOUT guessing grounding-dino's per-box behaviour.

No grasp, no motion — pure detection. ~60-90s. One per subprocess (MuJoCo can't realloc).
"""
from __future__ import annotations
import json, os, sys, time

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ["VECTOR_SIM_WITH_ARM"] = "1"
os.environ["VECTOR_NO_ROS2"] = "1"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)

_STOW_FOR_VIEW = [0.0, 1.2, 0.0, 0.0, 0.0, 0.0]
PROMPTS = ["a can.", "a can. a bottle.", "a red can.", "a can. a bottle. a cylinder.", "罐子"]


def main() -> int:
    res = {"probe": "dino"}
    go2 = piper = gripper = None
    try:
        from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2
        from vector_os_nano.hardware.sim.mujoco_piper import MuJoCoPiper
        from vector_os_nano.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
        from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception

        go2 = MuJoCoGo2(gui=False, room=True, backend="mpc"); go2.connect()
        piper = MuJoCoPiper(go2); piper.connect()
        gripper = MuJoCoPiperGripper(go2); gripper.connect()
        perception = Go2GraspPerception(go2, width=320, height=240)

        # object + dog geometry
        d = go2.get_position()
        objs = piper.get_object_positions()
        res["dog"] = [round(float(d[0]), 2), round(float(d[1]), 2)]
        res["objects"] = {k: [round(float(v[0]), 2), round(float(v[1]), 2), round(float(v[2]), 2)]
                          for k, v in objs.items() if "pickable" in k}

        # stow the arm out of the head-camera FOV (perception_grasp does this first)
        piper.move_joints(_STOW_FOR_VIEW, duration=1.2)
        time.sleep(1.5)

        import vector_os_nano.perception.grounding_dino as gd
        from vector_os_nano.perception.grounding_dino import (
            get_shared_detector, query_to_prompt,
        )
        det = get_shared_detector()
        frame = perception.get_color_frame()

        # 1) what query_to_prompt maps the REAL NL queries to
        res["mapped"] = {q: query_to_prompt(q) for q in ("罐子", "红色的罐子", "瓶子")}

        # 2) grounding-dino output for EXACT prompts (monkeypatch query_to_prompt to
        #    identity so det.detect sends the literal prompt, not the re-mapped one).
        _orig = gd.query_to_prompt
        gd.query_to_prompt = lambda q: q  # type: ignore
        res["detections"] = {}
        try:
            for p in PROMPTS:
                try:
                    dets = det.detect(frame, p)
                    res["detections"][p] = [
                        {"label": getattr(x, "label", "?"),
                         "conf": round(float(getattr(x, "confidence", 0.0)), 3),
                         "bbox": [round(float(b), 1) for b in getattr(x, "bbox", [])]}
                        for x in dets
                    ]
                except Exception as ex:
                    res["detections"][p] = {"error": str(ex)[:160]}
        finally:
            gd.query_to_prompt = _orig  # type: ignore
    except Exception as ex:
        import traceback
        res["error"] = str(ex)[:160]
        res["tb"] = traceback.format_exc()[-500:]
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:
                pass
    print("RESULT " + json.dumps(res, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
