#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R39 DEBUG PROBE — A vs B clean OBSERVE: why does perception localize the FLOOR
after a FAR+dock arrival, while the proven scripted-from-spawn grasp grounds?

READ-ONLY probe: no repo-code edits, no commit. Saves artifacts to /tmp/r39_debug/.
Uses ONLY existing APIs (Go2GraspPerception perceive pieces, terminal_dock,
base.navigate_to/walk, the /tmp/vector_reset_pose snap-to-+X flag).

ONE serialized go2+arm bridge sim. Captures BOTH cases with IDENTICAL
instrumentation at the SAME perceive moment:

  (A) WORKING baseline — perceive the red can from the SPAWN pose (~10.0, 3.0, +X),
      exactly as the proven scripted-from-spawn colour grasp does (perceive from afar
      BEFORE approach). Logs dog pose, d435 cam_xpos/cam_xmat, the onboard frame PNG,
      grasp_world, mask_px, route.
  (B) FAILING case — FAR navigate_to the table (10.5, 3.0), then HEAD's terminal_dock
      to the FIXED proven pose (10.0, 3.0, 0.0), then perceive with the SAME
      instrumentation. Logs the SAME fields at after-FAR / after-dock / at-perceive.

Then FALSIFICATION experiments (H1..H4), each a single discriminating check:
  H1: drive back to the afar x (~10.0) at the docked heading and re-perceive.
  H2: snap heading to +X in place (reset_pose flag) and re-perceive.
  H3: standoff sweep — perceive at several x and find where the cans frame.
  H4: compare cam_xpos to the live dog pose (stale/garbage cam pose on bridge path?).

Run (serialized; nuke after):
  VECTOR_SIM_WITH_ARM=1 VECTOR_ENABLE_MANIPULATION=1 MUJOCO_GL=egl \
  HF_HOME=/home/yusen/.cache/huggingface \
  PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r39_debug_floor_vs_cans.py
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("VECTOR_ENABLE_MANIPULATION", "1")
os.environ.setdefault("VECTOR_SIM_WITH_ARM", "1")

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

ART = "/tmp/r39_debug"
os.makedirs(ART, exist_ok=True)

# Proven scripted-from-spawn standoff (dock target) and the red-can GT (report only).
_DOCK_X, _DOCK_Y, _DOCK_HD = 10.0, 3.0, 0.0
_TABLE_X, _TABLE_Y = 10.5, 3.0          # FAR navigate goal (table vicinity)
_RED_GT = (10.90, 3.22, 0.32)
_GREEN_GT = (10.88, 3.00, 0.32)
_QUERY = "红色的罐子"                     # the proven colour-grasp query
_TABLE_NEAR_EDGE_X = 10.80              # D34: objects within ~6cm of this render 0px

import logging as _logging
_logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for _n in ("transformers", "urllib3", "PIL", "matplotlib"):
    _logging.getLogger(_n).setLevel(_logging.WARNING)


def _log(msg: str) -> None:
    print(f"[R39DBG] {msg}", flush=True)


def _save_png(rgb, name: str) -> str | None:
    try:
        import cv2
        if rgb is None:
            return None
        path = os.path.join(ART, name)
        cv2.imwrite(path, rgb[:, :, ::-1])  # RGB -> BGR
        return path
    except Exception as exc:  # noqa: BLE001
        _log(f"png save failed ({name}): {exc}")
        return None


def _pose(base) -> tuple[float, float, float]:
    p = base.get_position()
    return (round(float(p[0]), 3), round(float(p[1]), 3), round(float(base.get_heading()), 3))


