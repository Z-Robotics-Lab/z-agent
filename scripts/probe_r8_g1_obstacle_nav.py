#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R8 REAL-VERIFY — g1 routes AROUND an obstacle to reach a straight-line-BLOCKED
goal, instead of walking into it (the R2/R3 open-loop failure).

The proof, in the REAL sim, eyes-on:

  g1 spawns at (10, 3) facing +x. The pick_table sits at (10.95, 3.0) with
  half-extents (0.15, 0.25) -> it occupies x in [10.80, 11.10], y in [2.75, 3.25],
  squarely on g1's +x heading. A goal DEAD AHEAD past the table (12.0, 3.0) has a
  straight line that crosses the table -> the OLD open-loop navigate_to drove g1
  straight into it and stalled (~x 10.73, R2). The NEW navigate_to plans a
  visibility-graph path that DETOURS around the table and the RL gait follows the
  waypoint chain to the goal.

This probe runs TWO contrasting trials in ONE sim, serialized:
  (A) BASELINE — straight-line walk toward the blocked goal with NO plan
      (low-level set_velocity toward goal). Expect: STALL against the table,
      does NOT reach. This reproduces the R2 failure for the contrast.
  (B) PLANNED  — g1.navigate_to(blocked_goal): plans the vgraph chain, walks it.
      Expect: trajectory BENDS around the table, REACHES (at_position within tol),
      NO fall.

It logs both trajectories + the planned waypoint chain to /tmp/r8_g1_nav.json,
saves a top-down trajectory plot /tmp/r8_g1_nav.png (the detour is visible), and a
g1 head-camera frame at the goal /tmp/r8_g1_goal.png. Then a bare-cli check via the
PTY REPL: "切换到 g1 仿真" -> "走到坐标 (blocked goal)" -> at_position grades RAN
(HONEST, D14 — base gait is UNCAUSED; RAN is correct, not a failure), g1 reached
via the detour.

HONEST: if the humanoid gait cannot reliably follow the chain in the tight room, the
report says so (stall/fall = honest failure, never faked). plan_path returning inf
(boxed in / goal in obstacle) is a LOUD honest 'unreachable', not a phantom reach.

Usage (foreground, lead-run, serialized; sim torn down after):
    MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r8_g1_obstacle_nav.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "/home/yusen/.cache/huggingface")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_JSON_OUT = "/tmp/r8_g1_nav.json"
_PLOT_OUT = "/tmp/r8_g1_nav.png"
_GOAL_FRAME = "/tmp/r8_g1_goal.png"
_REPL_TX = "/tmp/r8_g1_repl.txt"

_SPAWN = (10.0, 3.0)
# Dead ahead on the +x heading, PAST the pick_table (10.95, hx 0.15 -> far edge
# 11.10). Straight line spawn->goal crosses the table -> old code stalled here.
_GOAL = (12.0, 3.0)
_TABLE_C = (10.95, 3.0)
_TABLE_HX, _TABLE_HY = 0.15, 0.25
_TOL = 0.35
_FALL_Z = 0.4
_SIM_DT = 0.002
_DECIMATION = 10


def _strip(s: str) -> str:
    return _ANSI.sub("", s)


