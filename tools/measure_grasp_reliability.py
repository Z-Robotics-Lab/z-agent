# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""LIVE-MODEL grasp routing reliability harness (R10/D80 — authorized by Yusen).

Measures the one thing every deterministic seal sidestepped: how reliably does the
REAL model ALONE route a grasp command to a GROUNDED verdict — no scripted backend.

Each attempt is a FRESH, ISOLATED `cli.main -p --sim --native-loop` subprocess (via the
pty harness, live=True so the repo-root .env DeepSeek key drives it): the model sees the
SO-101 arm + the tool descriptions + a Chinese NL grasp command and must autonomously
route pick -> verify(holding_object('banana')) -> finish. The honest spine grades it; a
real weld 0->1 is the only way to earn GROUNDED. We record the outcome of every run
(GROUNDED / RAN / NO_TRACE / ERROR-or-TIMEOUT) and print the reliability rate + the
failure-mode breakdown. Whatever the number is, it is reported honestly.

This is the standalone-arm isolation of the MODEL'S ROUTING reliability (a single -p turn,
no flaky multi-turn REPL launch). The go2+Piper perception_grasp is a harder follow-up.

Run (serialized sim; rosm nuke between runs is built in):
    N_RUNS=10 MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python tools/measure_grasp_reliability.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from tests.harness.pty_cli import run_cli_turn  # noqa: E402

_PROMPT = "把香蕉抓起来拿在手里"
_N = int(os.environ.get("N_RUNS", "10"))
_PER_RUN_TIMEOUT = float(os.environ.get("PER_RUN_TIMEOUT", "200"))


def _nuke() -> None:
    try:
        subprocess.run(["rosm", "nuke", "--yes"], timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass
    subprocess.run("pkill -9 -f '[m]ujoco' 2>/dev/null || true", shell=True)


def main() -> int:
    results: list[dict] = []
    print(f"=== live-model grasp reliability: N={_N}, prompt={_PROMPT!r} ===", flush=True)
    for i in range(_N):
        rec: dict = {"i": i}
        try:
            r = run_cli_turn(
                _PROMPT, sim=True, live=True,
                timeout_sec=_PER_RUN_TIMEOUT,
                extra_args=["--headless", "--native-loop"],
            )
            v = r.verdict or {}
            per_step = v.get("per_step") or []
            rec["outcome"] = v.get("evidence", "NO_TRACE")
            rec["verified"] = bool(v.get("verified", False))
            rec["strategy"] = per_step[0]["strategy"] if per_step else ""
            rec["verify"] = per_step[0]["verify"] if per_step else ""
            rec["exit"] = r.exit_code
        except Exception as exc:  # noqa: BLE001 — a stall/timeout/no-verdict is a real failure mode
            rec["outcome"] = "ERROR"
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        results.append(rec)
        print(f"run {i + 1}/{_N}: {json.dumps(rec, ensure_ascii=False)}", flush=True)
        _nuke()

    grounded = sum(1 for r in results if r.get("outcome") == "GROUNDED" and r.get("verified"))
    ran = sum(1 for r in results if r.get("outcome") == "RAN")
    no_trace = sum(1 for r in results if r.get("outcome") == "NO_TRACE")
    err = sum(1 for r in results if r.get("outcome") == "ERROR")
    print("\n=== RELIABILITY SUMMARY ===", flush=True)
    print(f"GROUNDED+verified : {grounded}/{_N}  ({100.0 * grounded / _N:.0f}%)")
    print(f"RAN (not grounded): {ran}/{_N}")
    print(f"NO_TRACE          : {no_trace}/{_N}")
    print(f"ERROR/TIMEOUT     : {err}/{_N}")
    print("RESULTS_JSON " + json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
