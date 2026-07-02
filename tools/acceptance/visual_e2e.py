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
from vector_os_nano.acceptance import capture  # noqa: E402
from vector_os_nano.acceptance import gate  # noqa: E402
from vector_os_nano.acceptance import motion_check  # noqa: E402
from vector_os_nano.acceptance import vision_judge as vj  # noqa: E402


def run_once(
    command: str,
    *,
    snapshot_dir: str,
    sim_go2: bool = True,
    live: bool = False,
    tool_script: dict | None = None,
    with_arm: bool = False,
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
        # Use the REAL HOME so the OFFLINE model caches resolve (root-caused 2026-06-30: the PTY
        # harness sets a temp HOME to isolate ~/.vector, but that also moves ~/.cache, so with
        # HF_HUB_OFFLINE=1 the cached grounding-dino (~/.cache/huggingface) + EdgeTAM
        # (Path.home()/.cache/vector_os/models) can't load -> the far recovery's localize returns
        # nothing -> no_detections -> GT=RAN; the eyes harness scored 0/5 far while the DIRECT probe
        # grounded). The native-loop turn does NOT use ~/.vector's goal_templates, so the real HOME
        # is safe + makes the eyes harness match the (grounding) direct probe. extra_env overrides
        # run_cli_turn's temp HOME (it documents this override hook).
        "HOME": os.path.expanduser("~"),
        # Stage 3 per-step temporal strip is OPT-IN (default OFF). Isolated root-cause (2026-06-29):
        # with VECTOR_SNAPSHOT_STRIP=1 a turn SEGFAULTS (NO_TRACE) / corrupts perception
        # (no_detections) — the per-step strip render opens a NEW EGL Renderer context while
        # perception_grasp's cam/depth/seg EGL renderers are live on the same thread (multiple EGL
        # contexts MuJoCo can't co-host -> a C-level crash try/except cannot catch). The SAME turn
        # GROUNDS verified=True with the strip OFF. The strip is a DOWNGRADE-ONLY temporal witness
        # (bonus), so default it OFF — the core acceptance (GT weld + VLM judges the verdict frame)
        # works without it. Re-enable via VECTOR_EYES_STRIP=1 once the GL-context sharing is fixed.
        **({"VECTOR_SNAPSHOT_STRIP": "1"} if os.environ.get("VECTOR_EYES_STRIP") == "1" else {}),
        # The detector (grounding-dino) + segmenter (EdgeTAM) are CACHED locally; force the
        # HF hub OFFLINE so a flaky network can't make perception (detect / the far-fetch
        # recovery's localize) try to phone home to huggingface.co and fail (observed: the
        # whole turn produced no verdict because detect/describe errored on a network blip).
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    if with_arm:
        env["VECTOR_SIM_WITH_ARM"] = "1"  # attach the in-process Piper for fetch/grasp turns
    # fresh strip manifest per trial
    try:
        os.remove(os.path.join(snapshot_dir, "strip.jsonl"))
    except OSError:
        pass
    for _f in glob.glob(f"{snapshot_dir}/frame_*.png"):
        os.remove(_f)
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

    # Stage 3: temporal strip -> montage -> temporal judge (soft) X hard pose-delta cross-check.
    strip = capture.load_strip(snapshot_dir)
    temporal = {"n_frames": len(strip), "witness": None, "disagreement": False}
    if len(strip) >= 2:
        montage_path = capture.montage([s["path"] for s in strip], os.path.join(snapshot_dir, "montage.png"))
        tv = vj.judge_temporal(montage_path) if montage_path else None
        mv = motion_check.cross_check(strip, tv.witness if tv else None)
        temporal = {
            "n_frames": len(strip),
            "witness": (tv.witness if tv else None),
            "moved_m": round(mv.moved_m, 3),
            "hard_moved": mv.hard_moved,
            "disagreement": mv.disagreement,
            "note": mv.note,
            "montage": montage_path,
        }

    temporal_flag = bool(temporal.get("disagreement"))
    # A temporal disagreement must move the DECISION (not only the flags), else the summary
    # accept-count silently hides it. Downgrade-only: it never turns a REJECT into an ACCEPT.
    decision = d.decision
    if temporal_flag and decision == gate.ACCEPT:
        decision = gate.RED_FLAG
    return {
        "command": command,
        "gt": {"evidence": verdict.get("evidence"), "verified": gt_verified, "exit": r.exit_code},
        "vision": vision,
        "temporal": temporal,
        "frame": frames[-1] if frames else None,
        "decision": decision,
        "disagreement": d.disagreement or temporal_flag,
        "needs_red_team": d.needs_red_team or temporal_flag,
        "block_headline": d.block_headline or temporal_flag,
        "reason": d.reason + (f" | TEMPORAL DISAGREEMENT: {temporal.get('note')}" if temporal_flag else ""),
    }


def _cleanup() -> None:
    # Target ONLY the bare-cli sim worker, NEVER 'mujoco'. An autonomous EvolvingLoop round runs
    # as `claude -p "<goal>"` whose cmdline literally contains "mujoco" (the goal's rc=137 guardrail
    # text), so `pkill -9 -f mujoco` SIGKILLs the ROUND ITSELF (rc=137 self-destruct → every round
    # dies at the sim REAL-VERIFY step, committing un-eyes-verified code). The in-process sim lives
    # inside the `python -m vector_os_nano.vcli.cli` child, so match that exact module path (absent
    # from the round's cmdline) — same fix as tools/verify_fetch_cli.py._nuke.
    _teardown = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "scripts", "sim-teardown")
    os.system(f"'{_teardown}' >/dev/null 2>&1; pkill -9 -f 'vector_os_nano.vcli.cli' 2>/dev/null")


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
