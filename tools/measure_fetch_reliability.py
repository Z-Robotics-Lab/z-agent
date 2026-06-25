# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Measure end-to-end fetch (find->navigate->grasp) reliability over N fresh sims.

MuJoCo cannot realloc worlds in one process, so each trial is a FRESH subprocess
running tools/verify_fetch_flow.py; we parse its `RESULT {json}` line and tally
overall_pass (the honest grasp verdict: bottle lifted + holding + oracle). A
`rosm nuke --yes` + pkill runs between trials to keep memory bounded (one sim at
a time — OOM safety).

This is the acceptance harness for grasp-reliability work: the headline number is
`grasped/N`. Run BEFORE and AFTER a change; keep the change only if it does not
regress. Red-team the number — it is GT-measured, but N must be >= 5 to trust it.

Usage:
  N=5 MUJOCO_GL=egl PATH=/usr/bin:$PATH .venv/bin/python tools/measure_fetch_reliability.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FLOW = os.path.join(_REPO, "tools", "verify_fetch_flow.py")
_PY = os.path.join(_REPO, ".venv", "bin", "python")


def _nuke() -> None:
    subprocess.run(["rosm", "nuke", "--yes"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "verify_fetch_flow"], capture_output=True)


def main() -> int:
    n = int(os.environ.get("N", "5"))
    env = dict(os.environ)
    env.setdefault("MUJOCO_GL", "egl")
    env["PATH"] = "/usr/bin:" + env.get("PATH", "")

    rows: list[dict] = []
    grasped = 0
    for i in range(1, n + 1):
        _nuke()
        proc = subprocess.run(
            [_PY, _FLOW], cwd=_REPO, env=env,
            capture_output=True, text=True, timeout=600,
        )
        result = None
        for line in proc.stdout.splitlines():
            if line.startswith("RESULT "):
                try:
                    result = json.loads(line[len("RESULT "):])
                except json.JSONDecodeError:
                    result = None
        ok = bool(result and result.get("overall_pass"))
        lifted = None
        diag = None
        if result:
            g = result.get("steps", {}).get("grasp", {})
            lifted = g.get("lifted_m")
            diag = (g.get("diag") or "") or (result.get("steps", {}).get("grasp", {})
                                             .get("diag"))
            # grasp result_data diagnosis is richer; pull from the printed line if present
        grasped += int(ok)
        rows.append({"trial": i, "pass": ok, "lifted_m": lifted,
                     "exit": proc.returncode})
        print(f"trial {i}/{n}: pass={ok} lifted={lifted}", flush=True)
        if not ok and result is None:
            # surface the tail so a crashed trial is debuggable
            tail = "\n".join(proc.stdout.splitlines()[-3:] + proc.stderr.splitlines()[-3:])
            print(f"  (no RESULT; tail) {tail}", file=sys.stderr)
    _nuke()

    rate = grasped / n if n else 0.0
    summary = {"n": n, "grasped": grasped, "rate": round(rate, 3), "rows": rows}
    print("SUMMARY " + json.dumps(summary))
    return 0 if grasped == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
