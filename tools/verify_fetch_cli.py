# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Bare-`vector-cli` + NL end-to-end FETCH acceptance (the non-negotiable face).

Every prior fetch harness builds ``VectorEngine`` / the go2+Piper rig IN-PROCESS and
calls ``run_turn_native`` directly — internal, never the product. THIS harness drives
the ACTUAL entrypoint:

    python -m vector_os_nano.vcli.cli -p "把绿色瓶子拿过来" --sim-go2 --headless --native-loop

through a real PTY with the REAL model (repo-root .env DeepSeek), so the MODEL ALONE
must route the full agent-adaptive fetch on a fresh, EMPTY scene graph:

    look (populate scene graph w/ depth-localized bottles)
      -> navigate_to_object('green bottle')  (drive to the standoff)
      -> perception_grasp('green bottle')    (re-perceive + IK + weld)

and the honest spine grades the verdict (a real 0->1 weld is the only GROUNDED). The
in-process Piper arm is attached by the --sim-go2 path itself (VECTOR_SIM_WITH_ARM=1),
so the fetch is reachable from the bare entrypoint — no ROS2 stack, no flaky multi-turn
REPL. Each attempt is a fresh isolated subprocess (MuJoCo can't realloc worlds);
`rosm nuke` + pkill between. The headline is `grounded/N` and the routing breakdown.

The routing brain + VLM run via OpenRouter (repo-root .env OPENROUTER_API_KEY) —
DeepSeek-direct is frequently network-blocked, OpenRouter is reachable. Force the
provider with VECTOR_PROVIDER=openrouter (+ a concrete VECTOR_MODEL); the
``--sim-go2`` VLM already routes GPT-4o via OpenRouter.

Run (serialized sim):
    N=3 MUJOCO_GL=egl VECTOR_PROVIDER=openrouter VECTOR_MODEL=deepseek/deepseek-chat \
      PATH=/usr/bin:$PATH .venv/bin/python tools/verify_fetch_cli.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from tests.harness.pty_cli import run_cli_turn  # noqa: E402

_PROMPT = os.environ.get("FETCH_PROMPT", "把绿色的瓶子拿给我")
_N = int(os.environ.get("N", "3"))
_PER_RUN_TIMEOUT = float(os.environ.get("PER_RUN_TIMEOUT", "420"))


def _nuke() -> None:
    try:
        subprocess.run(["rosm", "nuke", "--yes"], timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass
    subprocess.run("pkill -9 -f '[m]ujoco' 2>/dev/null || true", shell=True)


def main() -> int:
    results: list[dict] = []
    print(f"=== bare-cli fetch e2e: N={_N}, prompt={_PROMPT!r} ===", flush=True)
    for i in range(_N):
        rec: dict = {"i": i}
        try:
            r = run_cli_turn(
                _PROMPT, sim_go2=True, live=True,
                timeout_sec=_PER_RUN_TIMEOUT,
                extra_env={
                    "VECTOR_SIM_WITH_ARM": "1",
                    "MUJOCO_GL": "egl",
                    # Lightweight fully-in-process path: skip the external ROS2 nav
                    # stack (navigate_to plans via in-process vgraph) so an
                    # unattended round does not OOM/SIGKILL (rc=137 guardrail).
                    "VECTOR_NO_ROS2": "1",
                    # Force OpenRouter for the routing brain: anthropic-direct +
                    # DeepSeek-direct are network-blocked here, and a present
                    # Claude OAuth credential would otherwise hijack resolution to
                    # the dead anthropic endpoint (config.resolve_credentials honors
                    # this forced provider as a hard override). The VLM already
                    # routes GPT-4o via OpenRouter unconditionally.
                    "VECTOR_PROVIDER": os.environ.get("VECTOR_PROVIDER", "openrouter"),
                    "VECTOR_MODEL": os.environ.get("VECTOR_MODEL", "deepseek/deepseek-chat"),
                },
                extra_args=["--headless", "--native-loop"],
            )
            v = r.verdict or {}
            per_step = v.get("per_step") or []
            rec["evidence"] = v.get("evidence", "NO_TRACE")
            rec["verified"] = bool(v.get("verified", False))
            rec["strategies"] = [s.get("strategy", "") for s in per_step]
            rec["exit"] = r.exit_code
        except Exception as exc:  # noqa: BLE001 — a stall/timeout/no-verdict is a real failure mode
            rec["evidence"] = "ERROR"
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:280]}"
        results.append(rec)
        print(f"run {i + 1}/{_N}: {json.dumps(rec, ensure_ascii=False)}", flush=True)
        _nuke()

    grounded = sum(1 for r in results if r.get("evidence") == "GROUNDED" and r.get("verified"))
    routed = sum(1 for r in results if "perception_grasp" in (r.get("strategies") or []))
    print("\n=== FETCH E2E SUMMARY ===", flush=True)
    print(f"GROUNDED+verified : {grounded}/{_N}  ({100.0 * grounded / _N:.0f}%)")
    print(f"routed perception_grasp: {routed}/{_N}")
    print("RESULTS_JSON " + json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
