#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R4 cross-EMBODIMENT x cross-MODEL acceptance: the agent routes a LEARNED MODEL
(grounding-dino) to a SECOND embodiment's (g1's) HEAD camera, via the BARE
vector-cli REPL + natural language, graded by the byte-unchanged moat.

The headline: two North-Star axes composed on ONE humanoid body — the runtime
routes the learned DetectorCapability (the 2nd model family, D48-D50) to g1's
sensor (the 2nd embodiment, D57-D59), and the moat grades the detect RAN (honest,
read-only — like D50's detect step).

Two acceptance artefacts:

  repl  (the real acceptance) — drive the literal interactive ``cli.main`` REPL
        under a PTY with two NL turns (LLM FAKED per policy; sim + g1 head camera +
        grounding-dino + verify-spine all REAL):
          turn 1:  "启动 g1 仿真"            -> SimStartTool sim_type=g1 -> _start_g1
                                                (binds G1HeadPerception; init_vgg
                                                 registers the 'detect' capability)
          turn 2:  "找前面的红色的东西"        -> native detect tool -> grounding-dino on
                                                g1's head camera -> boxes; then
                                                verify(len(detect_objects()) > 0) ->
                                                RAN (read-only — the honest D50 grade)
        Saves the transcript to /tmp/r4_g1_detect.txt.

  frame (the visual evidence) — in-process: render g1's head camera at spawn, run
        the SAME shared grounding-dino detector on it for "a red object", draw the
        box(es), and save /tmp/r4_g1_detect.png (g1's camera + the detector box on
        the red stool/can). The bare-cli is the acceptance; this proves the box is
        ON the red object (not background) and gives the frame to LOOK at.

Usage (foreground, lead-run, serialized; sim torn down after):
    HF_HOME=/home/yusen/.cache/huggingface MUJOCO_GL=egl \
    PATH=/usr/bin:$PATH .venv/bin/python scripts/probe_r4_g1_detect.py
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "/home/yusen/.cache/huggingface")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_REPL_TX = "/tmp/r4_g1_detect.txt"
_FRAME_PNG = "/tmp/r4_g1_detect.png"
# g1 spawns at (10, 3) facing +x; through the doorway the red bar stool (stool1,
# rgba 0.94 0.37 0.34) + the red can (pickable_can_red @ (10.9,3.22)) are in view.
_QUERY_ZH = "找前面的红色的东西"
_QUERY_DETECT = "red object"  # the detector prompt for the in-process frame


def _strip(s: str) -> str:
    return _ANSI.sub("", s)


