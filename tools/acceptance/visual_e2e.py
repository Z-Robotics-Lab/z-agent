#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""visual_e2e — the visual-acceptance harness (ADR-002): drive a REAL bare ``vector-cli`` turn,
capture a SAME-PROCESS frame, grade it with the frozen GT oracle (the ``VECTOR_VERDICT``) AND the
visual second witness (VisionJudge), and combine them through the DOWNGRADE-ONLY AcceptanceGate.

Emits one ``AcceptanceRecord`` per trial (verdict + frame + vision + gate decision + disagreement).
This is the runnable the ``autonomous-visual-dev`` workflow calls; it is usable WITHOUT the
self-editor (a human / CI / a plug-in developer runs it).

Usage (real LLM+VLM acceptance):
  MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python tools/acceptance/visual_e2e.py \
      --command "把绿色的瓶子拿给我" --n 1 --live
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from tests.harness.pty_cli import run_cli_turn  # noqa: E402
from vector_os_nano.acceptance import gate  # noqa: E402
from vector_os_nano.acceptance import vision_judge as vj  # noqa: E402


def run_once(
    command: str,
    *,
    snapshot_dir: str,
    sim_go2: bool = True,
    live: bool = False,
    tool_script: dict | None = None,
    timeout: float = 240.0,
) -> dict:
    """One real bare-cli turn -> same-process frame -> GT oracle + VisionJudge -> AcceptanceGate."""
    os.makedirs(snapshot_dir, exist_ok=True)
    for f in glob.glob(f"{snapshot_dir}/verdict_*.png"):
        os.remove(f)
    # VECTOR_SIM_LOCK=1: the bare-cli child acquires the global one-sim lock (ADR-002 Stage 0), so
    # every sim this harness drives serializes host-wide. The cli child is the SOLE lock owner — the
    # harness does NOT also lock (that would deadlock its own child).
    env = {
        "VECTOR_SNAPSHOT_DIR": snapshot_dir,
        "MUJOCO_GL": "egl",
        "VECTOR_NO_ROS2": "1",
        "VECTOR_SIM_LOCK": "1",
    }
    r = run_cli_turn(
        command,
        sim_go2=sim_go2,
        live=live,
        tool_script=tool_script,
        timeout_sec=timeout,
        extra_args=["--headless", "--native-loop"],
        extra_env=env,
    )
    verdict = r.verdict or {}
    gt_verified = bool(verdict.get("verified"))
    frames = sorted(glob.glob(f"{snapshot_dir}/verdict_*.png"))
    if frames:
        vv = vj.judge(frames[-1])
        vision = {"witness": vv.witness, "per_item": [list(x) for x in vv.per_item], "model": vv.model}
        witness = vv.witness
    else:
        witness, vision = None, {"witness": None, "reason": "no same-process frame captured"}
    d = gate.decide(gt_verified, witness)
    return {
        "command": command,
        "gt": {"evidence": verdict.get("evidence"), "verified": gt_verified, "exit": r.exit_code},
        "vision": vision,
        "frame": frames[-1] if frames else None,
        "decision": d.decision,
        "disagreement": d.disagreement,
        "needs_red_team": d.needs_red_team,
        "block_headline": d.block_headline,
        "reason": d.reason,
    }


def _cleanup() -> None:
    os.system("rosm nuke --yes >/dev/null 2>&1; pkill -9 -f '[m]ujoco' 2>/dev/null")


def main() -> int:
    ap = argparse.ArgumentParser(description="visual-acceptance E2E harness (ADR-002)")
    ap.add_argument("--command", required=True, help="the natural-language turn for bare vector-cli")
    ap.add_argument("--n", type=int, default=1, help="trials (sim runs are serialized)")
    ap.add_argument("--snapshot-dir", default="/tmp/vector_visual_e2e")
    ap.add_argument("--live", action="store_true", help="use the REAL LLM/VLM (no fake seam)")
    args = ap.parse_args()

    records = []
    for _ in range(args.n):
        rec = run_once(args.command, snapshot_dir=args.snapshot_dir, live=args.live)
        records.append(rec)
        print("RECORD " + json.dumps(rec, ensure_ascii=False))
        _cleanup()
    summary = {
        "n": len(records),
        "accept": sum(1 for r in records if r["decision"] == "ACCEPT"),
        "red_flag": sum(1 for r in records if r["decision"] == "RED_FLAG"),
        "reject": sum(1 for r in records if r["decision"] == "REJECT"),
    }
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
