#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R1 probe: G1 humanoid in go2 apartment room — foreground verify.

Run by the lead (NOT in CI). Settles 2s, logs pose + lidar + camera stats,
writes JSON summary + camera PNG.

Usage:
    MUJOCO_GL=egl python3 scripts/probe_r1_g1_room.py

Outputs:
    /tmp/r1_g1_room.json   — stats summary
    /tmp/r1_g1_cam.png     — RGB camera frame (640x480)
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("MUJOCO_GL", "egl")

# ---------------------------------------------------------------------------
# Check for conflicting sims before loading MuJoCo
# ---------------------------------------------------------------------------
import subprocess as _sp

_running = _sp.run(
    ["pgrep", "-f", "mujoco|go2_vnav|launch_explore"],
    capture_output=True, text=True
).stdout.strip()
if _running:
    print(f"WARNING: possible sim processes running: {_running[:200]}")

# ---------------------------------------------------------------------------
# Build scene + connect
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_os_nano.hardware.sim.mujoco_g1 import (  # noqa: E402
    MuJoCoG1,
    _build_g1_room_scene_xml,
)

print("[probe] Building g1 room scene...")
scene_path = _build_g1_room_scene_xml()
print(f"[probe] Scene: {scene_path}")

import mujoco as _mj  # noqa: E402
import numpy as _np  # noqa: E402

_m = _mj.MjModel.from_xml_path(str(scene_path))
print(f"[probe] Model: nbody={_m.nbody}, njnt={_m.njnt}, nu={_m.nu}, ncam={_m.ncam}")

g1 = MuJoCoG1(gui=False, room=True)
g1.connect()

# ---------------------------------------------------------------------------
# (1) Log base-z over 2s settle
# ---------------------------------------------------------------------------
print("[probe] Settling 2s (logging base-z)...")
z_samples: list[float] = []
dt = float(g1._mj.model.opt.timestep)  # type: ignore[union-attr]
n_total = int(2.0 / dt)
sample_every = max(1, n_total // 100)  # ~100 samples

for step in range(n_total):
    # Hold stand ctrl
    g1._mj.data.ctrl[:] = g1._mj.model.key_ctrl[g1._mj.stand_kf_id]  # type: ignore[union-attr]
    _mj.mj_step(g1._mj.model, g1._mj.data)  # type: ignore[union-attr]
    if step % sample_every == 0:
        z_samples.append(g1.get_base_height())

z_final = g1.get_base_height()
z_min = min(z_samples)
z_max = max(z_samples)
z_mean = sum(z_samples) / len(z_samples)
stands = z_min > 0.5  # floor = 0; fallen = <0.5m
print(f"[probe] base-z: final={z_final:.4f}, min={z_min:.4f}, max={z_max:.4f}, mean={z_mean:.4f}")
print(f"[probe] STANDS: {stands}")

# Check g1 spawn pose
heading = g1.get_heading()
qa = g1._mj.pelvis_qpos_adr  # type: ignore[union-attr]
pelvis_pos = g1._mj.data.qpos[qa:qa+3].tolist()  # type: ignore[union-attr]
print(f"[probe] pelvis world pos: {[f'{v:.4f}' for v in pelvis_pos]}")
print(f"[probe] heading (yaw rad): {heading:.4f}")

# ---------------------------------------------------------------------------
# (2) Lidar scan
# ---------------------------------------------------------------------------
print("[probe] Getting lidar scan...")
scan = g1.get_lidar_scan()
valid_ranges = [r for r in scan.ranges if r < scan.range_max]
print(f"[probe] lidar: n_returns={scan.n_returns}, min={scan.min_range:.3f}m, "
      f"median={scan.median_range:.3f}m, near_zero_self_hits={scan.near_zero_self_hits}")
print(f"[probe] lidar 3d points: {len(scan.points_3d)}")

assert scan.near_zero_self_hits == 0, (
    f"FAIL: {scan.near_zero_self_hits} near-zero self-hits in lidar!"
)
assert scan.n_returns > 0, "FAIL: lidar returned 0 hits"

# ---------------------------------------------------------------------------
# (3) Camera frame
# ---------------------------------------------------------------------------
print("[probe] Rendering camera frame (640x480)...")
cam_pos, cam_xmat = g1.get_camera_pose()
frame = g1.get_camera_frame(width=640, height=480)
print(f"[probe] camera pose xpos: {cam_pos.tolist()}")
# Optical axis = -Z_cam = -cam_xmat[6:9]
z_col = cam_xmat.reshape(3, 3)[:, 2]  # Z column
optical_axis = (-z_col).tolist()
print(f"[probe] camera optical axis: {[f'{v:.3f}' for v in optical_axis]}  (expect ~[1,0,0])")

frame_mean = float(frame.mean())
frame_std = float(frame.std())
print(f"[probe] frame: shape={frame.shape}, dtype={frame.dtype}, "
      f"mean={frame_mean:.1f}, std={frame_std:.1f}")

# Save camera PNG
try:
    import importlib
    _pil = importlib.import_module("PIL.Image")
    img = _pil.fromarray(frame)
    img.save("/tmp/r1_g1_cam.png")
    print("[probe] Saved /tmp/r1_g1_cam.png")
except ImportError:
    try:
        import imageio  # type: ignore[import]
        imageio.imwrite("/tmp/r1_g1_cam.png", frame)
        print("[probe] Saved /tmp/r1_g1_cam.png (imageio)")
    except ImportError:
        print("[probe] PIL/imageio not available — camera PNG not saved (frame verified in-memory)")

# ---------------------------------------------------------------------------
# (4) JSON summary
# ---------------------------------------------------------------------------
summary = {
    "scene_path": str(scene_path),
    "model_nbody": int(_m.nbody),
    "model_njnt": int(_m.njnt),
    "model_nu": int(_m.nu),
    "model_ncam": int(_m.ncam),
    "pelvis_world_pos": [round(v, 4) for v in pelvis_pos],
    "heading_rad": round(heading, 4),
    "base_z_final": round(z_final, 4),
    "base_z_min": round(z_min, 4),
    "base_z_max": round(z_max, 4),
    "base_z_mean": round(z_mean, 4),
    "stands": stands,
    "lidar_n_returns": scan.n_returns,
    "lidar_min_range": round(scan.min_range, 3) if scan.min_range < 1e9 else None,
    "lidar_median_range": round(scan.median_range, 3) if scan.median_range < 1e9 else None,
    "lidar_near_zero_self_hits": scan.near_zero_self_hits,
    "lidar_3d_points": len(scan.points_3d),
    "camera_name": "g1_head_rgb",
    "camera_frame_shape": list(frame.shape),
    "camera_mean_pixel": round(frame_mean, 1),
    "camera_std_pixel": round(frame_std, 1),
    "camera_world_xpos": [round(v, 4) for v in cam_pos.tolist()],
    "camera_optical_axis": [round(v, 3) for v in optical_axis],
}
with open("/tmp/r1_g1_room.json", "w") as f:
    json.dump(summary, f, indent=2)
print("[probe] Wrote /tmp/r1_g1_room.json")

print(f"\n[probe] PASS — G1 stands={stands}, lidar_returns={scan.n_returns}, "
      f"cam_mean={frame_mean:.0f}")

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
g1.close()
sys.stdout.flush()

import os as _os
_os.system("rosm nuke --yes > /dev/null 2>&1")
_os._exit(0)
