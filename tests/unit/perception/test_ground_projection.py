# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit tests for pinhole pixel -> ground-plane projection (VLN target grounding).

Pure geometry, no sim. The projection turns a detected colour blob's pixel (the
RGB-only perception CLAIM) into a world-frame (x, y) navigation target by
intersecting the camera ray with the z=z_plane floor. Camera intrinsics come from
the sim (fovy) + extrinsics (cam_xpos / cam_xmat) — geometry the actor cannot author.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from zeno.perception.ground_projection import project_pixel_to_ground

# A downward-looking camera at height 1 m: cam_xmat = identity so the optical axis
# (-Z_cam) points straight down (0,0,-1). Focal f = 0.5*H/tan(fovy/2).
_IDENT = np.eye(3).reshape(9)


def test_center_pixel_projects_below_camera() -> None:
    p = project_pixel_to_ground(
        320, 240, width=640, height=480, fovy_deg=60.0,
        cam_pos=np.array([2.0, 3.0, 1.0]), cam_mat=_IDENT, z_plane=0.0,
    )
    assert p is not None
    assert p[0] == pytest.approx(2.0, abs=1e-6)
    assert p[1] == pytest.approx(3.0, abs=1e-6)


def test_right_pixel_offsets_positive_x_on_ground() -> None:
    # Height 1, a pixel offset of exactly f in +x → ground offset = 1*tan(atan(1)) = 1 m.
    f = 0.5 * 480 / math.tan(math.radians(60.0) / 2)
    p = project_pixel_to_ground(
        320 + f, 240, width=640, height=480, fovy_deg=60.0,
        cam_pos=np.array([0.0, 0.0, 1.0]), cam_mat=_IDENT, z_plane=0.0,
    )
    assert p is not None
    assert p[0] == pytest.approx(1.0, abs=1e-6)
    assert p[1] == pytest.approx(0.0, abs=1e-6)


def test_ray_pointing_away_from_plane_returns_none() -> None:
    # Optical axis pointing UP (+z): flip Z_cam so -Z_cam = +z. cam looks up, never
    # hits the floor below → None (never fabricate a target behind the camera).
    up_mat = np.diag([1.0, -1.0, -1.0]).reshape(9)  # -Z_cam = (0,0,+1)
    p = project_pixel_to_ground(
        320, 240, width=640, height=480, fovy_deg=60.0,
        cam_pos=np.array([0.0, 0.0, 1.0]), cam_mat=up_mat, z_plane=0.0,
    )
    assert p is None


def test_none_pixel_returns_none() -> None:
    assert project_pixel_to_ground(
        None, None, width=640, height=480, fovy_deg=60.0,
        cam_pos=np.array([0.0, 0.0, 1.0]), cam_mat=_IDENT,
    ) is None


def test_matches_sim_probe_geometry() -> None:
    # Regression against the live g1 head-cam probe (scratchpad/g1_mat_probe.py):
    # the blue mat blob-bottom pixel projected to ~(12.98, 3.0) vs GT (12.6, 3.0).
    # Reproduce with the compiled scene camera pose captured from that probe run.
    cam_pos = np.array([10.04, 3.0, 1.21])
    # Optical axis = +x world (g1 faces +x). MuJoCo camera axes X_cam=right=(0,-1,0),
    # Y_cam=up=(0,0,1), Z_cam=backward=(-1,0,0). Row-major xmat rows carry the world
    # x/y/z components across those three columns -> [[0,0,-1],[-1,0,0],[0,1,0]].
    cam_mat = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]], dtype=float).reshape(9)
    p = project_pixel_to_ground(
        319, 479, width=640, height=480, fovy_deg=45.0,
        cam_pos=cam_pos, cam_mat=cam_mat, z_plane=0.0,
    )
    assert p is not None
    # Lands ahead of the camera in +x, near the mat; y stays ~3.0 (dead ahead).
    assert 11.0 < p[0] < 16.0
    assert p[1] == pytest.approx(3.0, abs=0.6)
