# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R256/E60 regression: the courtyard PLACE *machinery* is sound.

Root-cause round R256 refuted the "mid-walk drop" framing: in-process (no brain) the grasp
weld holds the object through mobile_place's walk+dock, and the full place leaves the object
RESTING on the courtyard bin with the gripper empty. The real R255 failure was a BRAIN
post-place mis-recovery (it re-grasped the just-placed object), not a physics drop.

This test locks the machinery invariant so any future "掉了" is provably a brain misread:
after perception_grasp + mobile_place (auto-resolve), resting_on_receptacle()==1 and the
gripper is empty. Spawns a MuJoCo sim -> run via scripts/run-tests (memory-capped).
"""
from __future__ import annotations

import os
import time

import pytest

_TARGET = "green bottle"


class _StubVLM:
    def query(self, *_a, **_k):
        return {"answer": "yes", "confidence": 1.0}

    def describe(self, *_a, **_k):
        return "a green bottle on a table"


@pytest.mark.integration
def test_go2_courtyard_place_leaves_object_resting_no_midwalk_drop():
    os.environ["VECTOR_SIM_WITH_ARM"] = "1"
    os.environ["VECTOR_ROOM_TEMPLATE"] = "courtyard"

    from zeno.core.agent import Agent
    from zeno.core.scene_graph import SceneGraph
    from zeno.core.skill import SkillContext
    from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2
    from zeno.hardware.sim.mujoco_piper import MuJoCoPiper
    from zeno.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
    from zeno.perception.go2_grasp_perception import Go2GraspPerception
    from zeno.skills.mobile_place import MobilePlaceSkill, _scene_place_geom
    from zeno.skills.perception_grasp import PerceptionGraspSkill
    from zeno.vcli.worlds.arm_sim_oracle import (
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
    try:
        time.sleep(2.0)
        gr = PerceptionGraspSkill().execute({"query": _TARGET}, ctx)
        assert gr.success, f"perception_grasp failed: {gr.error_message!r}"
        assert holding() is True, "grasp must leave the green bottle held"

        geom = _scene_place_geom(go2)
        resting = make_resting_on_receptacle(agent, geom[3], float(geom[2]))

        # FULL real place: auto-resolve the scene bin, real nav + dock + drop-release.
        pr = MobilePlaceSkill().execute({}, ctx)
        assert pr.success, f"mobile_place failed: {pr.error_message!r} ({pr.result_data})"
        # The place empties the gripper BY DESIGN (this is success, not a drop) ...
        assert holding() is False, "a successful place must release the object"
        # ... and the object RESTS on the receptacle — no mid-walk drop, no roll-off.
        assert int(resting()) == 1, "the placed bottle must rest ON the courtyard bin"
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:  # noqa: BLE001
                pass
