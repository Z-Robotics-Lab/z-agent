#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""attended — Stage-4 LAUNCHER-TRUTH witness (ADR-002): grab the REAL :0 screen the owner watches and
judge whether a simulator window ACTUALLY opened. A bypassed launcher that claimed a sim but opened
no window grabs as a plain desktop -> simulator_window_present=no -> caught (the GT oracle is blind
to "did a window open on the physical screen"). Also a thin RViz launch+grab for attended demos.

Usage:
  DISPLAY=:0 PATH=/usr/bin:$PATH .venv/bin/python tools/acceptance/attended.py --out-dir /tmp/att
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from vector_os_nano.acceptance import capture  # noqa: E402
from vector_os_nano.acceptance import vision_judge as vj  # noqa: E402


def launcher_truth(out_dir: str, *, display: str = ":0") -> dict:
    """Grab the real screen and judge it: did a simulator window actually open? Returns a dict with
    the witness + the per-item launcher-truth answers, or a no-grab marker."""
    os.makedirs(out_dir, exist_ok=True)
    shot = capture.attended_snapshot(os.path.join(out_dir, "screen.png"), display=display)
    if not shot:
        return {"screen": None, "witness": None, "reason": "screen grab failed (no display / no X auth)"}
    v = vj.judge_attended(shot)
    items = {k: a for k, a, _ in v.per_item}
    return {
        "screen": shot,
        "witness": v.witness,  # FAIL when no sim window is on screen -> a bypassed/never-opened launcher
        "simulator_window_present": items.get("simulator_window_present"),
        "robot_visible": items.get("robot_visible_on_screen"),
        "reasoning": v.reasoning,
        "model": v.model,
    }


def rviz_grab(out_path: str, *, config: str | None = None, settle: float = 8.0, display: str = ":0") -> str | None:
    """Launch rviz2 (optional ``-d config``), let it settle, grab the screen, then kill rviz. For
    attended demos when the full ROS2 nav stack is up (costmap / planned path). Best-effort."""
    env = dict(os.environ)
    env["DISPLAY"] = display
    xa = capture._xauthority()
    if xa:
        env["XAUTHORITY"] = xa
    cmd = ["rviz2"] + (["-d", config] if config else [])
    proc = None
    try:
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(settle)
        return capture.attended_snapshot(out_path, display=display)
    except Exception:  # noqa: BLE001
        return None
    finally:
        if proc is not None:
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage-4 launcher-truth witness (ADR-002)")
    ap.add_argument("--out-dir", default="/tmp/vector_attended")
    ap.add_argument("--display", default=os.environ.get("DISPLAY", ":0"))
    args = ap.parse_args()
    print(json.dumps(launcher_truth(args.out_dir, display=args.display), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
