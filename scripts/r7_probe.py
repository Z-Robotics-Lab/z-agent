#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""R7 geometry probe (foreground, serialized, torn down).

Drives the ACTUAL R7 oracle (``detection_matches_gt``, segmentation-GT backed)
against the real g1 sim + the real grounding-dino detector, and proves the honesty
contract BY CONSTRUCTION:

  CORRECT  (red stool framed at spawn)  -> detection_matches_gt('red') == True
  REFUTE   (g1 turned to face away)     -> detection_matches_gt('red') == False

Prints the segmentation GT centroid, the detector box center, the pixel distance,
and saves annotated frames with BOTH the box and the GT seg-centroid marked.
"""
from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HOME", "/home/yusen/.cache/huggingface")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PNG_OK = "/tmp/r7_g1_grounded.png"
_PNG_REF = "/tmp/r7_g1_refute.png"
_QUERY = "找前面的红色的东西"  # the bare-cli NL query


class _Agent:
    """The g1-shape agent surface the oracle reads: a base + a perception adapter."""

    def __init__(self, base, perc):
        self._base = base
        self._arm = None
        self._perception = perc


def _annotate(base, perc, token, png):
    import numpy as np
    from PIL import Image, ImageDraw
    from vector_os_nano.perception.grounding_dino import get_shared_detector
    import vector_os_nano.vcli.worlds.g1_perception_oracle as om

    rgb = perc.get_color_frame()
    img = Image.fromarray(rgb.astype("uint8"), "RGB")
    dr = ImageDraw.Draw(img)
    dets = get_shared_detector().detect(rgb, _QUERY)
    for d in dets:
        x1, y1, x2, y2 = (float(v) for v in d.bbox)
        dr.rectangle([x1, y1, x2, y2], outline=(255, 255, 0), width=3)
        dr.text((x1 + 3, max(0, y1 - 12)), f"{d.label} {d.confidence:.2f}", fill=(255, 255, 0))
    seg = om._red_geom_seg_centroid(base, token)
    if seg is not None:
        gu, gv, gpx = seg
        dr.line([gu - 14, gv, gu + 14, gv], fill=(0, 255, 255), width=3)
        dr.line([gu, gv - 14, gu, gv + 14], fill=(0, 255, 255), width=3)
        dr.text((gu + 6, gv + 6), f"GT seg ({gpx}px)", fill=(0, 255, 255))
    img.save(png)
    boxes = [[round(float(v), 1) for v in d.bbox] for d in dets]
    return seg, boxes


def main() -> int:
    from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1
    from vector_os_nano.perception.g1_head_perception import G1HeadPerception
    from vector_os_nano.vcli.worlds.g1_perception_oracle import make_detection_matches_gt

    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    try:
        g1.step(60)
        perc = G1HeadPerception(g1, width=640, height=480)
        agent = _Agent(g1, perc)
        oracle = make_detection_matches_gt(agent)

        sx, sy, sz = (float(v) for v in g1.get_position())
        print(f"g1 spawn pose: ({sx:.2f},{sy:.2f},{sz:.2f}) heading={g1.get_heading():.3f}")

        print("\n=== CORRECT: red stool framed at spawn ===")
        ok_seg, ok_boxes = _annotate(g1, perc, "red", _PNG_OK)
        ok = oracle("red", tol=60.0)
        print(f"seg_gt={ok_seg} boxes={ok_boxes}")
        print(f"detection_matches_gt('red') == {ok}")

        print("\n=== REFUTATION: turn g1 ~180deg so the red object leaves view ===")
        g1.set_velocity(0.0, 0.0, 1.0)
        for _ in range(900):
            g1.step(1)
        g1.set_velocity(0.0, 0.0, 0.0)
        for _ in range(60):
            g1.step(1)
        hx, hy, hz = (float(v) for v in g1.get_position())
        print(f"g1 pose after turn: ({hx:.2f},{hy:.2f},{hz:.2f}) heading={g1.get_heading():.3f}")
        ref_seg, ref_boxes = _annotate(g1, perc, "red", _PNG_REF)
        ref = oracle("red", tol=60.0)
        print(f"seg_gt={ref_seg} boxes={ref_boxes}")
        print(f"detection_matches_gt('red') == {ref}")

        honest = (ok is True) and (ref is False)
        print("\n=== SUMMARY ===")
        print(json.dumps({
            "correct_grounded": ok, "refute_grounded": ref,
            "honest_by_construction": honest,
            "png_ok": _PNG_OK, "png_refute": _PNG_REF,
        }, indent=2))
        return 0 if honest else 2
    finally:
        try:
            g1.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
