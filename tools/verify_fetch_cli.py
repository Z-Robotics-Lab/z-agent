# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Bare-`zeno` + NL end-to-end FETCH acceptance (the non-negotiable face).

Every prior fetch harness builds ``VectorEngine`` / the go2+Piper rig IN-PROCESS and
calls ``run_turn_native`` directly — internal, never the product. THIS harness drives
the ACTUAL entrypoint:

    python -m zeno.vcli.cli -p "把绿色瓶子拿过来" --sim-go2 --headless --native-loop

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


# ---------------------------------------------------------------------------
# Pure rec-building helper (unit-testable; no sim / PTY / subprocess)
# ---------------------------------------------------------------------------


def _build_rec(i: int, verdict: dict, exit_code: int) -> dict:
    """Map (trial_index, verdict_dict, exit_code) -> harness result record.

    Pure function — no side effects, no I/O. Takes the parsed VECTOR_VERDICT
    JSON payload and returns the per-run ``rec`` dict the harness appends to
    its results list.

    ``diagnosis`` is the most specific failure signal available:
      1. The last per_step's flat ``diagnosis`` field (StepVerdict surfaces a
         bounded skill-level code, e.g. 'nav_failed', 'no_detections', 'ik_fail').
      2. The last per_step's ``result_data['diagnosis']`` (legacy / if present).
      3. Fall back to the top-level verdict ``error`` string.
      4. None when none is present (e.g. a successful GROUNDED turn).
    """
    per_step: list[dict] = verdict.get("per_step") or []
    last_step: dict = per_step[-1] if per_step else {}
    last_rd: dict = last_step.get("result_data") or {}
    diagnosis = (
        last_step.get("diagnosis")
        or last_rd.get("diagnosis")
        or verdict.get("error")
        or None
    )

    return {
        "i": i,
        "evidence": verdict.get("evidence", "NO_TRACE"),
        "verified": bool(verdict.get("verified", False)),
        "strategies": [s.get("strategy", "") for s in per_step],
        "exit": exit_code,
        "diagnosis": diagnosis,
    }


# ---------------------------------------------------------------------------
# Sim cleanup
# ---------------------------------------------------------------------------


def _nuke() -> None:
    try:
        subprocess.run(["rosm", "nuke", "--yes"], timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass
    # Target ONLY a leaked cli worker, never "mujoco": an autonomous round runs as
    # `claude -p "<loop prompt>"` whose cmdline literally contains "mujoco", so
    # `pkill -f mujoco` SIGKILLs the round itself (self-destruct → zero commits).
    # The in-process sim lives inside the `python -m zeno.vcli.cli`
    # worker, so match that exact module path (absent from the round's cmdline).
    subprocess.run(
        "pkill -9 -f 'zeno.vcli.cli' 2>/dev/null || true", shell=True
    )


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
                    # Serialize sims host-wide: the bare-cli child acquires the
                    # global one-sim lock (ADR-002 Stage 0) so concurrent
                    # autonomous rounds cannot double-drive the sim and OOM.
                    "VECTOR_SIM_LOCK": "1",
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
            rec.update(_build_rec(i, v, r.exit_code))
        except Exception as exc:  # noqa: BLE001 — a stall/timeout/no-verdict is a real failure mode
            rec["evidence"] = "ERROR"
            rec["error"] = f"{type(exc).__name__}: {str(exc)[:280]}"
        results.append(rec)
        print(
            f"run {i + 1}/{_N}: {json.dumps(rec, ensure_ascii=False)}",
            flush=True,
        )
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
