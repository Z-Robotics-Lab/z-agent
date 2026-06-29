# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MULTI-OBJECT SEQUENTIAL FETCH seal — the native producer composes TWO grasps.

``test_native_loop_grasp_attach_pty.py`` seals the SINGLE in-reach grasp on the
go2+Piper attach scene. This module is its multi-object analogue: the first
composed PHYSICAL task — fetch TWO named objects one at a time, proving the
North-Star thesis that the model composes verifiable building-block tools IN
SEQUENCE (not just routes one). The honest sequence, on ONE gripper:

    [抓绿色的瓶子] -> verify(holding_object('pickable_bottle_green'))  GROUNDED+CAUSED
    [gripper_open]                                       (RELEASE the green weld)
    [抓蓝色的瓶子] -> verify(holding_object('pickable_bottle_blue'))   GROUNDED+CAUSED
    finish

Why this is an HONEST multi-object proof (no spine change, nothing loosened):
  - ONE gripper holds ONE object — so the second weld (blue, 0->1) can form ONLY
    if ``gripper_open`` actually RELEASED the green weld (open() breaks the weld,
    mujoco_piper_gripper.open). A still-held green would block the blue grasp, so
    step-1 GROUNDED+CAUSED is itself the proof the release worked.
  - The frozen ``evidence_passed`` requires ALL checked steps GROUNDED, but it does
    NOT know the user asked for TWO objects — so the MULTI-OBJECT success criterion
    (a GROUNDED ``holding_object`` step for EACH named object) is asserted HERE, in
    the test, not auto-graded by the spine. The set of GROUNDED targets must equal
    {green, blue} — a green-only completion (one GROUNDED step) FAILS this seal.

A scripted ``FakeToolScriptBackend`` replays the (action -> verify) pairs so the
test is NETWORK-FREE (no live deepseek), but BOTH grasps run the FULL real
pipeline on a real ``MuJoCoGo2`` + ``MuJoCoPiper`` + ``MuJoCoPiperGripper`` —
VLM/colour resolve -> EdgeTAM segment -> rendered-depth pointcloud -> 3D grasp
point (never GT) -> approach -> Piper top-down IK -> weld -> lift -> release ->
re-perceive+approach+weld the second — graded by the UNTOUCHED honest spine.

The LIVE-model lever that gets the producer to EMIT this sequence (multi-object
prompt guidance in native_loop._build_system_prompt) is verified separately
through bare ``vector-cli`` + NL + the eyes harness; this seal pins the spine
gradability + physical feasibility deterministically.

Both bottles sit in-reach + adjacent on the near pick table (blue 10.90,2.78 ·
green 10.88,3.00; dog spawns ~x=9), NOT the gated far regime. Reproduce::

    MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python -m pytest \\
      tests/vcli/test_native_loop_multi_object_fetch_pty.py -v -s -m sim
