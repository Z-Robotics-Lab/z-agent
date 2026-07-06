# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2+arm pick -> place (RELEASE) composition (headless in-process sim).

The standalone-arm pick->place chain is already pinned (test_pick_place_chain.py).
This is the go2+arm (mobile-manipulation) analogue: it proves the honest pick->place
chain composes on the quadruped+Piper rig the bare-cli fetch/place route uses --
perception_grasp lifts the green bottle (weld forms, holding_object True), then
mobile_place RELEASES it (weld breaks, holding_object False).

The release is the honest pick->place primitive: you cannot reach holding_object()
False-after-True without having actually grasped then let go (the GT weld oracle the
actor cannot author). This guards the go2+arm place WIRING end to end (skill
registration, DoF-aware arm, gripper open) the way test_pick_place_chain guards the
standalone arm.

KNOWN GAP (D106, empirically characterised — NOT a wiring bug): `placed_count` (the
frozen place oracle, arm_sim_oracle) credits only objects resting BELOW _LIFT_MIN_Z
(0.10 m, i.e. on the FLOOR). On the go2+Piper at the table that floor-rest is blocked
by TWO real constraints, neither of them an IK-reach limit:
  * ARM<->TABLE COLLISION on descent under load. The collision-free top-down IK DOES
    converge to z=0.10 (fk(q) lands at the commanded low target), but the LIVE loaded
    arm, reaching from the dog's back over the table edge, COLLIDES with the table
    front-top corner (~x=10.80, z=0.28) and stalls at z~0.30 -- it cannot bring the
    held bottle down to the floor in front of the table. So a directed low place
    releases the bottle but it settles back near the table top (z~0.31, placed_count
    stays 0). Verified directly: ee_fk(q)=[10.70,3.00,0.20] vs ee_live=[10.80,2.98,
    0.34], bottle ends z~0.31 (probe, 2026-06-29).
  * FLOOR-ONLY ORACLE SEMANTICS. Even with clear floor, dropping a bottle on the
    ground is the wrong task for tabletop manipulation -- the natural place target is
    a RECEPTACLE at height, which placed_count (z<0.10) structurally cannot credit.
A placed_count-grounded place on a tall mobile manipulator therefore needs a
receptacle-relative resting oracle (a spine semantics change = CEO gate, already
queued), not absolute floor-z. This test asserts only the reachable honest truth
(grasp -> physical release, GT weld breaks); see DECISIONS D106. Direct skill calls
here bypass the planner.
"""
from __future__ import annotations

import os
import time

import pytest

mujoco = pytest.importorskip("mujoco")  # headless sim oracle; skip if unavailable

pytestmark = pytest.mark.sim

_TARGET = "green bottle"
_GT_BODY = "pickable_bottle_green"


class _StubVLM:
    """Names the scene objects without a network call (localization stays real)."""

    def describe_scene(self, frame):
        from zeno.perception.vlm_go2 import (
            DetectedObject, SceneDescription,
        )
        objs = [DetectedObject(name="green bottle", description="", confidence=0.9)]
        return SceneDescription(summary="a bottle on a table", objects=objs,
                                room_type="kitchen", details="")

    def identify_room(self, frame):
        from zeno.perception.vlm_go2 import RoomIdentification
        return RoomIdentification(room="kitchen", confidence=0.9, reasoning="stub")


def test_go2_perception_grasp_then_mobile_place_releases():
    from zeno.core.agent import Agent
    from zeno.core.scene_graph import SceneGraph
    from zeno.core.skill import SkillContext
    from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2
    from zeno.hardware.sim.mujoco_piper import MuJoCoPiper
    from zeno.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
    from zeno.perception.go2_grasp_perception import Go2GraspPerception
    from zeno.skills.mobile_place import MobilePlaceSkill
    from zeno.skills.perception_grasp import PerceptionGraspSkill
    from zeno.vcli.worlds.arm_sim_oracle import make_holding_object

    os.environ["VECTOR_SIM_WITH_ARM"] = "1"  # load the go2+Piper attach scene
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
        time.sleep(2.0)  # settle + warm the detector before the first perceive
        assert holding() is False, "gripper must start empty"

        # 1) perception_grasp -> green bottle lifted + welded (holding_object True)
        gr = PerceptionGraspSkill().execute({"query": _TARGET}, ctx)
        assert gr.success, f"perception_grasp failed: {gr.error_message!r}"
        assert holding() is True, "perception_grasp must leave the green bottle held"

        # 2) mobile_place -> descend in front of the table and RELEASE the held bottle
        #    (weld breaks). skip_navigate: the dog is already seated at the table from
        #    the grasp. The bottle settles near the table top, NOT the floor -- see the
        #    module docstring for the arm<->table collision / floor-only placed_count
        #    gap (D106); placed_count therefore stays 0 here (a CEO-gated oracle change).
        pr = MobilePlaceSkill().execute(
            {"target_xyz": [10.7, 3.0, 0.15], "skip_navigate": True}, ctx,
        )
        assert pr.success, f"mobile_place failed: {pr.error_message!r} ({pr.result_data})"

        # Honest pick->place primitive: the gripper let the object go (GT weld broke).
        # holding() reads the live MuJoCo weld -- an oracle the actor cannot author, so
        # False-after-True can only mean a real grasp followed by a real release.
        assert holding() is False, "mobile_place must release the held object (weld breaks)"
    finally:
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:  # noqa: BLE001
                pass
