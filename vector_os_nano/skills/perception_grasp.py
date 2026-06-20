# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""PerceptionGraspSkill — the honest, perception-driven Go2+Piper grasp.

This is the skill the North Star calls for: the robot LOCALIZES the target the
way a real robot must — perceive it — instead of reading the simulator's
omniscient object table.

Pipeline (the goal, verbatim):
    VLM 识别 (Moondream bbox)
      -> EdgeTAM 分割 (binary mask)
      -> pointcloud 取中点 (mask + REAL rendered depth -> camera-frame centroid
         -> world via the exact MuJoCo cam->world transform)   [grasp_point.py]
      -> IK + grasp motion (REUSES the proven PickTopDownSkill via its
         params['target_xyz'] seam — no re-implemented motion)
      -> verify  holding_object('<name>')

Contrast with PickTopDownSkill (skills/pick_top_down.py): that skill reads the
object's world pose from a pre-populated world model (ground truth). This skill
NEVER does — the 3D grasp point comes only from depth + mask. If perception
fails (no detection / empty mask / no depth points) it FAILS LOUD with a precise
diagnosis; it must NEVER silently substitute a ground-truth pose to stay green
(that re-fakes perception, the exact thing the goal forbids).

The verify oracle holding_object('<name>') stays ground-truth and BYTE-UNCHANGED
(it is the moat oracle the actor cannot author): the skill only EMITS the verify
string, it never imports/evaluates the oracle or feeds the centroid into it.
"""
from __future__ import annotations

import logging
from typing import Any

from vector_os_nano.core.skill import SkillContext, skill
from vector_os_nano.core.types import SkillResult
from vector_os_nano.perception.grasp_point import grasp_point_from_rgbd

logger = logging.getLogger(__name__)

# Perception-backend surface this skill consumes (a Go2GraspPerception or any
# RGB-D + VLM + segmenter adapter exposing these).
_REQUIRED_PERCEPTION = (
    "detect", "segment", "get_color_frame", "get_depth_frame",
    "get_intrinsics", "get_camera_pose",
)


def _fail(diagnosis: str, message: str, **extra: Any) -> SkillResult:
    data = {"diagnosis": diagnosis, "perceived": False}
    data.update(extra)
    return SkillResult(success=False, error_message=message, result_data=data)


@skill(
    aliases=[
        # Perception-natural grasp phrasings. Registered LAST (after PickTopDown)
        # so these win on the bare-cli / empty-world-model honest path.
        "抓", "拿", "抓起", "抓住", "抓取", "拿起", "取",
        "grab", "grasp", "pick up", "pick",
    ],
    direct=False,
)
class PerceptionGraspSkill:
    """Perceive a target (VLM->EdgeTAM->depth pointcloud) and grasp it."""

    name: str = "perception_grasp"
    description: str = (
        "Grasp an object the robot must FIND first: detect it with the VLM, "
        "segment it with EdgeTAM, compute the 3D grasp point from the depth "
        "camera + mask, then top-down grasp with the Piper arm. Use this when "
        "the object is NOT already in the world model (the normal case). The "
        "grasp point is perceived, never read from ground truth."
    )
    verify_hint: str = "holding_object('<object>')"
    parameters: dict = {
        "query": {
            "type": "string",
            "required": True,
            "description": "What to grasp, in natural language (e.g. 'banana', 'red can', 'the bottle').",
        },
    }
    preconditions: list[str] = ["gripper_empty"]
    postconditions: list[str] = []
    effects: dict = {"gripper_state": "holding"}
    failure_modes: list[str] = [
        "no_arm", "no_gripper", "arm_unsupported", "no_perception", "no_camera",
        "no_detections", "segmentation_failed", "no_depth_points",
        "ik_unreachable", "move_failed", "not_holding",
    ]

    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        import numpy as np  # local — keep import light

        arm = context.arm
        gripper = context.gripper
        if arm is None:
            return _fail("no_arm", "No arm connected")
        if gripper is None:
            return _fail("no_gripper", "No gripper connected")
        if not hasattr(arm, "ik_top_down"):
            return _fail(
                "arm_unsupported",
                f"Arm {getattr(arm, 'name', type(arm).__name__)!r} lacks ik_top_down; "
                "PerceptionGraspSkill needs a 6-DoF arm with top-down IK (e.g. MuJoCoPiper).",
            )

        perception = context.perception
        query = str(
            params.get("query") or params.get("object_label")
            or params.get("target") or params.get("object_id") or ""
        ).strip()
        if perception is None:
            return _fail("no_perception", "No perception backend available; cannot perceive the target")
        missing = [m for m in _REQUIRED_PERCEPTION if not hasattr(perception, m)]
        if missing:
            return _fail(
                "no_camera",
                f"Perception backend {type(perception).__name__} lacks RGB-D grasp surface: {missing}",
            )

        # --- acquire frames (real rendered RGB-D + camera pose) ---------------
        try:
            rgb = perception.get_color_frame()
            depth = perception.get_depth_frame()
            intrinsics = perception.get_intrinsics()
            cam_xpos, cam_xmat = perception.get_camera_pose()
        except Exception as exc:  # noqa: BLE001
            return _fail("no_camera", f"Failed to read RGB-D frame: {exc}")

        # --- VLM detect -------------------------------------------------------
        try:
            detections = perception.detect(query)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[PGRASP] detect raised: %s", exc)
            detections = []
        if not detections:
            return _fail(
                "no_detections",
                f"VLM found nothing matching {query!r}. The object is not visible; "
                "reposition the robot/camera or refine the query.",
                query=query,
            )
        det = max(detections, key=lambda d: getattr(d, "confidence", 0.0))
        resolved = str(getattr(det, "label", query) or query)

        # --- EdgeTAM segment --------------------------------------------------
        try:
            mask = perception.segment(rgb, det.bbox)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[PGRASP] segment raised: %s", exc)
            mask = None
        if mask is None or int(np.count_nonzero(mask)) == 0:
            return _fail(
                "segmentation_failed",
                f"EdgeTAM produced no mask for {resolved!r}.",
                detection_label=resolved, query=query,
            )

        # --- pointcloud 取中点 -> world grasp point (REAL depth, never GT) -----
        gp = grasp_point_from_rgbd(depth, rgb, mask, intrinsics, cam_xpos, cam_xmat)
        if gp is None:
            return _fail(
                "no_depth_points",
                f"No valid depth points under the {resolved!r} mask; cannot localize a grasp point. "
                "FAIL LOUD — not substituting a ground-truth pose.",
                detection_label=resolved, query=query,
            )
        logger.info("[PGRASP] %s -> perceived grasp_world=(%.3f, %.3f, %.3f)",
                    resolved, gp.x, gp.y, gp.z)

        # --- delegate the proven top-down motion via the target_xyz seam ------
        from vector_os_nano.skills.pick_top_down import PickTopDownSkill
        pick_params = dict(params)
        pick_params["target_xyz"] = [gp.x, gp.y, gp.z]
        pick_params["object_id"] = resolved
        res = PickTopDownSkill().execute(pick_params, context)

        rd = dict(res.result_data or {})
        rd.update({
            "perceived": True,
            "grasp_world": [gp.x, gp.y, gp.z],
            "detection_label": resolved,
            "query": query,
        })
        if not res.success and "diagnosis" not in rd:
            rd["diagnosis"] = "grasp_failed"
        return SkillResult(
            success=res.success,
            error_message=res.error_message,
            result_data=rd,
        )
