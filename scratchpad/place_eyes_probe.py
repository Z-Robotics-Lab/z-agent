"""Offline eyes-frame probe (no LLM) — render the verdict-hook snapshot at BOTH the
grasp state and the placed state, using the EXACT same mechanism the bare-REPL fires
(capture.snapshot_on_verdict). Answers D169's open question: is the placement eyes frame
visually conclusive, or does it look grasp-like?

Runs the REAL skill mechanism (perception_grasp weld + mobile_place full nav+dock+drop),
so the placed state is genuine (resting_on_receptacle GT True), then snapshots. NO qwen /
DashScope call anywhere — usable while the acceptance-face LLM billing is blocked.

Writes /tmp/place_eyes/eyes_grasp.png and eyes_place.png + prints RESULT {json}.
Run one per subprocess (MuJoCo can't realloc).
"""
from __future__ import annotations
import json, os, shutil, sys, time

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ["VECTOR_SIM_WITH_ARM"] = "1"
os.environ["VECTOR_NO_ROS2"] = "1"

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)
OUT = "/tmp/place_eyes"
os.makedirs(OUT, exist_ok=True)


class _StubVLM:
    def describe_scene(self, frame):
        from vector_os_nano.perception.vlm_go2 import DetectedObject, SceneDescription
        return SceneDescription(summary="a bottle on a table",
                                objects=[DetectedObject(name="green bottle", description="", confidence=0.9)],
                                room_type="kitchen", details="")

    def identify_room(self, frame):
        from vector_os_nano.perception.vlm_go2 import RoomIdentification
        return RoomIdentification(room="kitchen", confidence=0.9, reasoning="stub")


def _snap(agent, tag: str) -> str | None:
    """Fire the REAL verdict-hook snapshot then copy the newest verdict_*.png to a stable name."""
    from vector_os_nano.acceptance import capture
    os.environ["VECTOR_SNAPSHOT_DIR"] = OUT
    path = capture.snapshot_on_verdict(agent)
    if not path or not os.path.exists(path):
        return None
    dst = os.path.join(OUT, f"eyes_{tag}.png")
    shutil.copyfile(path, dst)
    return dst


def main() -> int:
    res: dict = {}
    go2 = piper = gripper = None
    try:
        from vector_os_nano.core.agent import Agent
        from vector_os_nano.core.scene_graph import SceneGraph
        from vector_os_nano.core.skill import SkillContext
        from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2
        from vector_os_nano.hardware.sim.mujoco_piper import MuJoCoPiper
        from vector_os_nano.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
        from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception
        from vector_os_nano.skills.mobile_place import MobilePlaceSkill
        from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill
        from vector_os_nano.vcli.worlds.arm_sim_oracle import (
            make_holding_object, make_resting_on_receptacle,
        )
        from vector_os_nano.vcli.worlds.robot import _place_receptacle_extent

        go2 = MuJoCoGo2(gui=False, room=True, backend="mpc"); go2.connect()
        piper = MuJoCoPiper(go2); piper.connect()
        gripper = MuJoCoPiperGripper(go2); gripper.connect()
        perception = Go2GraspPerception(go2, width=320, height=240)
        agent = Agent(base=go2, arm=piper, gripper=gripper, perception=perception, config={})
        ctx = SkillContext(arms={"default": piper}, grippers={"default": gripper},
                           bases={"default": go2}, perception_sources={"default": perception},
                           services={"vlm": _StubVLM(), "spatial_memory": SceneGraph()})
        holding = make_holding_object(agent)
        region, rest_z = _place_receptacle_extent(agent)
        resting = make_resting_on_receptacle(agent, region, rest_z)

        time.sleep(2.0)
        gr = PerceptionGraspSkill().execute({"query": "green bottle"}, ctx)
        res["grasp_ok"] = bool(gr.success and holding())
        if not res["grasp_ok"]:
            res["fail"] = "grasp"; print("RESULT " + json.dumps(res), flush=True); return 0
        res["eyes_grasp"] = _snap(agent, "grasp")  # frame WHILE holding, pre-place

        pr = MobilePlaceSkill().execute({}, ctx)
        res["place_success"] = bool(pr.success)
        res["resting"] = int(resting())
        time.sleep(2.0); res["resting_t2"] = int(resting())
        res["eyes_place"] = _snap(agent, "place")  # frame at the placed / resting state
        try:
            objs = piper.get_object_positions()
            b = objs.get("pickable_bottle_green") or objs.get("green bottle")
            if b is not None:
                res["bottle"] = [round(float(b[0]), 3), round(float(b[1]), 3), round(float(b[2]), 3)]
        except Exception:
            pass
    except Exception as ex:
        import traceback
        res["error"] = str(ex)[:120]
        res["tb"] = traceback.format_exc()[-300:]
    finally:
        for h in (gripper, piper, go2):
            try:
                h and h.disconnect()
            except Exception:
                pass
    print("RESULT " + json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
