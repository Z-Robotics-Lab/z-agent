# SPDX-License-Identifier: Apache-2.0
"""Live-model go2+Piper PERCEPTION-grasp reliability orchestrator (R10/D81).

Runs `_live_grasp_go2piper_once.py` N times, each a FRESH isolated subprocess
(MuJoCo can't realloc worlds; isolation also means a stall in one run can't kill the
batch), timeout-guarded, `rosm nuke` between. Aggregates the GROUNDED rate + failure
modes. This is the harder North-Star follow-up to the standalone-arm measurement (D80):
the model alone must route a PERCEPTION grasp (VLM/EdgeTAM -> pointcloud -> IK -> weld).

Run:  N_RUNS=10 MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python tools/measure_go2piper_grasp_reliability.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ONCE = os.path.join(_HERE, "_live_grasp_go2piper_once.py")
_N = int(os.environ.get("N_RUNS", "10"))
_TIMEOUT = float(os.environ.get("PER_RUN_TIMEOUT", "340"))


def _nuke() -> None:
    try:
        subprocess.run(["rosm", "nuke", "--yes"], timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass
    # Target the in-process sim WORKER, not 'mujoco': an autonomous round's `claude -p "<goal>"`
    # cmdline contains "mujoco", so pkill-mujoco would SIGKILL the round itself (rc=137). Same fix
    # as visual_e2e._cleanup / verify_fetch_cli._nuke.
    subprocess.run("pkill -9 -f 'zeno.vcli.cli' 2>/dev/null || true", shell=True)


def main() -> int:
    results: list[dict] = []
    print(f"=== live go2+Piper perception-grasp reliability: N={_N} ===", flush=True)
    env = dict(os.environ)
    for i in range(_N):
        rec: dict = {"i": i}
        try:
            p = subprocess.run(
                [sys.executable, _ONCE],
                cwd=os.path.dirname(_HERE), env=env,
                capture_output=True, text=True, timeout=_TIMEOUT,
            )
            line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
            rec.update(json.loads(line[len("RESULT "):]) if line else {"evidence": "NO_RESULT"})
        except subprocess.TimeoutExpired as te:
            rec["evidence"] = "TIMEOUT"
            # Capture WHAT the run was doing when it timed out (diagnose over-detect vs
            # an early/infra hang). TimeoutExpired carries the partial stdout/stderr.
            partial = ((te.stdout or "") + "\n" + (te.stderr or ""))
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", "replace")
            tail = [ln for ln in partial.splitlines()
                    if any(k in ln for k in ("skill", "strateg", "detect", "look",
                                             "describe", "perception_grasp", "PGRASP",
                                             "step", "RESULT"))]
            rec["timeout_tail"] = tail[-12:]
            rec["timeout_skill_counts"] = {
                k: partial.count(k) for k in ("perception_grasp", "look", "describe_scene",
                                              "detect", "navigate", "pick_top_down")
            }
        except Exception as exc:  # noqa: BLE001
            rec["evidence"] = "ORCH_ERROR"
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        results.append(rec)
        print(f"run {i + 1}/{_N}: {json.dumps(rec, ensure_ascii=False)}", flush=True)
        _nuke()

    grounded = sum(1 for r in results if r.get("evidence") == "GROUNDED" and r.get("verified"))
    print("\n=== RELIABILITY SUMMARY (go2+Piper perception grasp) ===", flush=True)
    print(f"GROUNDED+verified : {grounded}/{_N}  ({100.0 * grounded / _N:.0f}%)")
    for ev in ("RAN", "ERROR", "TIMEOUT", "NO_RESULT", "ORCH_ERROR"):
        c = sum(1 for r in results if r.get("evidence") == ev)
        if c:
            print(f"{ev:18s}: {c}/{_N}")
    print("RESULTS_JSON " + json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
