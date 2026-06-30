"""ONE skill-direct go2+Piper PICK->PLACE attempt; prints `RESULT {json}`.

Bypasses the LLM/cli (no routing latency) but runs the REAL mechanism: perception_grasp
welds the green bottle, then mobile_place does the FULL nav-to-bin + dock + drop. Reads the
moat oracle resting_on_receptacle + the green bottle's final xyz + the post-dock geometry side
file. This sizes the two place failure modes (nav/dock vs drop roll-off) and the miss magnitude
fast (~100-150s/attempt vs ~420s for the cli). Run one per subprocess (MuJoCo can't realloc).
"""
from __future__ import annotations
import json, os, sys, time

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ["VECTOR_SIM_WITH_ARM"] = "1"
os.environ["VECTOR_NO_ROS2"] = "1"

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)


class _StubVLM:
    def describe_scene(self, frame):
        from vector_os_nano.perception.vlm_go2 import DetectedObject, SceneDescription
        return SceneDescription(summary="a bottle on a table",
                                objects=[DetectedObject(name="green bottle", description="", confidence=0.9)],
                                room_type="kitchen", details="")

    def identify_room(self, frame):
        from vector_os_nano.perception.vlm_go2 import RoomIdentification
        return RoomIdentification(room="kitchen", confidence=0.9, reasoning="stub")


def main() -> int:
    res = {}
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
        rcp = _place_receptacle_extent(agent)
        region, rest_z = rcp
        resting = make_resting_on_receptacle(agent, region, rest_z)
        res["region"] = [round(v, 3) for v in region]
        res["rest_z"] = round(rest_z, 3)

        time.sleep(2.0)
        # 1) grasp
        gr = PerceptionGraspSkill().execute({"query": "green bottle"}, ctx)
        res["grasp_ok"] = bool(gr.success and holding())
        if not res["grasp_ok"]:
            res["fail"] = "grasp"; print("RESULT " + json.dumps(res), flush=True); return 0
        # 2) place — FULL nav-to-bin + dock + drop (no skip_navigate, no target = scene bin)
        pr = MobilePlaceSkill().execute({}, ctx)
        res["place_success"] = bool(pr.success)
        res["diag"] = (pr.result_data or {}).get("diagnosis", "?")
        res["resting"] = int(resting())
        # velocity at verdict + re-poll resting after extra settle (is it a settling-time issue?)
        try:
            vels = piper.get_object_velocities()
            v = vels.get("pickable_bottle_green") or vels.get("green bottle")
            if v is not None:
                sp = (float(v[0])**2 + float(v[1])**2 + float(v[2])**2) ** 0.5
                res["bottle_speed"] = round(sp, 4)
        except Exception:
            pass
        res["held_after"] = bool(holding())
        time.sleep(2.0); res["resting_t2"] = int(resting())
        time.sleep(2.0); res["resting_t4"] = int(resting())
        # 3) where did the green bottle end up + dog/ee final
        try:
            objs = piper.get_object_positions()
            b = objs.get("pickable_bottle_green") or objs.get("green bottle")
            if b is not None:
                bx, by, bz = float(b[0]), float(b[1]), float(b[2])
                res["bottle"] = [round(bx, 3), round(by, 3), round(bz, 3)]
                x0, y0, x1, y1 = region
                res["bottle_in_region"] = bool(x0 < bx < x1 and y0 < by < y1)
                res["bottle_dz"] = round(bz - rest_z, 3)
        except Exception as ex:
            res["bottle_err"] = str(ex)[:50]
        try:
            dog = go2.get_position()
            res["dog"] = [round(float(dog[0]), 3), round(float(dog[1]), 3)]
        except Exception:
            pass
    except Exception as ex:
        import traceback
        res["error"] = str(ex)[:120]
        res["tb"] = traceback.format_exc()[-300:]
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:
                pass
    print("RESULT " + json.dumps(res), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
