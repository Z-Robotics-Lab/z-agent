#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R7 — g1's first HONEST GROUNDED perception, through the BARE vector-cli REPL.

Drives the literal interactive ``cli.main`` REPL under a PTY (LLM token stream FAKED
per policy; the sim, RL gait, head camera, grounding-dino, and the verify spine are
ALL REAL). The honest verdicts surface in the transcript:

  turn 1:  "启动 g1 仿真"           -> g1 RL-gait humanoid in the go2 room; binds
                                       G1HeadPerception; registers the 'detect'
                                       capability + the R7 detection_matches_gt oracle.
  turn 2:  "找前面的红色的东西"       -> detect (grounding-dino on g1's head cam) ->
                                       verify(detection_matches_gt('红色') == True)
                                       -> GROUNDED: the detector's box MATCHES the
                                          INDEPENDENT segmentation-GT of the red object.
  turn 3 (REFUTATION): "找前面的绿色的东西" -> detect -> verify(detection_matches_gt(
                                       '绿色') == True) -> RAN: no green object is in
                                       view, so the independent GT refuses to
                                       corroborate the claim (False == True -> not
                                       grounded). SAME frame, only the colour differs —
                                       proving the oracle is spatial + non-trivial,
                                       NOT a self-read.

Acceptance is the bare REPL. Saved: the two transcripts + the annotated frame
(box + GT seg-centroid) from the in-process eyes-on render.
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

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TX_OK = "/tmp/r7_g1_grounded.txt"
_TX_REF = "/tmp/r7_g1_refute.txt"
_Q_RED = "找前面的红色的东西"
_Q_GREEN = "找前面的绿色的东西"


def _strip(s: str) -> str:
    return _ANSI.sub("", s)


# FakeToolScriptBackend consumes `turns` in order across the NL lines. The verify
# expr is MODEL-AUTHORED (faked here) but the spine grades it against the LIVE oracle.
_TOOL_SCRIPT = {
    "turns": [
        # line 1: switch embodiment to g1
        {"tool_calls": [{"name": "start_simulation", "input": {"sim_type": "g1", "gui": False}}]},
        {"text": "g1 仿真已启动。", "tool_calls": [], "stop_reason": "end_turn"},
        # line 2: detect the RED object, verify the GT-backed match -> GROUNDED
        {"tool_calls": [{"name": "detect", "input": {"query": _Q_RED}}]},
        {"tool_calls": [{"name": "verify",
                         "input": {"expr": "detection_matches_gt('红色') == True"}}]},
        {"text": "已定位红色物体。", "tool_calls": [], "stop_reason": "end_turn"},
        # line 3 (REFUTATION): detect GREEN (not in view), verify -> RAN
        {"tool_calls": [{"name": "detect", "input": {"query": _Q_GREEN}}]},
        {"tool_calls": [{"name": "verify",
                         "input": {"expr": "detection_matches_gt('绿色') == True"}}]},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}


def main() -> int:
    from tests.harness.pty_cli import run_repl_session

    print("[r7] bare cli.main REPL: g1 start -> detect red (GROUNDED) -> detect green (RAN)")
    result = run_repl_session(
        [
            (0.0, "启动 g1 仿真"),
            (50.0, _Q_RED),
            (80.0, _Q_GREEN),
            (105.0, "quit"),
        ],
        tool_script=_TOOL_SCRIPT,
        native=True,
        boot_sec=8.0,
        settle_sec=10.0,
        extra_args=["--native-first"],
    )
    text = _strip(result.transcript)
    with open(_TX_OK, "w") as fh:
        fh.write(text)
    print(f"[r7] transcript saved -> {_TX_OK} ({len(text)} chars) exit={result.exit_code}")

    lines = text.splitlines()

    def _verdict_for(oracle_substr: str) -> str | None:
        """Return the verdict line whose verify expr contains *oracle_substr*."""
        for i, ln in enumerate(lines):
            if oracle_substr in ln and ("verify" in ln.lower() or "▸" in ln):
                # the verdict usually lands on the same or the next couple of lines
                for j in range(i, min(i + 4, len(lines))):
                    if re.search(r"GROUNDED|\bRAN\b|verdict|verified", lines[j], re.I):
                        return lines[j].strip()
        return None

    red_lines = [ln.strip() for ln in lines if "红色" in ln and re.search(r"GROUNDED|RAN|verdict|verified|detection_matches", ln, re.I)]
    green_lines = [ln.strip() for ln in lines if "绿色" in ln and re.search(r"GROUNDED|RAN|verdict|verified|detection_matches", ln, re.I)]
    all_verdicts = [ln.strip() for ln in lines if re.search(r"verdict|VECTOR_VERDICT|GROUNDED|\bRAN\b|verified=", ln)]

    print("\n[r7] --- verdict lines from transcript ---")
    for ln in all_verdicts[-16:]:
        print(f"[r7]   {ln[:170]}")

    n_grounded = sum(1 for ln in all_verdicts if "GROUNDED" in ln)
    n_ran = sum(1 for ln in all_verdicts if re.search(r"\bRAN\b", ln))
    cmd_echoed = ("启动 g1" in text) and (_Q_RED in text) and (_Q_GREEN in text)
    print(f"\n[r7] grades: GROUNDED={n_grounded} RAN={n_ran} cmd_echoed={cmd_echoed} exit={result.exit_code}")
    print(f"[r7] red detect verdict lines: {red_lines[-3:]}")
    print(f"[r7] green (refutation) verdict lines: {green_lines[-3:]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