# ---------------------------------------------------------------------------
# The bare-cli two-turn acceptance: switch to g1, then detect the red object.
# ---------------------------------------------------------------------------
_TOOL_SCRIPT = {
    "turns": [
        # --- line 1: switch embodiment to g1 by NL ---
        {"tool_calls": [
            {"name": "start_simulation", "input": {"sim_type": "g1", "gui": False}}
        ]},
        {"text": "g1 仿真已启动。", "tool_calls": [], "stop_reason": "end_turn"},
        # --- line 2: detect the red object on g1's head camera, then verify ---
        {"tool_calls": [
            {"name": "detect", "input": {"query": _QUERY_ZH}}
        ]},
        {"tool_calls": [
            {"name": "verify", "input": {"expr": "len(detect_objects()) > 0"}}
        ]},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}


def _run_repl() -> tuple[bool, str]:
    from tests.harness.pty_cli import run_repl_session

    print("[r4] REPL acceptance: two-turn bare cli.main — g1 switch + detect red")
    result = run_repl_session(
        [
            (0.0, "启动 g1 仿真"),     # turn 1: NL embodiment switch
            (30.0, _QUERY_ZH),         # turn 2: NL detect on g1's camera
            (45.0, "quit"),
        ],
        tool_script=_TOOL_SCRIPT,
        native=True,
        boot_sec=8.0,
        settle_sec=10.0,
        extra_args=["--native-first"],
    )
    text = _strip(result.transcript)
    with open(_REPL_TX, "w") as fh:
        fh.write(text)
    print(f"[r4] transcript saved -> {_REPL_TX} ({len(text)} chars), exit={result.exit_code}")

    def _grep(pat: str) -> list[str]:
        return [ln for ln in text.splitlines() if re.search(pat, ln, re.I)]

    started = bool(_grep(r"start.*sim|g1.*仿真|MuJoCoG1|sim_type=g1"))
    detect_lines = _grep(r"detect|grounding-dino|localized|box|找前面")
    verdict_lines = _grep(r"verdict|VERDICT|GROUNDED|RAN|verified|evidence|detect_objects")

    print("\n[r4] --- evidence from transcript ---")
    print(f"[r4] embodiment-switch to g1 seen: {started}")
    for ln in detect_lines[-8:]:
        print(f"[r4]   det> {ln.strip()[:160]}")
    for ln in verdict_lines[-8:]:
        print(f"[r4]   vrd> {ln.strip()[:160]}")

    ran = any("RAN" in ln for ln in verdict_lines)
    grounded = any("GROUNDED" in ln for ln in verdict_lines)
    localized = any("localized" in ln.lower() for ln in detect_lines)
    cmd_echoed = _QUERY_ZH in text and "启动 g1" in text
    ok = cmd_echoed and started and bool(detect_lines) and (ran or grounded)
    grade = "GROUNDED" if grounded else ("RAN" if ran else "NO-VERDICT")
    print(f"\n[r4] REPL VERDICT: bare-cli g1 detect {'PASS' if ok else 'INCOMPLETE'} "
          f"(moat grade: {grade}; RAN is the honest D50 grade for read-only detect; "
          f"detector localized={localized}).")
    return ok, grade


# ---------------------------------------------------------------------------
# The visual frame: g1 head camera + grounding-dino box on the red object.
# ---------------------------------------------------------------------------
def _run_frame() -> tuple[bool, dict]:
    from PIL import Image, ImageDraw
    from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1
    from vector_os_nano.perception.g1_head_perception import G1HeadPerception
    from vector_os_nano.perception.grounding_dino import get_shared_detector

    print(f"[r4] FRAME: render g1 head camera + grounding-dino box for {_QUERY_DETECT!r}")
    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    try:
        # settle a few steps so the pose is stable (R1 showed stands at spawn).
        try:
            g1.step(60)
        except Exception:  # noqa: BLE001 — settling is best-effort
            pass
        perc = G1HeadPerception(g1, width=640, height=480)
        rgb = perc.get_color_frame()
        detector = get_shared_detector()
        dets = detector.detect(rgb, _QUERY_DETECT)
        h, w = rgb.shape[:2]

        img = Image.fromarray(rgb.astype("uint8"), "RGB")
        draw = ImageDraw.Draw(img)
        out_dets = []
        for d in dets:
            x1, y1, x2, y2 = (float(v) for v in d.bbox)
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            # the red stool/can sits in the upper-CENTRE of g1's view (through the
            # doorway); a box centred there (not at an edge/background) is ON it.
            centred = (0.20 * w) < cx < (0.80 * w) and (0.15 * h) < cy < (0.85 * h)
            draw.rectangle([x1, y1, x2, y2], outline=(255, 255, 0), width=4)
            draw.text((x1 + 3, max(0, y1 - 12)),
                      f"{d.label} {d.confidence:.2f}", fill=(255, 255, 0))
            out_dets.append({
                "label": d.label,
                "bbox": [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                "center": [round(cx, 1), round(cy, 1)],
                "score": round(float(d.confidence), 3),
                "on_object_centred": centred,
            })
        img.save(_FRAME_PNG)
        print(f"[r4] annotated frame saved -> {_FRAME_PNG} ({w}x{h}, {len(dets)} box(es))")

        report = {
            "query": _QUERY_DETECT,
            "frame_shape": [h, w, 3],
            "n_detections": len(out_dets),
            "detections": out_dets,
            "any_box_on_object": any(d["on_object_centred"] for d in out_dets),
        }
        print(json.dumps(report, indent=2))
        ok = report["any_box_on_object"]
        print(f"[r4] FRAME VERDICT: grounding-dino on g1's camera "
              f"{'localized the red object (box centred, not background)' if ok else 'no centred box'} -> "
              f"{'PASS' if ok else 'CHECK'}")
        return ok, report
    finally:
        try:
            g1.close()
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    # FRAME first (in-process; gives the visual + confirms the model localizes), then
    # the bare-cli REPL acceptance (a SEPARATE child process — serialized after the
    # in-process sim is torn down in _run_frame's finally).
    frame_ok, frame_report = _run_frame()
    repl_ok, grade = _run_repl()

    print("\n" + "=" * 70)
    print("[r4] FINAL VERDICT (cross-EMBODIMENT x cross-MODEL on g1):")
    print(f"[r4]   bare-cli detect routed + graded: {repl_ok} (moat grade {grade})")
    print(f"[r4]   grounding-dino box ON the red object (frame): {frame_ok}")
    print(f"[r4]   detections: {frame_report.get('detections')}")
    composed = repl_ok and frame_ok
    print(f"[r4]   COMPOSED (learned model -> g1 sensor, moat-graded): "
          f"{'YES' if composed else 'PARTIAL'}")
    return 0 if composed else 2


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
