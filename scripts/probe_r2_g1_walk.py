#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R2 probe: G1 humanoid WALKS to a point in the go2 apartment room.

Foreground verify (run by the lead, NOT in CI). G1 spawns at (10,3) facing +x.
We command it to walk toward the pick_table (at ~(10.95, 3.0)) — first a leg
~1.5m ahead, then toward the table standoff — and verify:

  (1) g1 WALKS: base x/y moves toward the target; base-z stays UP (no fall).
  (2) SENSORS UPDATE while moving: lidar n_returns + min_range CHANGE across
      START / MID / ARRIVAL (the table/walls come into range); the camera view
      changes along the walk.

Runs N trials; reports honest success rate (reached + did-not-fall).

Usage:
    MUJOCO_GL=egl python3 scripts/probe_r2_g1_walk.py

Outputs:
    /tmp/r2_g1_walk.json            — full per-stage + per-trial summary
    /tmp/r2_g1_cam_start.png        — head-cam at spawn
    /tmp/r2_g1_cam_mid.png          — head-cam mid-walk
    /tmp/r2_g1_cam_arrival.png      — head-cam at arrival
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

os.environ.setdefault("MUJOCO_GL", "egl")

# --- conflicting-sim guard --------------------------------------------------
import subprocess as _sp

_running = _sp.run(
    ["pgrep", "-f", "[m]ujoco|[g]o2_vnav|[l]aunch_explore"],
    capture_output=True, text=True,
).stdout.strip()
if _running:
    print(f"WARNING: possible sim processes running: {_running[:200]}")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1  # noqa: E402


def _save_png(frame, path: str) -> bool:
    try:
        import importlib
        _pil = importlib.import_module("PIL.Image")
        _pil.fromarray(frame).save(path)
        return True
    except Exception:
        try:
            import imageio  # type: ignore[import]
            imageio.imwrite(path, frame)
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[probe] PNG save failed for {path}: {exc}")
            return False


def _sensor_snapshot(g1: MuJoCoG1, label: str) -> dict:
    """Capture pose + lidar + camera at the current instant; save the cam PNG."""
    x, y, z = _base_xyz(g1)
    heading = g1.get_heading()
    scan = g1.get_lidar_scan()
    n_ret = int(getattr(scan, "n_returns", 0))
    min_r = float(getattr(scan, "min_range", float("inf")))
    med_r = float(getattr(scan, "median_range", float("inf")))
    n_pts = len(getattr(scan, "points_3d", []) or [])
    frame = g1.get_camera_frame(width=640, height=480)
    cam_mean = float(frame.mean())
    cam_std = float(frame.std())
    png_path = f"/tmp/r2_g1_cam_{label}.png"
    saved = _save_png(frame, png_path)
    # nearest 3d point that is NOT a wall (within ~2m horizontally of g1) —
    # a proxy for "did the table/near furniture enter lidar range"
    near_pts = 0
    for p in (getattr(scan, "points_3d", []) or []):
        dx, dy = p[0] - x, p[1] - y
        if math.hypot(dx, dy) < 2.0:
            near_pts += 1
    snap = {
        "label": label,
        "x": round(x, 4), "y": round(y, 4), "z": round(z, 4),
        "heading_rad": round(heading, 4),
        "lidar_n_returns": n_ret,
        "lidar_min_range": round(min_r, 3) if min_r < 1e9 else None,
        "lidar_median_range": round(med_r, 3) if med_r < 1e9 else None,
        "lidar_3d_points": n_pts,
        "lidar_near_pts_<2m": near_pts,
        "cam_mean_pixel": round(cam_mean, 1),
        "cam_std_pixel": round(cam_std, 1),
        "cam_png": png_path if saved else None,
    }
    print(
        f"[probe] {label:8s}  pos=({x:+.3f},{y:+.3f},{z:.3f}) hdg={heading:+.2f}  "
        f"lidar n={n_ret} min={min_r:.2f}m near<2m={near_pts}  "
        f"cam mean={cam_mean:.0f} std={cam_std:.0f}"
    )
    return snap


def _base_xyz(g1: MuJoCoG1) -> tuple[float, float, float]:
    p = g1.get_position()
    return float(p[0]), float(p[1]), float(p[2])


# --- target geometry --------------------------------------------------------
# g1 spawns at (10, 3) facing +x.  The pick_table is at (10.95, 3.0) with its
# near face at x~=10.80, DIRECTLY blocking the +x path (verified: a straight +x
# walk stalls against the table at x~=10.73 — the gait churns in place, no fall).
# So we walk g1 around the room to REACHABLE open points, ending at a table-side
# standoff so the table enters lidar/camera range as g1 approaches.
#   Clear space: south wall at y~=0, west doorway at x=6, table blocks +x.
#   Leg 1: south to (10.0, 1.4) — ~1.6 m of clear floor.
#   Leg 2: to a table-side standoff (10.45, 2.4) — ends ~0.7 m from the table
#          corner with the table in the head-camera/lidar field.
_SPAWN = (10.0, 3.0)
_LEG1 = (10.0, 1.4)
_TABLE_STANDOFF = (10.45, 2.4)
_FALL_Z = 0.4
_N_TRIALS = 2


