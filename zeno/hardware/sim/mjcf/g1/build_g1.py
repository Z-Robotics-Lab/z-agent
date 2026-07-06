# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Build G1 MJCF with absolute mesh paths + head camera.

Mirrors build_go2_piper.py exactly: load the upstream Menagerie G1, rewrite
mesh file paths to absolute (so the XML is include-safe from any directory),
set meshdir="", add a forward-pointing head camera on torso_link, then
write the compiled model to g1.xml.

Usage:
    python3 vector_os_nano/hardware/sim/mjcf/g1/build_g1.py
"""
from __future__ import annotations

import os
from pathlib import Path

import mujoco

# Menagerie G1 — HAS a "stand" keyframe (qpos: pelvis z=0.793, free joint)
G1_MENAGERIE_XML = Path("/home/yusen/Desktop/mujoco_menagerie/unitree_g1/g1.xml")
G1_ASSETS_DIR = G1_MENAGERIE_XML.parent / "assets"

# Head camera parameters — mounted on torso_link, pointing forward (+x when g1 faces +x)
# torso_link origin is approx at waist/chest level. The head top is ~0.45m above
# torso_link origin (torso_link pos in body hierarchy). We mount ~0.04m forward and
# ~0.42m up to land at head height (~1.25m from ground with pelvis at 0.793m).
#
# Camera orientation: same as go2's d435_rgb xyaxes="0 -1 0 0 0 1"
# Camera frame: X_cam=(0,-1,0), Y_cam=(0,0,1), Z_cam=(-1,0,0) [Z points backward]
# Optical axis = -Z_cam = (+1,0,0) → looks in +X world direction (forward).
# Rotation matrix columns [X_cam | Y_cam | Z_cam] → quaternion (w,x,y,z):
# w=0.5, x=0.5, y=-0.5, z=-0.5  (computed from rotation matrix, det=1, norm=1).
_HEAD_CAM_NAME = "head_rgb"  # becomes "g1_head_rgb" after scene attach with prefix "g1_"
_HEAD_CAM_POS = [0.04, 0.0, 0.42]   # m, relative to torso_link
_HEAD_CAM_QUAT = [0.5, 0.5, -0.5, -0.5]  # (w,x,y,z) — optical axis = +X_world
_HEAD_CAM_FOVY = 58.0  # deg — slightly wider than go2's 42° for humanoid perspective


def build_g1_spec() -> mujoco.MjSpec:
    """Load menagerie G1, rewrite meshes to absolute, add head camera.

    Returns the modified MjSpec (not yet compiled/written).
    """
    spec = mujoco.MjSpec.from_file(str(G1_MENAGERIE_XML))

    # Rewrite mesh file paths to absolute — makes the XML include-safe
    for mesh in spec.meshes:
        if not os.path.isabs(mesh.file):
            mesh.file = str(G1_ASSETS_DIR / mesh.file)
    spec.meshdir = ""

    # Add head camera on torso_link
    torso = spec.body("torso_link")
    cam = torso.add_camera()
    cam.name = _HEAD_CAM_NAME
    cam.pos = _HEAD_CAM_POS
    cam.quat = _HEAD_CAM_QUAT
    cam.fovy = _HEAD_CAM_FOVY

    return spec


def main() -> Path:
    """Build and write g1.xml, return its path."""
    this_dir = Path(__file__).resolve().parent

    spec = build_g1_spec()
    spec.compile()

    out = this_dir / "g1.xml"
    out.write_text(spec.to_xml())
    print(f"Wrote: {out}")

    model = mujoco.MjModel.from_xml_path(str(out))
    print(
        f"Sanity: nbody={model.nbody}, njnt={model.njnt}, nu={model.nu}, "
        f"ncam={model.ncam}"
    )

    # Verify head camera exists
    cam_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i)
        for i in range(model.ncam)
    ]
    print(f"Cameras: {cam_names}")
    assert _HEAD_CAM_NAME in cam_names, f"Head camera '{_HEAD_CAM_NAME}' not found!"
    print(f"Head camera '{_HEAD_CAM_NAME}' verified.")
    print(
        "Note: when attached to a scene with prefix 'g1_', "
        "the camera name becomes 'g1_head_rgb'."
    )

    return out


if __name__ == "__main__":
    main()
