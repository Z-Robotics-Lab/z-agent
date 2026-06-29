# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2+arm pick -> place composition (headless in-process sim).

The standalone-arm pick->place chain is already pinned (test_pick_place_chain.py).
This is the go2+arm (mobile-manipulation) analogue: it proves the SAME honest chain
composes on the quadruped+Piper rig the bare-cli NL fetch/place route uses --
perception_grasp lifts the green bottle (weld forms, holding_object True), then
mobile_place releases it onto the FLOOR (weld breaks, holding_object False) and the
bottle ends up moved + resting.

Honest verify (both GT oracles the actor cannot author, arm_sim_oracle):
  * make_holding_object  -> True after grasp, False after place (release).
  * make_placed_count    -> 0 before (all bottles on the table, z=0.32 > lift_min),
                            >=1 after (green now floor-resting, z < _LIFT_MIN_Z 0.10).
The floor drop is what makes placed_count the STRONGER witness: blue/red stay on the
table so a +1 in the floor-rest count can only come from the green bottle we placed.

This is the deterministic composition proof (the D93 analogue for PLACE). It is
NECESSARY but not sufficient -- bare-cli + NL acceptance (the model routing
拿起->放到) is the separate live step. Direct skill calls here bypass the planner.
"""
from __future__ import annotations

import math
import time

import pytest

mujoco = pytest.importorskip("mujoco")  # headless sim oracle; skip if unavailable

pytestmark = pytest.mark.sim

_TARGET = "green bottle"
_GT_BODY = "pickable_bottle_green"


class _StubVLM:
    """Names the scene objects without a network call (localization stays real)."""

    def describe_scene(self, frame):
        from vector_os_nano.perception.vlm_go2 import (
            DetectedObject, SceneDescription,
        )
        objs = [DetectedObject(name="green bottle", description="", confidence=0.9)]
        return SceneDescription(summary="a bottle on a table", objects=objs,
                                room_type="kitchen", details="")

    def identify_room(self, frame):
        from vector_os_nano.perception.vlm_go2 import RoomIdentification
        return RoomIdentification(room="kitchen", confidence=0.9, reasoning="stub")


def _gt_xyz(go2, name):
    model, data = go2._mj.model, go2._mj.data
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
    return [float(v) for v in data.xpos[bid]]


def test_go2_perception_grasp_then_mobile_place_releases_onto_floor():
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
        make_holding_object, make_placed_count,
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
    placed = make_placed_count(agent)

    ctx = SkillContext(
        arms={"default": piper}, grippers={"default": gripper},
        bases={"default": go2}, perception_sources={"default": perception},
        services={"vlm": _StubVLM(), "spatial_memory": SceneGraph()},
    )

    try:
        # Pre-state: nothing held, nothing floor-resting (3 bottles on the table).
        green0 = _gt_xyz(go2, _GT_BODY)
        time.sleep(2.0)  # settle + warm the detector before the first perceive
        assert holding() is False, "gripper must start empty"
        assert placed() == 0, "no object should be floor-resting before the place"

        # 1) perception_grasp -> green bottle lifted + welded (holding_object True)
        gr = PerceptionGraspSkill().execute({"query": _TARGET}, ctx)
        assert gr.success, f"perception_grasp failed: {gr.error_message!r}"
        assert holding() is True, "perception_grasp must leave the green bottle held"

        # 2) mobile_place onto the FLOOR ahead of the dog (skip_navigate: the dog is
        #    already seated at the table from the grasp; place in place). z below
        #    _LIFT_MIN_Z so the dropped bottle counts as floor-resting (placed_count).
        target = [green0[0] - 0.30, green0[1], 0.06]
        pr = MobilePlaceSkill().execute(
            {"target_xyz": target, "skip_navigate": True}, ctx,
        )
        assert pr.success, f"mobile_place failed: {pr.error_message!r} ({pr.result_data})"

        # Honest chain: released, moved, resting on the floor, counted.
        assert holding() is False, "mobile_place must release the held object"
        green1 = _gt_xyz(go2, _GT_BODY)
        moved = math.hypot(green1[0] - green0[0], green1[1] - green0[1])
        assert moved > 0.05, f"placed bottle should have moved (>5cm); moved {moved:.3f}m"
        assert green1[2] < 0.10, f"placed bottle should rest on the floor; z={green1[2]:.3f}"
        assert placed() >= 1, "placed_count oracle must register the floor-rested bottle"
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:  # noqa: BLE001
                pass