def perceive_instrumented(perception, base, tag: str, *, save_frame: bool = True) -> dict:
    """Reproduce the proven afar-perceive AND log every field, route-agnostic.

    Mirrors PerceptionGraspSkill._perceive_grasp_point: parse colour, route a NAMED
    query ("红色的罐子" has noun 罐子) to grounding-dino detect+segment; capture rgb,
    depth stats, mask_px, cam_xpos/cam_xmat, and the back-projected grasp_world.
    """
    import numpy as np
    from vector_os_nano.perception.front_object import parse_color
    from vector_os_nano.perception.grasp_point import grasp_point_from_rgbd
    from vector_os_nano.skills.perception_grasp import _names_object

    rec: dict = {"tag": tag, "dog_pose": _pose(base)}
    try:
        rgb = perception.get_color_frame()
        depth = perception.get_depth_frame()
        intr = perception.get_intrinsics()
        cam_xpos, cam_xmat = perception.get_camera_pose()
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"frame read failed: {exc}"
        return rec

    color = parse_color(_QUERY)
    named = _names_object(_QUERY)
    rec["color"] = color
    rec["route"] = "detector(grounding-dino)" if named else "front_object(classical)"

    # cam pose (the EXACT transform fed to back-projection)
    cxp = [round(float(v), 4) for v in np.asarray(cam_xpos).reshape(-1)[:3]]
    cxm = [round(float(v), 4) for v in np.asarray(cam_xmat).reshape(-1)[:9]]
    rec["cam_xpos"] = cxp
    rec["cam_xmat"] = cxm
    # camera optical axis in world = -col2 of xmat (forward)
    xm = np.asarray(cam_xmat, dtype=float).reshape(3, 3)
    fwd = -xm[:, 2]
    rec["cam_forward_world"] = [round(float(v), 4) for v in fwd]
    rec["cam_pitch_deg"] = round(math.degrees(math.atan2(fwd[2], math.hypot(fwd[0], fwd[1]))), 2)

    # depth stats over the whole frame (what is the camera actually seeing?)
    if depth is not None and np.isfinite(depth).any():
        dvalid = depth[(depth > 0) & (depth < 10.0)]
        rec["depth_valid_px"] = int(dvalid.size)
        if dvalid.size:
            rec["depth_min_m"] = round(float(dvalid.min()), 3)
            rec["depth_med_m"] = round(float(np.median(dvalid)), 3)
            rec["depth_max_m"] = round(float(dvalid.max()), 3)
    # center-of-frame world point (what's straight ahead)
    try:
        from vector_os_nano.perception.depth_projection import project_center_to_world
        # use the exact cam transform via a 1px mask at center instead — see below
    except Exception:
        pass

    # --- resolve the target mask via the SAME route the skill uses ---
    mask = None
    resolved = None
    try:
        if named:
            dets = perception.detect(_QUERY)
            rec["n_detections"] = len(dets)
            if dets:
                # colour-preferred selection (mirror _select_detection)
                def _conf(d):
                    return float(getattr(d, "confidence", 0.0))
                matching = [d for d in dets
                            if color and color in str(getattr(d, "label", "") or "").lower()]
                det = max(matching, key=_conf) if matching else max(dets, key=_conf)
                resolved = str(getattr(det, "label", _QUERY))
                rec["det_label"] = resolved
                rec["det_bbox"] = [round(float(v), 1) for v in det.bbox]
                rec["det_conf"] = round(_conf(det), 3)
                mask = perception.segment(rgb, det.bbox)
            else:
                # detector empty -> front-object fallback (the skill does this too)
                if hasattr(perception, "front_object_mask"):
                    mask = perception.front_object_mask(rgb, depth)
                    rec["det_label"] = "front_object_fallback"
        else:
            mask = perception.front_object_mask(rgb, depth, color=color)
            rec["det_label"] = f"front_object(color={color})"
    except Exception as exc:  # noqa: BLE001
        rec["mask_error"] = str(exc)

    mask_px = int(np.count_nonzero(mask)) if mask is not None else 0
    rec["mask_px"] = mask_px

    # save the onboard frame + mask overlay
    if save_frame:
        rec["frame_png"] = _save_png(rgb, f"{tag}_frame.png")
        try:
            if mask is not None and rgb is not None and mask_px:
                import cv2
                overlay = rgb.copy()
                overlay[mask > 0] = [255, 0, 0]
                cv2.imwrite(os.path.join(ART, f"{tag}_mask.png"), overlay[:, :, ::-1])
                rec["mask_png"] = os.path.join(ART, f"{tag}_mask.png")
        except Exception:  # noqa: BLE001
            pass

    # back-project to world (the grasp_world the skill would compute)
    if mask is not None and mask_px >= 1:
        gp = grasp_point_from_rgbd(depth, rgb, mask, intr, cam_xpos, cam_xmat)
        if gp is not None:
            rec["grasp_world"] = [round(gp.x, 3), round(gp.y, 3), round(gp.z, 3)]
            rec["grasp_vs_red_gt_m"] = round(math.hypot(gp.x - _RED_GT[0], gp.y - _RED_GT[1]), 3)
            rec["grasp_vs_green_gt_m"] = round(math.hypot(gp.x - _GREEN_GT[0], gp.y - _GREEN_GT[1]), 3)
            rec["grasp_z_floor"] = bool(gp.z < 0.10)   # z~0 => floor mislocalization
        else:
            rec["grasp_world"] = None
            rec["grasp_note"] = "grasp_point_from_rgbd returned None (<4 depth pts / degenerate)"
    else:
        rec["grasp_world"] = None
        rec["grasp_note"] = "no mask / 0 px"

    _log(f"{tag}: pose={rec['dog_pose']} cam_xpos={cxp} pitch={rec.get('cam_pitch_deg')} "
         f"mask_px={mask_px} grasp_world={rec.get('grasp_world')} "
         f"floor={rec.get('grasp_z_floor')} d_med={rec.get('depth_med_m')}")
    return rec


