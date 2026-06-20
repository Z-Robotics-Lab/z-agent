# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Perception-driven 3D grasp point — (RGB-D + mask) -> world coordinate.

The honest core of the Go2+Piper grasp pipeline. The grasp POINT is computed
ONLY from a real rendered depth frame + an EdgeTAM mask + the proven cam->world
transform — it is NEVER a ground-truth object pose lookup. That is the whole
point of the goal: localize the target the way a real robot must (perceive it),
not by reading the simulator's omniscient state.

Pure module: no MuJoCo / torch / GPU import. Composes already-tested pieces —
``rgbd_to_pointcloud_fast`` (mask -> camera-frame points), ``remove_depth_outliers``
+ ``robust_centroid`` (the trimmed-mean reducer), and ``camera_to_world`` (the
OpenCV->MuJoCo axis flip, ground-truth-tested in test_depth_projection_groundtruth).

UNIT CONTRACT: MuJoCo ``get_depth_frame`` returns float32 METRES, so the default
``depth_scale=1.0``. The RealSense-mm default (1000.0) would divide metres by
1000 and collapse every point to ~origin — a silent, plausible-looking wrong
grasp. Always pass metres + depth_scale=1.0 (or raw mm + depth_scale=1000.0).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from vector_os_nano.core.types import Pose3D
from vector_os_nano.perception._centroid import remove_depth_outliers, robust_centroid
from vector_os_nano.perception.depth_projection import camera_to_world
from vector_os_nano.perception.pointcloud import rgbd_to_pointcloud_fast

_MIN_POINTS = 4


def grasp_point_from_rgbd(
    depth: np.ndarray,
    color: np.ndarray,
    mask: np.ndarray,
    intrinsics: Any,
    cam_xpos: Any,
    cam_xmat: Any,
    *,
    depth_scale: float = 1.0,
    depth_trunc: float = 10.0,
) -> Pose3D | None:
    """Compute the world-frame grasp point for a masked object, or None.

    Pipeline: mask + depth + intrinsics -> camera-frame point cloud (only the
    masked pixels) -> IQR depth-outlier rejection -> trimmed-mean centroid (camera
    frame) -> exact MuJoCo camera->world transform via cam_xpos/cam_xmat.

    Returns None (FAIL LOUD — never a fabricated point) when fewer than 4 valid
    depth points survive: an empty/degenerate mask or an all-zero depth patch
    means the object was not perceived, and the caller must surface that, NOT
    substitute a ground-truth pose to stay green.

    Args:
        depth: (H, W) depth image. Metres with depth_scale=1.0 (MuJoCo render),
            or raw uint16 mm with depth_scale=1000.0 (RealSense).
        color: (H, W, 3) uint8 RGB (carried for parity; not used for the point).
        mask: (H, W) binary mask; only pixels where mask > 0 are projected.
        intrinsics: CameraIntrinsics (fx, fy, cx, cy) — e.g. mujoco_intrinsics().
        cam_xpos: (3,) camera world position (MuJoCo data.cam_xpos[id]).
        cam_xmat: (9,) or (3,3) camera world rotation (MuJoCo data.cam_xmat[id]).
        depth_scale: Raw-depth-units -> metres divisor. 1.0 for metric depth.
        depth_trunc: Max depth in metres; farther points discarded.

    Returns:
        Pose3D world-frame grasp point, or None if the object was not localizable.
    """
    points, _colors = rgbd_to_pointcloud_fast(
        depth, color, intrinsics,
        depth_scale=depth_scale, depth_trunc=depth_trunc, mask=mask,
    )
    if len(points) < _MIN_POINTS:
        return None

    points = remove_depth_outliers(points)
    if len(points) < _MIN_POINTS:
        return None

    centroid_cam = robust_centroid(points)  # camera frame (OpenCV: x=right,y=down,z=fwd)

    # Transforming the single centroid is affine-equivalent to transforming all
    # points then reducing — and far cheaper. Reuses the ground-truth-tested flip.
    wx, wy, wz = camera_to_world(
        centroid_cam.x, centroid_cam.y, centroid_cam.z,
        0.0, 0.0, 0.0, 0.0,
        cam_xpos=cam_xpos, cam_xmat=cam_xmat,
    )
    return Pose3D(x=float(wx), y=float(wy), z=float(wz))