"""
from __future__ import annotations

import os

# Select the go2_piper attach scene (cylinders + INACTIVE welds) at scene-build
# time — MuJoCoGo2._build_room_scene_xml reads this env var. MUST precede import.
os.environ.setdefault("VECTOR_SIM_WITH_ARM", "1")

import subprocess

import pytest

pytest.importorskip("mujoco")

# Two distinct in-reach colour queries -> classical HSV front_object resolver (no
# network); each resolves the verify LABEL to its bottle's canonical scene name.
_GREEN_QUERY: str = "抓绿色的瓶子"
_GREEN_TARGET: str = "pickable_bottle_green"
_BLUE_QUERY: str = "抓蓝色的瓶子"
_BLUE_TARGET: str = "pickable_bottle_blue"
# The NL goal names BOTH objects (都 = "both") -> grasp intent -> the D69 object-goal
# turn gate applies; the turn passes only via NECESSARY holding_object conjuncts.
_GOAL: str = "把绿色和蓝色的瓶子都拿过来"


def _nuke() -> None:
    try:
        subprocess.run(["rosm", "nuke", "--yes"], timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture()
def sim_cleanup():
    yield
    _nuke()


@pytest.mark.sim
def test_native_multi_object_fetch_grounds_both_welds(sim_cleanup) -> None:
    """Two sequential perception_grasps (green then blue) BOTH ground holding_object.

    Mirrors the single-grasp seal but composes the grasp TWICE around a
    ``gripper_open`` release, sealing the first multi-object physical task: the
    set of GROUNDED ``holding_object`` targets must equal {green, blue}, each a
    real GT weld 0->1 the actor caused, graded by the untouched spine.
    """
    os.environ["VECTOR_SIM_WITH_ARM"] = "1"

    from pathlib import Path as _Path

    from vector_os_nano.core.agent import Agent
    from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2
    from vector_os_nano.hardware.sim.mujoco_piper import MuJoCoPiper
    from vector_os_nano.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
    from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception
    from vector_os_nano.skills.go2 import get_go2_skills
    from vector_os_nano.skills.gripper import GripperOpenSkill
    from vector_os_nano.skills.mobile_pick import MobilePickSkill
    from vector_os_nano.skills.mobile_place import MobilePlaceSkill
    from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill
    from vector_os_nano.skills.pick_top_down import PickTopDownSkill
    from vector_os_nano.skills.place_top_down import PlaceTopDownSkill
    from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused
    from vector_os_nano.vcli.cognitive.trace_store import (
        classify_step_evidence,
        evidence_passed,
        verify_oracle_names,
    )
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.permissions import PermissionContext
    from vector_os_nano.vcli.session import Session
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
    from vector_os_nano.vcli.verdict import VerdictReport
    from vector_os_nano.vcli.worlds.arm_sim_oracle import make_holding_object
    from vector_os_nano.vcli.worlds.robot import RobotWorld

    from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn

    go2 = MuJoCoGo2(gui=False, room=True, backend="mpc")
    go2.connect()
    piper = gripper = None
    try:
        piper = MuJoCoPiper(go2)
        piper.connect()
        gripper = MuJoCoPiperGripper(go2)
        gripper.connect()
        perception = Go2GraspPerception(go2, width=320, height=240)
        agent = Agent(base=go2, arm=piper, gripper=gripper, perception=perception, config={})

        for s in get_go2_skills():
            agent._skill_registry.register(s)
        for sk in (PickTopDownSkill(), PlaceTopDownSkill(), MobilePickSkill(),
                   MobilePlaceSkill(), GripperOpenSkill()):
            agent._skill_registry.register(sk)
        agent._skill_registry.register(PerceptionGraspSkill())

        # Boot NOT holding -> each weld 0->1 is a genuine actor-CAUSED transition.
        assert make_holding_object(agent)() is False, (
            "the go2+Piper rig must boot NOT holding so each grasp is genuinely caused"
        )

        backend = FakeToolScriptBackend.from_tool_script([
            tool_turn(("perception_grasp", {"query": _GREEN_QUERY})),
            tool_turn(("verify", {"expr": f"holding_object('{_GREEN_TARGET}')"})),
            # RELEASE the green weld so the single gripper is free for the blue grasp.
            tool_turn(("gripper_open", {})),
            # RETREAT to a perceiving standoff before the next grasp: the first grasp
            # leaves the dog DOCKED close to the table (x~10.46), where NO table object
            # is in the camera FOV (probed: both bottles -> 0 px at x=10.46, but ~490 px
            # at the x~9.7 standoff). Backing off ~0.8 m restores visibility so the next
            # perception_grasp can perceive + self-approach its target.
            tool_turn(("walk", {"direction": "backward", "distance": 1.0})),
            tool_turn(("perception_grasp", {"query": _BLUE_QUERY})),
            tool_turn(("verify", {"expr": f"holding_object('{_BLUE_TARGET}')"})),
            tool_turn(end=True),
        ])
        eng = VectorEngine(
            backend=backend, registry=CategorizedToolRegistry(),
            permissions=PermissionContext(),
        )
        eng._world = RobotWorld()
        eng.init_vgg(agent=agent, skill_registry=agent._skill_registry, world=RobotWorld())
        eng._vgg_agent = agent
        eng._backend = backend

        session = Session(
            session_id="native-multi-fetch", created_at="t", updated_at="t",
            path=_Path("/tmp/native_multi_object_fetch.jsonl"),
        )
        trace = eng.run_turn_native(_GOAL, session=session)

        # TWO StepRecords — one per (grasp -> holding_object) pair; the gripper_open
        # release is an action absorbed into step-1 (strategy = the last action,
        # perception_grasp), so it does not add a third verified step.
        assert len(trace.steps) == 2, (
            f"expected 2 native steps (green grasp, blue grasp); got {len(trace.steps)}: "
            f"{[(s.strategy, sg.verify) for s, sg in zip(trace.steps, trace.goal_tree.sub_goals)]}"
        )

        names = verify_oracle_names(agent, eng)
        grounded_targets: set[str] = set()
        for step, sub in zip(trace.steps, trace.goal_tree.sub_goals):
            # ROUTING — each producing skill is the perception-first grasp.
            assert step.strategy == "perception_grasp", (
                f"step strategy must be perception_grasp; got {step.strategy!r}"
            )
            # PREDICATE — the target-aware GRIPPER oracle.
            assert sub.verify.startswith("holding_object"), f"verify={sub.verify!r}"
            # GROUNDING — a real perceived grasp lifted + welded the named bottle.
            assert step.verify_result is True, (
                f"grasp should leave holding_object True; "
                f"result_data={getattr(step, 'result_data', None)} verify={sub.verify!r}"
            )
            # CAUSATION — a fresh weld 0->1 (for the BLUE step this also proves the
            # green weld was RELEASED, else the single gripper could not weld blue).
            assert step.actor_caused is ActorCaused.CAUSED, (
                f"grasp must grade CAUSED (fresh weld 0->1); got {step.actor_caused.value} "
                f"for verify={sub.verify!r}"
            )
            assert classify_step_evidence(step, sub, names) == "GROUNDED"
            grounded_targets.add(sub.verify)

        # MULTI-OBJECT CRITERION — BOTH named objects grasped (the seal's core claim;
        # a single-object completion would ground only one target and FAIL here).
        assert grounded_targets == {
            f"holding_object('{_GREEN_TARGET}')",
            f"holding_object('{_BLUE_TARGET}')",
        }, f"both green AND blue must be grounded; got {grounded_targets}"

        # The frozen verdict gate: all checked steps GROUNDED -> verified.
        report = VerdictReport.from_trace(trace, names)
        assert report.verified is True, f"both grounded grasps must verify; {report.evidence}"
        assert report.evidence == "GROUNDED"
        assert report.exit_code() == 0
        # D69 object-goal turn gate: grasp intent + holding_object oracle exposed.
        assert evidence_passed(trace, names) is True
    finally:
        for dev in (gripper, piper, go2):
            if dev is None:
                continue
            try:
                dev.disconnect()
            except Exception:  # noqa: BLE001
                pass
        _nuke()
