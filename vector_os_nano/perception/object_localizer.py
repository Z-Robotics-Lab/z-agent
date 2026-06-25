# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Reusable 3D object localizer — depth+mask centroid lifted to world frame.

Routes object name queries through the existing (correct) depth→world pipeline:

    grounding-dino detect → EdgeTAM segment → grasp_point_from_rgbd → Pose3D

This is the SysNav-style masked-cloud centroid approach: detect each object
by name, segment the bounding box to get a tight mask, project the masked
depth pixels through the proven camera→world transform, and return the
world-frame centroid.  The pipeline reuses grasp_point_from_rgbd exactly —
no re-implementation of projection.

Used by the look skill to fill accurate (x, y) coordinates in the scene
graph instead of the 0.0, 0.0 defaults that placed every object at room
centre.

GUARD contract: if perception is None or lacks any required method, returns
[].  Per-object failures are silently skipped (debug-logged) so one bad
detection can never kill the sweep.  This function NEVER raises.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Methods the perception object must expose for localization to run.
_REQUIRED_METHODS = (
    "detect",
    "segment",
    "get_color_frame",
    "get_depth_frame",
    "get_intrinsics",
    "get_camera_pose",
)


def _perception_is_usable(perception: Any) -> bool:
    """Return True only if *perception* exposes every required method."""
    if perception is None:
        return False
    for m in _REQUIRED_METHODS:
        if not callable(getattr(perception, m, None)):
            return False
    return True


def localize_objects_3d(
    perception: Any,
    queries: list[str],
) -> list[tuple[str, float, float, float]]:
    """Localize each query string to a world-frame (x, y, z) position.

    For each query:
      1. Run the open-vocab detector (grounding-dino) on the live RGB frame.
      2. For the highest-confidence detection, segment the bbox (EdgeTAM /
         box-rect fallback) to get a binary mask.
      3. Feed depth + mask + intrinsics + camera pose through
         grasp_point_from_rgbd to obtain a world-frame Pose3D.
      4. Emit (label, float(x), float(y), float(z)).

    Deduplicates by label: only the highest-confidence detection per label
    is kept.  Multiple queries producing the same label are also deduped (the
    first world point wins, as that comes from the highest-score detection).

    Args:
        perception: A Go2GraspPerception-like object with the required API.
            Pass None (or an object missing a method) to get [] with no error.
        queries: List of natural-language object name strings to detect.

    Returns:
        List of (label, x, y, z) for successfully localised objects.  May be
        shorter than *queries* (failed detections are silently dropped).
        Returns [] if perception is unusable or all detections fail.
    """
    if not _perception_is_usable(perception):
        logger.debug(
            "[OBJ-LOC] perception not usable (None or missing method) — returning []"
        )
        return []

    from vector_os_nano.perception.grasp_point import grasp_point_from_rgbd

    # Capture frames + camera geometry once (reuse across all queries).
    try:
        color = perception.get_color_frame()
        depth = perception.get_depth_frame()
        intrinsics = perception.get_intrinsics()
        cam_pose = perception.get_camera_pose()
        cam_xpos, cam_xmat = cam_pose[0], cam_pose[1]
    except Exception as exc:
        logger.debug("[OBJ-LOC] failed to capture frames/pose: %s", exc)
        return []

    results: dict[str, tuple[str, float, float, float]] = {}

    for query in queries:
        try:
            detections = perception.detect(query)
        except Exception as exc:
            logger.debug("[OBJ-LOC] detect(%r) failed: %s", query, exc)
            continue

        if not detections:
            logger.debug("[OBJ-LOC] no detections for %r", query)
            continue

        # detections are sorted by confidence descending (grounding-dino contract).
        for det in detections:
            label: str = det.label if det.label else query
            # Skip if we already have a world point for this label
            # (first = highest-confidence detection wins).
            if label in results:
                continue

            try:
                mask = perception.segment(color, det.bbox)
                if mask is None:
                    logger.debug("[OBJ-LOC] segment returned None for %r", label)
                    continue

                world = grasp_point_from_rgbd(
                    depth, color, mask, intrinsics, cam_xpos, cam_xmat
                )
                if world is None:
                    logger.debug(
                        "[OBJ-LOC] grasp_point_from_rgbd returned None for %r "
                        "(too few depth points in mask)",
                        label,
                    )
                    continue

                results[label] = (label, float(world.x), float(world.y), float(world.z))
                logger.debug(
                    "[OBJ-LOC] localised %r → (%.3f, %.3f, %.3f)",
                    label, world.x, world.y, world.z,
                )
                # Found a good point for this label; move to next query.
                break

            except Exception as exc:
                logger.debug(
                    "[OBJ-LOC] per-object localization failed for %r: %s", label, exc
                )
                continue

    return list(results.values())
