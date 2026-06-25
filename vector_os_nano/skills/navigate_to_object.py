# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""NavigateToObjectSkill — drive to the vicinity of a KNOWN object by name.

This is the object-layer counterpart of NavigateSkill (which goes to a named
ROOM).  It is a small composable building block, NOT a hardcoded pipeline:

    object name  ->  SceneGraph.find_objects_by_category  ->  world (x, y)
                 ->  NavigateSkill coordinate drive (FAR planner, hold at goal)

The object's position is the SceneGraph's single source of truth, populated by
look/explore via the depth->world localizer (refactor #1).  Reaching the exact
object cell is NOT the goal here — FAR avoids the object as an obstacle and the
coordinate drive holds the dog in the goal's vicinity.  Precise final approach +
re-perception + grasp is a separate building block (refactor #3); the agent
composes them per situation.

Hardware-agnostic: works with any BaseProtocol exposing navigate_to / get_position.
"""
from __future__ import annotations

import logging
from typing import Any

from vector_os_nano.core.skill import SkillContext, skill
from vector_os_nano.core.types import SkillResult
from vector_os_nano.skills.navigate import NavigateSkill, _distance

logger = logging.getLogger(__name__)

# An object whose stored coord is within this of the origin on BOTH axes is
# treated as "not localized yet" (the merge_object x=y=0.0 default), mirroring
# pick.py's abs()>0.01 guard.
_COORD_EPS_M: float = 0.01


def _accept_object_name(params: dict) -> str:
    """Extract the target object name from params, tolerating aliases."""
    for key in ("object", "query", "name", "target", "object_label", "object_id"):
        val = params.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


@skill(
    aliases=[
        "navigate to object",
        "go to object",
    ],
    direct=False,
)
class NavigateToObjectSkill:
    """Navigate the robot to the vicinity of a known object, by name.

    Looks the object up in the SceneGraph (populated by look/explore) and drives
    to its world position via the navigation planner, holding at the vicinity so
    a downstream approach/grasp can take over.
    """

    name: str = "navigate_to_object"
    description: str = (
        "Navigate the robot to the vicinity of a specific OBJECT by name "
        "(e.g. 'green bottle', 'red can', '绿色瓶子'), using the object's "
        "position from the scene graph. Use this when the user wants to GO TO / "
        "APPROACH a named object rather than a room. The object must have been "
        "seen first (via look or explore) so its position is known. For going to "
        "a ROOM, use 'navigate' instead."
    )
    parameters: dict = {
        "object": {
            "type": "string",
            "required": True,
            "description": (
                "Name or category of the object to go to, e.g. 'green bottle', "
                "'red can', 'banana'. Matched against scene-graph object categories."
            ),
        },
    }
    preconditions: list[str] = []
    postconditions: list[str] = []
    effects: dict = {"position": "changed"}
    failure_modes: list[str] = [
        "no_base",
        "no_scene_graph",
        "object_not_found",
        "object_not_localized",
        "navigation_failed",
    ]

    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        if context.base is None:
            return SkillResult(
                success=False,
                error_message="No base connected",
                diagnosis_code="no_base",
            )

        obj_name = _accept_object_name(params)
        if not obj_name:
            return SkillResult(
                success=False,
                error_message="No object specified (pass 'object').",
                diagnosis_code="object_not_found",
            )

        sg = context.services.get("spatial_memory")
        if sg is None or not hasattr(sg, "find_objects_by_category"):
            return SkillResult(
                success=False,
                error_message="No scene graph available. Run look/explore first.",
                diagnosis_code="no_scene_graph",
            )

        matches = sg.find_objects_by_category(obj_name)
        localized = [
            o for o in matches
            if abs(getattr(o, "x", 0.0)) > _COORD_EPS_M
            or abs(getattr(o, "y", 0.0)) > _COORD_EPS_M
        ]

        if not localized:
            if matches:
                # Known category but no usable position yet (stored at 0,0).
                return SkillResult(
                    success=False,
                    error_message=(
                        f"Object '{obj_name}' is known but has no position yet — "
                        "look at it first."
                    ),
                    diagnosis_code="object_not_localized",
                )
            available = self._available_categories(sg)
            return SkillResult(
                success=False,
                error_message=(
                    f"Object '{obj_name}' not found in scene graph. "
                    f"Known objects: {available}."
                ),
                diagnosis_code="object_not_found",
            )

        # Pick the localized match nearest to the robot; tie-break on confidence.
        pos = context.base.get_position()
        rx, ry = float(pos[0]), float(pos[1])
        target_obj = min(
            localized,
            key=lambda o: (
                _distance(rx, ry, o.x, o.y),
                -getattr(o, "confidence", 0.0),
            ),
        )
        tx, ty = float(target_obj.x), float(target_obj.y)
        logger.info(
            "[NAV-OBJ] %r -> object %r in %s @ (%.2f, %.2f)",
            obj_name, target_obj.category, getattr(target_obj, "room_id", "?"), tx, ty,
        )

        # Delegate the drive to NavigateSkill's coordinate path (FAR planner +
        # hold at vicinity). Reuse, don't reimplement.
        nav_result = NavigateSkill().execute({"x": tx, "y": ty}, context)

        # Enrich the result with the object metadata so the agent/loop sees what
        # it actually drove to.
        rd: dict[str, Any] = dict(getattr(nav_result, "result_data", None) or {})
        final_pos = context.base.get_position()
        rd.update({
            "object": obj_name,
            "matched_category": target_obj.category,
            "object_world": [round(tx, 3), round(ty, 3)],
            "room": getattr(target_obj, "room_id", ""),
            "distance_to_object": round(
                _distance(float(final_pos[0]), float(final_pos[1]), tx, ty), 2
            ),
        })
        return SkillResult(
            success=nav_result.success,
            error_message=nav_result.error_message,
            diagnosis_code=nav_result.diagnosis_code,
            result_data=rd,
        )

    @staticmethod
    def _available_categories(sg: Any) -> str:
        """Comma-joined list of distinct localized object categories, for errors."""
        try:
            cats = sorted({
                o.category for o in getattr(sg, "_objects", {}).values()
                if abs(getattr(o, "x", 0.0)) > _COORD_EPS_M
                or abs(getattr(o, "y", 0.0)) > _COORD_EPS_M
            })
            return ", ".join(cats) if cats else "none"
        except Exception:  # noqa: BLE001
            return "unknown"