def _snap_heading_plus_x(base, timeout: float = 4.0) -> None:
    """Snap the dog to upright +X at its current XY via the bridge reset_pose flag."""
    try:
        with open("/tmp/vector_reset_pose", "w") as fh:
            fh.write("1")
    except Exception as exc:  # noqa: BLE001
        _log(f"reset_pose flag write failed: {exc}")
        return
    # bridge polls at 1 Hz; wait for the heading to snap toward 0
    t0 = time.time()
    while time.time() - t0 < timeout:
        if abs(float(base.get_heading())) < 0.12:
            break
        time.sleep(0.3)
    time.sleep(0.5)


def main() -> int:
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool
    from vector_os_nano.skills.utils.terminal_dock import terminal_dock

    _log("booting go2+arm sim (real MuJoCo + ROS2 bridge + FAR)...")
    agent = SimStartTool._start_go2(gui=False, with_arm=True)
    if getattr(agent, "_arm", None) is None:
        _log("FAIL: no arm")
        return 1
    base = agent._base
    perception = agent._perception
    if perception is None:
        _log("FAIL: no perception backend")
        return 1
    _log(f"sim up: base={type(base).__name__} perception={type(perception).__name__}")
    time.sleep(9.0)  # let bridge + FAR + camera settle

    report: dict = {
        "query": _QUERY, "dock_target": [_DOCK_X, _DOCK_Y, _DOCK_HD],
        "far_goal": [_TABLE_X, _TABLE_Y], "red_gt": list(_RED_GT),
        "green_gt": list(_GREEN_GT), "table_near_edge_x": _TABLE_NEAR_EDGE_X,
    }

    # ================= CASE A — WORKING baseline (perceive from spawn) ==========
    _log("=== CASE A: perceive from SPAWN (~10.0, 3.0, +X) — the proven afar perceive ===")
    # Make sure we are at the clean spawn pose: reset to +X at spawn xy.
    _snap_heading_plus_x(base)
    time.sleep(0.5)
    report["A_working"] = perceive_instrumented(perception, base, "A_spawn")

    # ================= CASE B — FAILING (FAR -> dock -> perceive) ===============
    _log("=== CASE B: FAR navigate to table, then HEAD dock, then perceive ===")
    # 1. drive AWAY first so FAR genuinely crosses back (honest "FAR drove it").
    try:
        _log("B: pre-drive AWAY to (16.0, 2.8)")
        base.navigate_to(16.0, 2.8, timeout=45.0)
    except Exception as exc:  # noqa: BLE001
        _log(f"B pre-drive raised: {exc}")
    try:
        if os.path.exists("/tmp/vector_nav_active"):
            os.remove("/tmp/vector_nav_active")
        base.stop()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(1.0)

    # 2. FAR navigate to the table vicinity (the chain's navigate leg).
    try:
        _log(f"B: FAR navigate_to table ({_TABLE_X}, {_TABLE_Y})")
        base.navigate_to(_TABLE_X, _TABLE_Y, timeout=90.0)
    except Exception as exc:  # noqa: BLE001
        _log(f"B FAR navigate raised: {exc}")
    try:
        if os.path.exists("/tmp/vector_nav_active"):
            os.remove("/tmp/vector_nav_active")
        base.stop()
    except Exception:  # noqa: BLE001
        pass
    time.sleep(1.5)
    report["B_after_far"] = {"dog_pose": _pose(base)}
    _log(f"B: after FAR pose={report['B_after_far']['dog_pose']}")
    # perceive right after FAR (no dock) — what the camera frames at the raw arrival
    report["B_perceive_after_far"] = perceive_instrumented(perception, base, "B_after_far")

    # 3. HEAD terminal_dock to the FIXED proven pose (10.0, 3.0, 0.0).
    _log("B: terminal_dock to FIXED proven pose (10.0, 3.0, 0.0)")
    try:
        terminal_dock(base, (_DOCK_X, _DOCK_Y), _DOCK_HD,
                      on_progress=lambda m: _log(f"B dock {m}"))
    except Exception as exc:  # noqa: BLE001
        _log(f"B dock raised: {exc}")
    time.sleep(1.0)
    report["B_after_dock"] = {"dog_pose": _pose(base)}
    _log(f"B: after dock pose={report['B_after_dock']['dog_pose']}")

    # 4. perceive at the docked pose — the FAILING perceive moment.
    report["B_failing"] = perceive_instrumented(perception, base, "B_docked")

    # ================= FALSIFICATION EXPERIMENTS ===============================
    exp: dict = {}

    # H1 — drive back to the afar x (~10.0) at the docked heading and re-perceive.
    # If the cans reappear, the failure is being TOO FAR FORWARD (past the afar spot).
    _log("=== H1: drive to afar x=10.0 (centerline, +X) via dock, re-perceive ===")
    try:
        terminal_dock(base, (_DOCK_X, _DOCK_Y), _DOCK_HD,
                      on_progress=lambda m: _log(f"H1 dock {m}"))
    except Exception as exc:  # noqa: BLE001
        _log(f"H1 dock raised: {exc}")
    _snap_heading_plus_x(base)
    time.sleep(0.8)
    exp["H1_afar_x10_plusx"] = perceive_instrumented(perception, base, "H1_afar")

    # H2 — at WHATEVER the current xy is, snap heading to +X only, re-perceive.
    # Isolates heading from x: if H1 already at x10 this confirms heading effect.
    _log("=== H2: snap heading to +X in place, re-perceive (heading isolation) ===")
    _snap_heading_plus_x(base)
    time.sleep(0.8)
    exp["H2_heading_plusx"] = perceive_instrumented(perception, base, "H2_heading")

    # H3 — standoff sweep: walk forward in small steps from x~10.0 toward the table,
    # perceiving at each x. Find where the cans frame vs where they vanish (D34).
    _log("=== H3: standoff sweep x=10.0 -> table, perceive at each step ===")
    sweep = []
    _snap_heading_plus_x(base)
    time.sleep(0.6)
    for i in range(8):
        p = _pose(base)
        r = perceive_instrumented(perception, base, f"H3_sweep_{i}", save_frame=(i % 2 == 0))
        sweep.append({"step": i, "pose": p, "mask_px": r.get("mask_px"),
                      "grasp_world": r.get("grasp_world"),
                      "grasp_z_floor": r.get("grasp_z_floor"),
                      "depth_med_m": r.get("depth_med_m"),
                      "n_detections": r.get("n_detections")})
        # step ~10 cm forward toward the table (heading is +X)
        try:
            base.walk(vx=0.35, vy=0.0, vyaw=0.0, duration=0.7)
        except Exception:  # noqa: BLE001
            break
        time.sleep(0.4)
        # keep heading clamped +X so the sweep isolates x only
        _snap_heading_plus_x(base, timeout=2.0)
        time.sleep(0.3)
    exp["H3_standoff_sweep"] = sweep

    # H4 — cam_xpos vs the live dog pose: is the bridge cam pose updated/sane?
    # Compare cam_xpos to dog (x,y) + expected mount offset (0.25 fwd, 0.10 up).
    _log("=== H4: cam_xpos vs live dog pose (stale/garbage cam pose check) ===")
    dp = _pose(base)
    try:
        import numpy as np
        cxp, cxm = perception.get_camera_pose()
        cxp = np.asarray(cxp, dtype=float).reshape(-1)
        # expected cam xy ~ dog xy + 0.25 m forward along heading
        h = dp[2]
        exp_x = dp[0] + 0.25 * math.cos(h)
        exp_y = dp[1] + 0.25 * math.sin(h)
        exp["H4_cam_vs_dog"] = {
            "dog_pose": dp,
            "cam_xpos": [round(float(v), 4) for v in cxp[:3]],
            "expected_cam_xy_from_dog": [round(exp_x, 3), round(exp_y, 3)],
            "cam_xy_err_m": round(math.hypot(cxp[0] - exp_x, cxp[1] - exp_y), 3),
            "cam_z_m": round(float(cxp[2]), 3),
        }
        _log(f"H4: dog={dp} cam_xpos={exp['H4_cam_vs_dog']['cam_xpos']} "
             f"err={exp['H4_cam_vs_dog']['cam_xy_err_m']}m cam_z={exp['H4_cam_vs_dog']['cam_z_m']}")
    except Exception as e:  # noqa: BLE001
        exp["H4_cam_vs_dog"] = {"error": str(e)}

    report["experiments"] = exp

    path = os.path.join(ART, "ab_debug.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
    _log(f"report written: {path}")

    # Compact A-vs-B summary line
    A = report["A_working"]
    B = report["B_failing"]
    _log("=== A vs B SUMMARY ===")
    _log(f"A(spawn)  pose={A.get('dog_pose')} cam_xpos={A.get('cam_xpos')} "
         f"mask_px={A.get('mask_px')} grasp_world={A.get('grasp_world')} floor={A.get('grasp_z_floor')}")
    _log(f"B(docked) pose={B.get('dog_pose')} cam_xpos={B.get('cam_xpos')} "
         f"mask_px={B.get('mask_px')} grasp_world={B.get('grasp_world')} floor={B.get('grasp_z_floor')}")
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        rc = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
