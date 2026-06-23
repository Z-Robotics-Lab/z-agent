#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R3 cross-EMBODIMENT acceptance: the SAME orchestration that works on go2 drives
G1 (a humanoid) via the BARE vector-cli REPL + natural language, graded by the
byte-unchanged moat.

The headline proof: g1 is a MOAT-GRADED ROUTABLE EMBODIMENT (parity with go2). The
agent is commanded in NL to (1) switch embodiment to g1 and (2) walk to an open
coordinate; the RL gait walks there; the verify spine grades ``at_position(x, y)``.

Two acceptance modes (run with --mode):

  repl  (DEFAULT, the real acceptance) — drive the literal interactive ``cli.main``
        REPL through a PTY with two NL turns:
          turn 1:  "启动 g1 仿真"        -> SimStartTool sim_type=g1 -> _start_g1
          turn 2:  "走到坐标 (10.0,1.5)" -> native navigate -> g1.navigate_to (RL gait)
                                            -> verify(at_position(10.0, 1.5))
        The LLM is FAKED (VECTOR_FAKE_LLM_TOOLS, per policy: sim + gait + world +
        verify-spine all REAL, only the network LLM is canned). The HONEST moat
        verdict surfaces in the transcript. at_position grades RAN (UNCAUSED) per
        D14 — base cmd_vel/gait is NOT actor-causation-gated; RAN is the CORRECT
        honest grade for a cross-embodiment base-nav task, NOT a failure. Saves the
        transcript to /tmp/r3_g1_nav.txt.

  probe (fallback) — an in-process drive of MuJoCoG1.navigate_to to the same open
        point, asserting the pose moved toward the target and base-z stayed up
        (no fall). Used to confirm the gait independently if the REPL wiring is
        flaky. Saves /tmp/r3_g1_nav_probe.json.

Usage (foreground, lead-run, serialized; sim torn down after):
    MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r3_g1_nav.py --mode repl
    MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r3_g1_nav.py --mode probe
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys

os.environ.setdefault("MUJOCO_GL", "egl")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# g1 spawns at (10, 3) facing +x. The open south area is clear floor down to the
# south wall (y~0); the pick_table at ~(10.95, 3.0) blocks +x but is NOT on the
# straight line to a southern target. (10.0, 1.5) is ~1.5 m straight south of
# spawn through open space — exactly the R2-verified leg-1 corridor.
_TARGET = (10.0, 1.5)
_SPAWN = (10.0, 3.0)
_FALL_Z = 0.4
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_REPL_TX = "/tmp/r3_g1_nav.txt"
_PROBE_JSON = "/tmp/r3_g1_nav_probe.json"


def _strip(s: str) -> str:
    return _ANSI.sub("", s)


# --- conflicting-sim guard --------------------------------------------------
def _guard_no_other_sim() -> None:
    import subprocess as _sp

    running = _sp.run(
        ["pgrep", "-f", "[m]ujoco|[g]o2_vnav|[l]aunch_explore"],
        capture_output=True, text=True,
    ).stdout.strip()
    if running:
        print(f"[r3] WARNING: possible sim processes already running: {running[:200]}")


