#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R5 CORRECTION re-verify (moat integrity): the SAME bare-cli g1-detect drive as
R4, asserting the moat now grades the self-read detect **RAN** (not GROUNDED).

R4 (D60) graded the g1 detect GROUNDED via a self-certifying detect_objects()
oracle (read agent._last_detection = the detector's OWN boxes). Red-team caught
it (D61). R5 removed that world-side oracle; with no detect_objects in the g1
verify namespace, classify_verify_expr returns RAN (fail-closed to the honest
D50 grade) — spine byte-unchanged.

This re-drives the literal two-turn cli.main REPL (reusing the R4 harness) and
CONFIRMS:
  (1) the detector STILL routes to g1's head camera + localizes the red object
      (the cross-EMBODIMENT x cross-MODEL route is intact);
  (2) the verdict is now **RAN** (NOT GROUNDED) — the self-certification no
      longer greens.
Saves the transcript to /tmp/r5_g1_detect_ran.txt.

Usage (foreground, lead-run, serialized; sim torn down after):
    HF_HOME=/home/yusen/.cache/huggingface MUJOCO_GL=egl \
    PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r5_g1_detect_ran.py
"""
from __future__ import annotations

import os
import re
import sys

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "/home/yusen/.cache/huggingface")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the R4 harness verbatim (the wiring under test is identical; only the
# moat GRADE is expected to flip from GROUNDED -> RAN after the R5 fix).
import scripts.probe_r4_g1_detect as r4  # noqa: E402

_R5_TX = "/tmp/r5_g1_detect_ran.txt"


def _run_repl_r5() -> tuple[bool, str, bool]:
    from tests.harness.pty_cli import run_repl_session

    print("[r5] REPL re-verify: two-turn bare cli.main — g1 switch + detect red")
    result = run_repl_session(
        [
            (0.0, "启动 g1 仿真"),       # turn 1: NL embodiment switch
            (30.0, r4._QUERY_ZH),        # turn 2: NL detect on g1's camera
            (45.0, "quit"),
        ],
        tool_script=r4._TOOL_SCRIPT,
        native=True,
        boot_sec=8.0,
        settle_sec=10.0,
        extra_args=["--native-first"],
    )
    text = r4._strip(result.transcript)
    with open(_R5_TX, "w") as fh:
        fh.write(text)
    print(f"[r5] transcript saved -> {_R5_TX} ({len(text)} chars), exit={result.exit_code}")

    def _grep(pat: str) -> list[str]:
        return [ln for ln in text.splitlines() if re.search(pat, ln, re.I)]

    started = bool(_grep(r"start.*sim|g1.*仿真|MuJoCoG1|sim_type=g1"))
    detect_lines = _grep(r"detect|grounding-dino|localized|box|找前面")
    verdict_lines = _grep(r"verdict|VERDICT|GROUNDED|RAN|verified|evidence|detect_objects")

    print("\n[r5] --- evidence from transcript ---")
    print(f"[r5] embodiment-switch to g1 seen: {started}")
    for ln in detect_lines[-8:]:
        print(f"[r5]   det> {ln.strip()[:160]}")
    for ln in verdict_lines[-8:]:
        print(f"[r5]   vrd> {ln.strip()[:160]}")

    ran = any("RAN" in ln for ln in verdict_lines)
    grounded = any("GROUNDED" in ln for ln in verdict_lines)
    localized = any("localized" in ln.lower() for ln in detect_lines)
    routed = bool(detect_lines)
    grade = "GROUNDED" if grounded else ("RAN" if ran else "NO-VERDICT")

    # R5 acceptance: the route still works (started + routed/localized) AND the
    # verdict is RAN, NOT GROUNDED (the false green is gone).
    route_ok = started and routed
    grade_ok = ran and not grounded
    print(f"\n[r5] REPL VERDICT: route_ok={route_ok} (started={started}, "
          f"routed={routed}, localized={localized}); moat grade={grade}; "
          f"grade_ok(RAN, not GROUNDED)={grade_ok}")
    return route_ok, grade, grade_ok


def main() -> int:
    # FRAME first (in-process; confirms the model still localizes on g1's camera),
    # then the bare-cli REPL re-verify (separate child, serialized after teardown).
    frame_ok, frame_report = r4._run_frame()
    route_ok, grade, grade_ok = _run_repl_r5()

    print("\n" + "=" * 70)
    print("[r5] FINAL VERDICT (R5 moat-correction re-verify on g1):")
    print(f"[r5]   detector STILL routed + localized on g1's camera: {route_ok and frame_ok}")
    print(f"[r5]   grounding-dino box ON the red object (frame): {frame_ok}")
    print(f"[r5]   moat grade now: {grade} (must be RAN, not GROUNDED)")
    print(f"[r5]   FALSE-GREEN FIXED (RAN, not GROUNDED): {grade_ok}")
    passed = route_ok and frame_ok and grade_ok
    print(f"[r5]   R5 CORRECTION VERIFIED: {'YES' if passed else 'NO'}")
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        rc = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
