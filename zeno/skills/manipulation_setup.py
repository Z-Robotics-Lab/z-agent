# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Single-source go2+arm manipulation wiring.

Both go2+arm launch paths register the SAME Piper manipulation skill set and the
perception-grasp pipeline:

  * the lightweight in-process ``--sim-go2`` flag path (``vcli/cli.py``), and
  * the ROS2 natural-language path (``vcli/tools/sim_tool._start_go2``).

Keeping that registration in ONE function means the two can never drift (Rule 3
single-source / Rule 11 no per-embodiment forks) — adding a manipulation skill or
changing the perception wiring happens here, once, for every go2+arm launcher.

The arm/gripper are constructed per-path (in-process ``MuJoCoPiper`` vs the ROS2
``PiperROS2Proxy``) and attached to the agent BEFORE this is called; this helper
only owns the skill registration + the RGB-D perception that ``perception_grasp``
reads. ``base`` is the locomotion base supplying the head camera frames.
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def register_manipulation_skills(agent: Any, base: Any, *, enable_env: bool = True) -> bool:
    """Register the Piper manipulation skills + perception-grasp on ``agent``.

    Args:
        agent: the constructed Agent (its ``_arm``/``_gripper`` already attached).
        base:  the locomotion base supplying head-camera RGB-D for grasp perception.
        enable_env: honor the ``VECTOR_ENABLE_MANIPULATION=0`` opt-out (default on).

    Returns ``True`` when the manipulation stack was wired, ``False`` when skipped
    via the env opt-out. ``perception_grasp`` is registered LAST so it wins the
    shared 抓/grab aliases on the empty-world-model path (it needs no pre-populated
    world model; ``pick_top_down`` does).
    """
    if enable_env and os.environ.get("VECTOR_ENABLE_MANIPULATION", "1") == "0":
        logger.info("[manip] VECTOR_ENABLE_MANIPULATION=0 — manipulation skills skipped")
        return False

    from zeno.skills.pick_top_down import PickTopDownSkill
    from zeno.skills.place_top_down import PlaceTopDownSkill
    from zeno.skills.mobile_pick import MobilePickSkill
    from zeno.skills.mobile_place import MobilePlaceSkill

    agent._skill_registry.register(PickTopDownSkill())
    agent._skill_registry.register(PlaceTopDownSkill())
    agent._skill_registry.register(MobilePickSkill())
    agent._skill_registry.register(MobilePlaceSkill())

    # Perception-driven grasp (the honest North-Star path): real RGB-D from the
    # go2 head camera -> VLM/colour resolve -> EdgeTAM mask -> rendered-depth
    # pointcloud -> 3D grasp point (NEVER ground truth) -> IK -> weld.
    from zeno.perception.go2_grasp_perception import (
        GO2_HEAD_CAM_HEIGHT,
        GO2_HEAD_CAM_WIDTH,
        Go2GraspPerception,
    )
    from zeno.skills.perception_grasp import PerceptionGraspSkill

    # The go2 head camera / bridge publishes the single-sourced head-cam
    # resolution; intrinsics must match it (guarded in test_go2_perception_wiring).
    agent._perception = Go2GraspPerception(
        base, width=GO2_HEAD_CAM_WIDTH, height=GO2_HEAD_CAM_HEIGHT
    )
    agent._skill_registry.register(PerceptionGraspSkill())
    logger.info("[manip] perception-grasp wired: Go2GraspPerception + PerceptionGraspSkill")
    return True
