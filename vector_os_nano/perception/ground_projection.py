# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Pinhole pixel -> ground-plane projection for VLN target grounding.

Turns a detected object's pixel (the RGB-only perception CLAIM) into a world-frame
(x, y) navigation target by intersecting the camera ray through that pixel with the
z=z_plane floor. Intrinsics (fovy) + extrinsics (cam_xpos / cam_xmat) come from the
sim/hardware — geometry the perception actor cannot author. Pure, embodiment-agnostic:
give it any pinhole camera pose and it returns where a pixel's ray meets the floor.

Convention (matches MuJoCo cameras, verified against the live g1 head-cam probe):
  - image origin top-left, +x right, +y down; principal point at (W/2, H/2)
  - focal length f = 0.5 * H / tan(fovy/2)  (vertical fov)
  - camera-frame ray for pixel (px,py): d_cam = normalize((px-W/2)/f, -(py-H/2)/f, -1)
    (optical axis = -Z_cam); world ray = cam_mat @ d_cam with cam_mat row-major (3,3).
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np


def project_pixel_to_ground(
    px: float | None,
    py: float | None,
    *,
    width: int,
    height: int,
    fovy_deg: float,
    cam_pos: Sequence[float],
    cam_mat: Sequence[float],
    z_plane: float = 0.0,
) -> Optional[tuple[float, float]]:
    """Return the (x, y) where the pixel's camera ray meets the z=z_plane floor.

    Returns None if the pixel is missing, or the ray is parallel to / points away
    from the plane (never fabricate a target behind the camera).
    """
    if px is None or py is None:
        return None
    f = 0.5 * float(height) / math.tan(math.radians(float(fovy_deg)) / 2.0)
    if f <= 0.0:
        return None

    x = (float(px) - width / 2.0) / f
    y = (float(py) - height / 2.0) / f
    d_cam = np.array([x, -y, -1.0], dtype=float)
    d_cam /= np.linalg.norm(d_cam)

    mat = np.asarray(cam_mat, dtype=float).reshape(3, 3)
    d_world = mat @ d_cam
    if abs(float(d_world[2])) < 1e-9:
        return None

    cam = np.asarray(cam_pos, dtype=float).reshape(3)
    t = (float(z_plane) - float(cam[2])) / float(d_world[2])
    if t <= 0.0:
        return None
    hit = cam + t * d_world
    return (float(hit[0]), float(hit[1]))
