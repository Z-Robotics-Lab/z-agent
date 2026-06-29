#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""measure_fetch_visual — the loop's EYES-ON REAL-VERIFY (ADR-002): N live fetch trials through the
visual acceptance harness (real bare-cli + real DeepSeek routing + real VLM + GT oracle + visual
witness + temporal cross-check). Tallies the GROUNDED rate AND the visual agreement, surfacing
oracle-vs-vision DISAGREEMENTS that a GT-only reliability run is structurally blind to.

This SUBSUMES the GT-only tools/measure_fetch_reliability.py: a green GT number with a vision
disagreement is NOT acceptance — the RESULT carries disagreements so the loop red-teams before
believing the rate. Prints one ``RESULT {json}`` line the loop parses. Uses OFFSCREEN render (sim
frames), so no screen-privacy concern (the attended :0 path is separate + consent-gated).

Usage:
  MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python tools/acceptance/measure_fetch_visual.py --n 5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from tools.acceptance.visual_e2e import _cleanup, run_once  # noqa: E402


def measure(command: str, *, n: int, snapshot_dir: str, timeout: float = 280.0) -> dict:
    recs = []
    for i in range(n):
        rec = run_once(command, snapshot_dir=snapshot_dir, live=True, with_arm=True, timeout=timeout)
        recs.append(rec)
        _cleanup()
        t = rec.get("temporal", {})
        # ``reason`` is the gate decision string; it captures the failure mode when
        # the trial does NOT reach GROUNDED (e.g. the nav/grasp step that failed).
        # Truncated to 80 chars so the trial line stays readable in the loop log.
        diag = (rec.get("reason") or "")[:80]
        print(
            f"TRIAL {i + 1}/{n}: GT={rec['gt']['evidence']} verified={rec['gt']['verified']} "
            f"vision={rec['vision'].get('witness')} temporal={t.get('witness')} "
            f"decision={rec['decision']} disagree={rec['disagreement']} "
            f"diag={diag!r}",
            flush=True,
        )
    grounded = sum(1 for r in recs if r["gt"]["verified"])
    result = {
        "n": n,
        "command": command,
        "grounded": grounded,
        "grounded_rate": round(grounded / n, 3) if n else 0.0,
        "vision_pass": sum(1 for r in recs if r["vision"].get("witness") == "PASS"),
        # The false-green catch: count ONLY trials the GT oracle GROUNDED yet the eyes object to
        # (vision FAIL/ABSTAIN or a temporal motion disagreement on a "verified" turn). A failed
        # trial is already not-acceptance (REJECT) — re-flagging it would be noise, not the D91-D95
        # convincing-but-wrong signal this number exists to surface. >0 here => red-team before
        # believing the grounded_rate.
        "disagreements": sum(1 for r in recs if r["gt"]["verified"] and r["disagreement"]),
        "accept": sum(1 for r in recs if r["decision"] == "ACCEPT"),
        "red_flag": sum(1 for r in recs if r["decision"] == "RED_FLAG"),
        # Per-trial gate reason strings: diagnostic context for failed/red-flag trials
        # (nav failure, grasp miss, perception fault, etc.). Non-empty only on failures;
        # use to distinguish nav_failed vs grasp_missed vs no_detections without a sim run.
        "diagnoses": [r.get("reason", "") for r in recs],
    }
    print("RESULT " + json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="eyes-on fetch reliability (ADR-002 REAL-VERIFY)")
    ap.add_argument("--command", default="把绿色的瓶子拿过来")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--snapshot-dir", default="/tmp/vector_fetch_visual")
    args = ap.parse_args()
    measure(args.command, n=args.n, snapshot_dir=args.snapshot_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