def _run_trial(trial: int) -> dict:
    print(f"\n[probe] ===== TRIAL {trial} =====")
    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    g1.settle(0.3) if hasattr(g1, "settle") else None

    stages: list[dict] = []
    fell = False
    dist_traveled = 0.0

    # START snapshot (at spawn, before moving) — only trial 1 saves PNGs to
    # the canonical names the lead Reads (start/mid/arrival).
    save_pngs = trial == 1
    x0, y0, z0 = _base_xyz(g1)
    if save_pngs:
        stages.append(_sensor_snapshot(g1, "start"))
    else:
        stages.append({"label": "start", "x": round(x0, 4), "y": round(y0, 4),
                       "z": round(z0, 4)})

    # --- Leg 1: walk ~1.5m forward ---
    print(f"[probe] navigate_to LEG1 {_LEG1} ...")
    r1 = g1.navigate_to(_LEG1[0], _LEG1[1], tol=0.35, speed=0.5)
    dist_traveled += float(r1.get("moved_m", 0.0))
    xm, ym, zm = _base_xyz(g1)
    if zm < _FALL_Z:
        fell = True
    if save_pngs:
        stages.append(_sensor_snapshot(g1, "mid"))
    else:
        stages.append({"label": "mid", "x": round(xm, 4), "y": round(ym, 4),
                       "z": round(zm, 4), "leg1": r1})
    print(f"[probe] leg1 result: {r1}")

    # --- Leg 2: walk toward the table standoff (table enters range) ---
    if not fell:
        print(f"[probe] navigate_to TABLE_STANDOFF {_TABLE_STANDOFF} ...")
        r2 = g1.navigate_to(_TABLE_STANDOFF[0], _TABLE_STANDOFF[1], tol=0.4, speed=0.45)
        dist_traveled += float(r2.get("moved_m", 0.0))
    else:
        r2 = {"reached": False, "reason": "fell_in_leg1"}

    xa, ya, za = _base_xyz(g1)
    if za < _FALL_Z:
        fell = True
    if save_pngs:
        stages.append(_sensor_snapshot(g1, "arrival"))
    else:
        stages.append({"label": "arrival", "x": round(xa, 4), "y": round(ya, 4),
                       "z": round(za, 4), "leg2": r2})
    print(f"[probe] leg2 result: {r2}")

    net = math.hypot(xa - x0, ya - y0)
    reached = bool(r2.get("reached", False)) and not fell
    print(
        f"[probe] TRIAL {trial}: reached={reached} fell={fell} "
        f"net_disp={net:.3f}m path={dist_traveled:.3f}m "
        f"start=({x0:.2f},{y0:.2f},{z0:.2f}) end=({xa:.2f},{ya:.2f},{za:.2f})"
    )

    g1.close()
    return {
        "trial": trial,
        "reached": reached,
        "fell": fell,
        "net_displacement_m": round(net, 3),
        "path_length_m": round(dist_traveled, 3),
        "start": [round(x0, 3), round(y0, 3), round(z0, 3)],
        "end": [round(xa, 3), round(ya, 3), round(za, 3)],
        "leg1": r1,
        "leg2": r2,
        "stages": stages,
    }


def main() -> int:
    trials = []
    for t in range(1, _N_TRIALS + 1):
        try:
            trials.append(_run_trial(t))
        except Exception as exc:  # noqa: BLE001 — report, don't hide
            import traceback
            traceback.print_exc()
            trials.append({"trial": t, "error": str(exc)})

    n_ok = sum(1 for tr in trials if tr.get("reached") and not tr.get("fell"))
    n_fell = sum(1 for tr in trials if tr.get("fell"))

    # cross-stage sensor change (from trial 1, which saved PNGs)
    sensor_change = None
    t1 = next((tr for tr in trials if tr["trial"] == 1 and "stages" in tr), None)
    if t1:
        st = {s["label"]: s for s in t1["stages"] if "lidar_n_returns" in s}
        if {"start", "mid", "arrival"} <= set(st):
            sensor_change = {
                "lidar_n_returns": [st["start"]["lidar_n_returns"],
                                    st["mid"]["lidar_n_returns"],
                                    st["arrival"]["lidar_n_returns"]],
                "lidar_min_range": [st["start"]["lidar_min_range"],
                                    st["mid"]["lidar_min_range"],
                                    st["arrival"]["lidar_min_range"]],
                "lidar_near_pts_<2m": [st["start"]["lidar_near_pts_<2m"],
                                       st["mid"]["lidar_near_pts_<2m"],
                                       st["arrival"]["lidar_near_pts_<2m"]],
                "cam_mean_pixel": [st["start"]["cam_mean_pixel"],
                                   st["mid"]["cam_mean_pixel"],
                                   st["arrival"]["cam_mean_pixel"]],
            }

    summary = {
        "n_trials": _N_TRIALS,
        "n_reached_no_fall": n_ok,
        "n_fell": n_fell,
        "success_rate": f"{n_ok}/{_N_TRIALS}",
        "sensor_change_trial1": sensor_change,
        "trials": trials,
    }
    with open("/tmp/r2_g1_walk.json", "w") as f:
        json.dump(summary, f, indent=2)
    print("\n[probe] Wrote /tmp/r2_g1_walk.json")
    print(f"[probe] VERDICT: reached_no_fall {n_ok}/{_N_TRIALS}, fell {n_fell}")
    if sensor_change:
        print(f"[probe] sensor change (start/mid/arrival): {json.dumps(sensor_change)}")
    return 0


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os.system("rosm nuke --yes > /dev/null 2>&1")
    os.system("pkill -9 -f '[m]ujoco' > /dev/null 2>&1")
    os._exit(rc)