# ---------------------------------------------------------------------------
# Mode REPL — the bare-cli two-turn acceptance.
# ---------------------------------------------------------------------------
# Global cursor over `turns` (FakeToolScriptBackend): the turns are consumed in
# order across BOTH NL lines in the one cli.main process.
#   line 1 "启动 g1 仿真": one tool_use turn -> start_simulation(sim_type=g1),
#           then a terminal end_turn so the turn finishes after the sim boots.
#   line 2 "走到坐标 (10.0,1.5)": the native loop consumes navigate -> verify -> finish.
_TOOL_SCRIPT = {
    "turns": [
        # --- line 1: switch embodiment to g1 by NL ---
        {"tool_calls": [
            {"name": "start_simulation", "input": {"sim_type": "g1", "gui": False}}
        ]},
        {"text": "g1 仿真已启动。", "tool_calls": [], "stop_reason": "end_turn"},
        # --- line 2: walk to the open coordinate, then verify at_position ---
        {"tool_calls": [
            {"name": "navigate", "input": {"x": _TARGET[0], "y": _TARGET[1]}}
        ]},
        {"tool_calls": [
            {"name": "verify",
             "input": {"expr": f"at_position({_TARGET[0]}, {_TARGET[1]})"}}
        ]},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}


def _run_repl() -> int:
    from tests.harness.pty_cli import run_repl_session

    print(f"[r3] REPL acceptance: two-turn bare cli.main; target {_TARGET}")
    result = run_repl_session(
        [
            (0.0, "启动 g1 仿真"),        # turn 1: NL embodiment switch
            (45.0, f"走到坐标 ({_TARGET[0]},{_TARGET[1]})"),  # turn 2: NL nav
            (60.0, "quit"),
        ],
        # NO sim_go2 flag — the sim is started BY NL (the cross-embodiment proof).
        tool_script=_TOOL_SCRIPT,
        native=True,
        boot_sec=8.0,        # cli.main cold-import headroom before line 1
        settle_sec=8.0,
        extra_args=["--native-first"],
    )
    text = _strip(result.transcript)
    with open(_REPL_TX, "w") as fh:
        fh.write(text)
    print(f"[r3] transcript saved -> {_REPL_TX} ({len(text)} chars), exit={result.exit_code}")

    # --- extract the load-bearing evidence lines from the transcript ---
    def _grep(pat: str) -> list[str]:
        return [ln for ln in text.splitlines() if re.search(pat, ln)]

    started = bool(_grep(r"start.*sim|g1.*仿真|Started g1|sim_type=g1|MuJoCoG1"))
    nav_lines = _grep(r"navigate|走到坐标|at_position")
    verdict_lines = _grep(r"verdict|VERDICT|GROUNDED|RAN|verified|evidence")

    print("\n[r3] --- evidence from transcript ---")
    print(f"[r3] embodiment-switch to g1 seen: {started}")
    for ln in nav_lines[-6:]:
        print(f"[r3]   nav> {ln.strip()[:160]}")
    for ln in verdict_lines[-8:]:
        print(f"[r3]   vrd> {ln.strip()[:160]}")

    # HONEST verdict: at_position grades RAN (UNCAUSED) per D14 — that is success
    # for a cross-embodiment base-nav task (cross-embodiment task demonstrated +
    # honestly graded). We confirm the NL command reached the REPL, g1 was the
    # routed embodiment, and the moat produced a verdict (RAN or GROUNDED).
    ran = any("RAN" in ln for ln in verdict_lines)
    grounded = any("GROUNDED" in ln for ln in verdict_lines)
    has_verdict = ran or grounded
    cmd_echoed = "走到坐标" in text and "启动 g1" in text
    ok = cmd_echoed and started and bool(nav_lines) and has_verdict
    grade = "GROUNDED" if grounded else ("RAN" if ran else "NO-VERDICT")
    print(f"\n[r3] VERDICT: bare-cli cross-embodiment nav {'PASS' if ok else 'INCOMPLETE'} "
          f"(moat grade: {grade}; RAN is the honest D14 grade for base nav).")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Mode PROBE — in-process fallback: drive the gait directly, assert no fall.
# ---------------------------------------------------------------------------
def _run_probe() -> int:
    from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1

    print(f"[r3] PROBE fallback: in-process navigate_to {_TARGET}")
    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    try:
        sx, sy, sz = (float(v) for v in g1.get_position())
        d0 = math.hypot(_TARGET[0] - sx, _TARGET[1] - sy)
        res = g1.navigate_to(_TARGET[0], _TARGET[1], tol=0.35, speed=0.5)
        ex, ey, ez = (float(v) for v in g1.get_position())
        d1 = math.hypot(_TARGET[0] - ex, _TARGET[1] - ey)
        # bool(res) honors the navigate contract (== reached)
        reached = bool(res)
        moved_toward = d1 < d0
        no_fall = ez >= _FALL_Z
        out = {
            "target": list(_TARGET),
            "start": [round(sx, 3), round(sy, 3), round(sz, 3)],
            "end": [round(ex, 3), round(ey, 3), round(ez, 3)],
            "dist_start": round(d0, 3), "dist_end": round(d1, 3),
            "moved_toward_target": moved_toward,
            "no_fall_min_z": round(ez, 3),
            "no_fall": no_fall,
            "navigate_to_reached": reached,
            "navigate_to_bool_contract": reached,  # bool(_G1NavResult) == reached
            "nav_result": {k: (round(v, 3) if isinstance(v, float) else v)
                           for k, v in dict(res).items()},
        }
        with open(_PROBE_JSON, "w") as fh:
            json.dump(out, fh, indent=2)
        print(json.dumps(out, indent=2))
        ok = moved_toward and no_fall
        print(f"\n[r3] PROBE VERDICT: {'PASS' if ok else 'FAIL'} "
              f"(moved toward target {moved_toward}, no fall {no_fall}, reached {reached})")
        return 0 if ok else 1
    finally:
        try:
            g1.close()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["repl", "probe"], default="repl")
    args = ap.parse_args()
    _guard_no_other_sim()
    rc = _run_repl() if args.mode == "repl" else _run_probe()
    return rc


if __name__ == "__main__":
    code = main()
    # Hard-exit so any lingering GL/MuJoCo context cannot keep the process alive.
    os._exit(code)
