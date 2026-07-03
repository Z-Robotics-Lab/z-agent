#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""DEBUG R256/E60 — run the FULL MobilePlaceSkill in-process (courtyard) and read the
GT verdict oracles. No brain/VLM. Tells apart the real failure branch:
  - drop-release happened but object did NOT rest on the receptacle (roll-off) -> resting=0
  - object_lost_in_transport / dock_off_receptacle diagnosis
Prints DIAG_SUMMARY= JSON.
"""
from __future__ import annotations

import json
import os
import time

_TARGET = "green bottle"


class _StubVLM:
    def query(self, *_a, **_k):
        return {"answer": "yes", "confidence": 1.0}

    def describe(self, *_a, **_k):
        return "a green bottle on a table"


def main() -> int:
    os.environ["VECTOR_SIM_WITH_ARM"] = "1"
    os.environ.setdefault("VECTOR_ROOM_TEMPLATE", "courtyard")

    from vector_os_nano.core.agent import Agent
    from vector_os_nano.core.scene_graph import SceneGraph
    from vector_os_nano.core.skill import SkillContext
    from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2
    from vector_os_nano.hardware.sim.mujoco_piper import MuJoCoPiper
    from vector_os_nano.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
    from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception
    from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill
    from vector_os_nano.skills.mobile_place import MobilePlaceSkill, _scene_place_geom
    from vector_os_nano.vcli.worlds.arm_sim_oracle import (
        make_holding_object, make_resting_on_receptacle,
    )

    go2 = MuJoCoGo2(gui=False, room=True, backend="mpc")
    go2.connect()
    piper = MuJoCoPiper(go2)
    piper.connect()
    gripper = MuJoCoPiperGripper(go2)
    gripper.connect()
    perception = Go2GraspPerception(go2, width=320, height=240)
    agent = Agent(base=go2, arm=piper, gripper=gripper, perception=perception, config={})
    holding = make_holding_object(agent)
    ctx = SkillContext(
        arms={"default": piper}, grippers={"default": gripper},
        bases={"default": go2}, perception_sources={"default": perception},
        services={"vlm": _StubVLM(), "spatial_memory": SceneGraph()},
    )
    result = {"template": os.environ.get("VECTOR_ROOM_TEMPLATE")}
    try:
        time.sleep(2.0)
        gr = PerceptionGraspSkill().execute({"query": _TARGET}, ctx)
        result["grasp_success"] = bool(gr.success)
        result["grasp_holding_object"] = bool(holding())
        if not (gr.success and holding()):
            result["abort"] = f"grasp failed: {gr.error_message!r}"
            print("DIAG_SUMMARY=" + json.dumps(result, ensure_ascii=False))
            return 2

        geom = _scene_place_geom(go2)
        resting = make_resting_on_receptacle(agent, geom[3], float(geom[2]))
        result["place_geom"] = [round(float(v), 3) for v in geom[:3]]

        # FULL real place: auto-resolve the scene place_bin, real nav + dock + drop-release.
        pr = MobilePlaceSkill().execute({}, ctx)
        result["place_success"] = bool(pr.success)
        result["place_diagnosis"] = (pr.result_data or {}).get("diagnosis")
        result["place_error"] = pr.error_message
        result["holding_object_after"] = bool(holding())
        try:
            result["resting_on_receptacle_after"] = int(resting())
        except Exception as exc:  # noqa: BLE001
            result["resting_on_receptacle_after"] = f"err:{exc}"
        # where did the bottle end up?
        try:
            objs = piper.get_object_positions() or {}
            gb = objs.get("pickable_bottle_green") or objs.get("bottle_green")
            if gb is None and objs:
                gb = list(objs.values())[0]
            result["green_final_xyz"] = [round(float(c), 3) for c in gb] if gb else None
        except Exception as exc:  # noqa: BLE001
            result["green_final_xyz"] = f"err:{exc}"
        print("DIAG_SUMMARY=" + json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
