"""ONE skill-direct go2+Piper perception_grasp attempt; prints `RESULT {json}`.

Bypasses the LLM/cli (no routing latency) but runs the REAL mechanism the bare-REPL
native loop invokes: PerceptionGraspSkill.execute({"query": <q>}) -> real Go2GraspPerception
(Moondream detect + EdgeTAM segment + rendered-depth 3D grasp point) -> approach -> weld.
Reads the moat oracle holding_object(<name>) as ground truth and the skill's own result_data
(diagnosis / stage) so we can size the DOMINANT fetch failure mode on the acceptance geometry
(green bottle ~0.88 m ahead of the (10,3) spawn — in perception_grasp self-approach reach).

Usage: python grasp_probe.py [query] [target_name]   (defaults: 绿色的瓶子 / pickable_bottle_green)
Run one per subprocess (MuJoCo can't realloc). ~90-120s/attempt.
"""
from __future__ import annotations
import json, os, sys, time

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ["VECTOR_SIM_WITH_ARM"] = "1"
os.environ["VECTOR_NO_ROS2"] = "1"

ROOT = "/home/yusen/Desktop/vector_os_nano"
sys.path.insert(0, ROOT)

QUERY = sys.argv[1] if len(sys.argv) > 1 else "绿色的瓶子"
TARGET = sys.argv[2] if len(sys.argv) > 2 else "pickable_bottle_green"


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
    res = {"query": QUERY, "target": TARGET}
    go2 = piper = gripper = None
    try:
        from vector_os_nano.core.agent import Agent
        from vector_os_nano.core.scene_graph import SceneGraph
        from vector_os_nano.core.skill import SkillContext
        from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2
        from vector_os_nano.hardware.sim.mujoco_piper import MuJoCoPiper
        from vector_os_nano.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
        from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception
        from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill
        from vector_os_nano.vcli.worlds.arm_sim_oracle import make_holding_object

        go2 = MuJoCoGo2(gui=False, room=True, backend="mpc"); go2.connect()
        piper = MuJoCoPiper(go2); piper.connect()
        gripper = MuJoCoPiperGripper(go2); gripper.connect()
        perception = Go2GraspPerception(go2, width=320, height=240)
        agent = Agent(base=go2, arm=piper, gripper=gripper, perception=perception, config={})
        ctx = SkillContext(arms={"default": piper}, grippers={"default": gripper},
                           bases={"default": go2}, perception_sources={"default": perception},
                           services={"vlm": _StubVLM(), "spatial_memory": SceneGraph()})
        holding = make_holding_object(agent)

        # dog + bottle geometry at start (distance the lone grasp must self-close)
        try:
            d = go2.get_position(); b = piper.get_object_positions().get(TARGET)
            res["dog0"] = [round(float(d[0]), 2), round(float(d[1]), 2)]
            if b is not None:
                res["bottle0"] = [round(float(b[0]), 2), round(float(b[1]), 2), round(float(b[2]), 2)]
                res["dist0"] = round(((float(b[0]) - float(d[0])) ** 2 + (float(b[1]) - float(d[1])) ** 2) ** 0.5, 2)
        except Exception:
            pass

        time.sleep(2.0)
        t0 = time.time()
        gr = PerceptionGraspSkill().execute({"query": QUERY}, ctx)
        res["dur"] = round(time.time() - t0, 1)
        res["skill_success"] = bool(gr.success)
        rd = gr.result_data or {}
        # capture the loud diagnosis fields perception_grasp emits
        for k in ("diagnosis", "perceived", "weld_formed", "approached",
                  "detection_label", "grasp_world", "reperceived", "consumed_bbox"):
            if k in rd:
                res[k] = rd[k]
        res["result_keys"] = sorted(rd.keys())
        res["held"] = bool(holding(TARGET)) if callable(holding) else None
        # where did the dog + bottle end up
        try:
            d = go2.get_position(); b = piper.get_object_positions().get(TARGET)
            res["dog1"] = [round(float(d[0]), 2), round(float(d[1]), 2)]
            if b is not None:
                res["bottle1"] = [round(float(b[0]), 2), round(float(b[1]), 2), round(float(b[2]), 2)]
        except Exception:
            pass
    except Exception as ex:
        import traceback
        res["error"] = str(ex)[:160]
        res["tb"] = traceback.format_exc()[-400:]
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:
                pass
    print("RESULT " + json.dumps(res, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