def _seg_hits_table(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Does segment a->b cross the (uninflated) pick_table AABB? Sampled — just to
    label the goal as 'straight-line-blocked' in the report (honest framing)."""
    x0, y0 = a
    x1, y1 = b
    for i in range(101):
        t = i / 100.0
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if abs(x - _TABLE_C[0]) <= _TABLE_HX and abs(y - _TABLE_C[1]) <= _TABLE_HY:
            return True
    return False


def _sample_pos(g1) -> tuple[float, float, float]:
    p = g1.get_position()
    return float(p[0]), float(p[1]), float(p[2])


def _baseline_straight(g1, goal: tuple[float, float], max_ticks: int = 220) -> dict:
    """Reproduce the R2 open-loop failure: steer straight at the goal with raw
    set_velocity, NO planning. Expect a stall against the table."""
    traj: list[list[float]] = []
    gx, gy = goal
    min_z = 9.9
    for _ in range(max_ticks):
        cx, cy, cz = _sample_pos(g1)
        traj.append([round(cx, 3), round(cy, 3), round(cz, 3)])
        min_z = min(min_z, cz)
        if cz < _FALL_Z:
            break
        dx, dy = gx - cx, gy - cy
        dist = math.hypot(dx, dy)
        if dist < _TOL:
            break
        desired = math.atan2(dy, dx)
        yaw_err = desired - g1.get_heading()
        while yaw_err > math.pi:
            yaw_err -= 2 * math.pi
        while yaw_err < -math.pi:
            yaw_err += 2 * math.pi
        if abs(yaw_err) > 0.35 and dist > 0.5:
            g1.set_velocity(0.0, 0.0, max(-0.6, min(0.6, 2.0 * yaw_err)))
        else:
            g1.set_velocity(0.5, 0.0, max(-0.6, min(0.6, 2.0 * yaw_err)))
        g1.step(5)
    g1.stop()
    cx, cy, cz = _sample_pos(g1)
    return {
        "trajectory": traj,
        "end": [round(cx, 3), round(cy, 3), round(cz, 3)],
        "dist_end": round(math.hypot(gx - cx, gy - cy), 3),
        "reached": math.hypot(gx - cx, gy - cy) < _TOL,
        "min_z": round(min_z, 3),
        "fell": min_z < _FALL_Z,
        "max_x": round(max((t[0] for t in traj), default=cx), 3),
    }


def _planned_nav(g1, goal: tuple[float, float]) -> dict:
    """The NEW navigate_to: plan the vgraph chain, walk it. We record g1's
    trajectory by polling between sub-walks via an on_progress sampler if the base
    supports it; otherwise we reconstruct from the returned result + a coarse
    re-poll. We also read the planned chain off the instance (_last_nav_plan)."""
    traj: list[list[float]] = []

    def _on_progress(*_a, **_k) -> None:
        try:
            cx, cy, cz = _sample_pos(g1)
            traj.append([round(cx, 3), round(cy, 3), round(cz, 3)])
        except Exception:  # noqa: BLE001
            pass

    sx, sy, sz = _sample_pos(g1)
    traj.append([round(sx, 3), round(sy, 3), round(sz, 3)])
    # navigate_to ignores unknown kwargs; on_progress is sampled if honored.
    res = g1.navigate_to(goal[0], goal[1], tol=_TOL, speed=0.5, on_progress=_on_progress)
    ex, ey, ez = _sample_pos(g1)
    traj.append([round(ex, 3), round(ey, 3), round(ez, 3)])

    plan = getattr(g1, "_last_nav_plan", None)
    plan_pts = [[round(float(p[0]), 3), round(float(p[1]), 3)] for p in plan] if plan else None
    return {
        "planned_waypoints": plan_pts,
        "trajectory": traj,
        "result": {k: (round(v, 3) if isinstance(v, float) else v)
                   for k, v in dict(res).items()},
        "reached": bool(res),
        "end": [round(ex, 3), round(ey, 3), round(ez, 3)],
        "dist_end": round(math.hypot(goal[0] - ex, goal[1] - ey), 3),
        "min_z": round(min((t[2] for t in traj), default=ez), 3),
    }


def _plot(obstacles, baseline, planned, goal) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPoly

        fig, ax = plt.subplots(figsize=(8, 8))
        for poly in obstacles:
            ax.add_patch(MplPoly(poly, closed=True, facecolor="#b0b0b8",
                                 edgecolor="#606068", alpha=0.6))
        bt = baseline["trajectory"]
        pt = planned["trajectory"]
        if bt:
            ax.plot([p[0] for p in bt], [p[1] for p in bt], "-", color="#d04030",
                    lw=2, label="baseline straight-line (stalls)")
        if pt:
            ax.plot([p[0] for p in pt], [p[1] for p in pt], "-", color="#2060d0",
                    lw=2, label="planned vgraph (detour)")
        wp = planned.get("planned_waypoints")
        if wp:
            ax.plot([p[0] for p in wp], [p[1] for p in wp], "o--", color="#20a020",
                    lw=1.2, ms=7, label="vgraph waypoints")
        ax.plot(*_SPAWN, "ks", ms=12, label="spawn (10,3)")
        ax.plot(*goal, "g*", ms=20, label="goal (blocked straight-line)")
        ax.set_title("R8 — g1 routes AROUND the pick_table (top-down)")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_aspect("equal")
        ax.legend(loc="upper left", fontsize=8)
        ax.set_xlim(9.0, 13.0)
        ax.set_ylim(1.5, 4.5)
        ax.grid(alpha=0.3)
        fig.savefig(_PLOT_OUT, dpi=110, bbox_inches="tight")
        plt.close(fig)
        print(f"[r8] top-down trajectory plot saved -> {_PLOT_OUT}")
    except Exception as exc:  # noqa: BLE001
        print(f"[r8] plot skipped: {exc}")


def _goal_frame(g1) -> None:
    try:
        from PIL import Image
        from vector_os_nano.perception.g1_head_perception import G1HeadPerception
        rgb = G1HeadPerception(g1, width=640, height=480).get_color_frame()
        Image.fromarray(rgb.astype("uint8"), "RGB").save(_GOAL_FRAME)
        print(f"[r8] goal-vantage head frame saved -> {_GOAL_FRAME}")
    except Exception as exc:  # noqa: BLE001
        print(f"[r8] goal frame skipped: {exc}")


def _run_sim() -> dict:
    from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1, obstacles_from_model

    blocked = _seg_hits_table(_SPAWN, _GOAL)
    print(f"[r8] goal {_GOAL}: straight line from spawn crosses pick_table? {blocked}")

    # --- Trial B (planned) gets a FRESH stance so the baseline stall doesn't
    #     bias it. We run baseline first on one instance, then planned on a
    #     fresh instance — serialized, one sim at a time. ---
    print("[r8] === TRIAL A: baseline straight-line (expect stall at table) ===")
    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    try:
        g1.step(60)  # settle stance
        import mujoco
        mujoco.mj_forward(g1._model, g1._data)
        obstacles = obstacles_from_model(
            g1._model, g1._data,
            getattr(g1._offsets, "robot_geom_ids", None),
        )
        print(f"[r8] obstacles enumerated from live scene: {len(obstacles)} polygons")
        baseline = _baseline_straight(g1, _GOAL)
        print(f"[r8] baseline: reached={baseline['reached']} dist_end={baseline['dist_end']} "
              f"max_x={baseline['max_x']} (table near edge x=10.80)")
    finally:
        g1.close()

    print("[r8] === TRIAL B: planned navigate_to (expect detour + reach) ===")
    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    try:
        g1.step(60)
        planned = _planned_nav(g1, _GOAL)
        print(f"[r8] planned: reached={planned['reached']} dist_end={planned['dist_end']} "
              f"min_z={planned['min_z']} waypoints={planned['planned_waypoints']}")
        if planned["reached"]:
            _goal_frame(g1)
    finally:
        g1.close()

    _plot(obstacles, baseline, planned, _GOAL)

    report = {
        "spawn": list(_SPAWN),
        "goal": list(_GOAL),
        "goal_straight_line_blocked_by_table": blocked,
        "pick_table": {"center": list(_TABLE_C), "half": [_TABLE_HX, _TABLE_HY]},
        "n_obstacles": len(obstacles),
        "baseline_straight": baseline,
        "planned_navigate": planned,
        "detour_observed": _detour_metric(planned),
    }
    with open(_JSON_OUT, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"[r8] full report -> {_JSON_OUT}")
    return report


def _detour_metric(planned: dict) -> dict:
    """A detour = the trajectory leaves the straight-line y=3.0 corridor by more
    than the table half-width before reaching the goal. Quantify the max |y-3.0|
    deviation (a straight walk stays ~0; a real detour exceeds the table half-y)."""
    traj = planned.get("trajectory") or []
    if not traj:
        return {"max_y_dev": 0.0, "is_detour": False}
    max_dev = max(abs(p[1] - _SPAWN[1]) for p in traj)
    # also from the planned chain (more reliable than the sparse polled traj)
    wp = planned.get("planned_waypoints") or []
    max_wp_dev = max((abs(p[1] - _SPAWN[1]) for p in wp), default=0.0)
    dev = max(max_dev, max_wp_dev)
    return {
        "max_y_dev_traj": round(max_dev, 3),
        "max_y_dev_plan": round(max_wp_dev, 3),
        "is_detour": dev > _TABLE_HY,  # left the table's y-band
    }


# ---------------------------------------------------------------------------
# Bare-cli check: NL switch -> NL nav to the blocked goal -> at_position RAN
# ---------------------------------------------------------------------------
_TOOL_SCRIPT = {
    "turns": [
        {"tool_calls": [
            {"name": "start_simulation", "input": {"sim_type": "g1", "gui": False}}
        ]},
        {"text": "g1 仿真已启动。", "tool_calls": [], "stop_reason": "end_turn"},
        {"tool_calls": [
            {"name": "navigate", "input": {"x": _GOAL[0], "y": _GOAL[1]}}
        ]},
        {"tool_calls": [
            {"name": "verify", "input": {"expr": f"at_position({_GOAL[0]}, {_GOAL[1]})"}}
        ]},
        {"text": "已绕过桌子走到坐标。", "tool_calls": [], "stop_reason": "end_turn"},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}


def _run_repl() -> dict:
    from tests.harness.pty_cli import run_repl_session

    print(f"[r8] REPL: bare cli.main — 切换到 g1 + 走到坐标 {_GOAL} (blocked straight-line)")
    result = run_repl_session(
        [
            (0.0, "切换到 g1 仿真"),
            (45.0, f"走到坐标 ({_GOAL[0]},{_GOAL[1]})"),
            (110.0, "quit"),
        ],
        tool_script=_TOOL_SCRIPT,
        native=True,
        boot_sec=8.0,
        settle_sec=10.0,
        extra_args=["--native-first"],
    )
    text = _strip(result.transcript)
    with open(_REPL_TX, "w") as fh:
        fh.write(text)
    print(f"[r8] transcript saved -> {_REPL_TX} ({len(text)} chars), exit={result.exit_code}")

    def _grep(pat: str) -> list[str]:
        return [ln for ln in text.splitlines() if re.search(pat, ln, re.I)]

    started = bool(_grep(r"start.*sim|g1.*仿真|MuJoCoG1|sim_type=g1"))
    nav_lines = _grep(r"navigate|走到坐标|at_position")
    verdict_lines = _grep(r"verdict|VERDICT|GROUNDED|RAN|verified|at_position")
    n_grounded = sum(1 for ln in verdict_lines if "GROUNDED" in ln)
    n_ran = sum(1 for ln in verdict_lines if re.search(r"\bRAN\b", ln))
    print("\n[r8] --- REPL evidence ---")
    for ln in (nav_lines + verdict_lines)[-12:]:
        print(f"[r8]   > {ln.strip()[:160]}")
    return {
        "started": started,
        "nav_seen": bool(nav_lines),
        "n_grounded": n_grounded,
        "n_ran": n_ran,
        "no_false_green": n_grounded == 0,
        "cmd_echoed": ("走到坐标" in text) and ("g1" in text),
        "exit_code": result.exit_code,
        "verdict_lines": [ln.strip()[:160] for ln in verdict_lines],
    }


def main() -> int:
    sim = _run_sim()
    repl = _run_repl()

    base = sim["baseline_straight"]
    plan = sim["planned_navigate"]
    detour = sim["detour_observed"]

    # The headline claim: planned REACHES via a DETOUR where straight-line did NOT.
    planned_reached = plan["reached"]
    planned_no_fall = plan["min_z"] >= _FALL_Z
    is_detour = detour["is_detour"]
    baseline_stalled = not base["reached"]
    repl_honest = repl["started"] and repl["nav_seen"] and repl["no_false_green"]

    print("\n" + "=" * 72)
    print("[r8] FINAL VERDICT — g1 obstacle-aware navigation (honest):")
    print(f"[r8]   goal {_GOAL} straight-line blocked by pick_table: {sim['goal_straight_line_blocked_by_table']}")
    print(f"[r8]   obstacles enumerated from live scene: {sim['n_obstacles']}")
    print(f"[r8]   BASELINE straight-line: reached={base['reached']} (max_x {base['max_x']}, "
          f"dist_end {base['dist_end']}) -> stalled at table: {baseline_stalled}")
    print(f"[r8]   PLANNED waypoints: {plan['planned_waypoints']}")
    print(f"[r8]   PLANNED reached={planned_reached} dist_end={plan['dist_end']} "
          f"min_z={plan['min_z']} (no fall: {planned_no_fall})")
    print(f"[r8]   DETOUR observed (left table y-band): {is_detour} "
          f"(max |y-3.0| traj={detour['max_y_dev_traj']} plan={detour['max_y_dev_plan']})")
    print(f"[r8]   bare-cli: NL drove g1 nav, at_position RAN-honest (GROUNDED={repl['n_grounded']} must be 0, "
          f"RAN={repl['n_ran']}): {repl_honest}")
    passed = (planned_reached and planned_no_fall and is_detour
              and baseline_stalled and repl_honest)
    print(f"[r8]   R8 PASS (routes around table to a blocked goal, baseline stalls, RAN-honest): "
          f"{'YES' if passed else 'PARTIAL/FAIL — see honest notes'}")
    return 0 if passed else 2


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
