# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Motion cross-check (ADR-002 Stage 3): pair the DETERMINISTIC pose-delta with the temporal VLM.

The pose-delta over the per-step strip manifest is the HARD channel — the authority on WHETHER the
robot moved (the same ground-truth displacement ``actor_causation`` grades, ``DISPLACEMENT_EPS``).
The temporal VLM is the SOFT narrator — it only adds plausibility (gait vs slide vs teleport) and
raises a DISAGREEMENT flag. Vision is NEVER the sole motion judge; it can flag, never decide.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Planar displacement below which the pose is treated as UNCHANGED — mirrors
# vcli.cognitive.actor_causation.DISPLACEMENT_EPS (the hard motion gate the verdict already uses).
DISPLACEMENT_EPS: float = 0.02

_PASS = "PASS"


@dataclass(frozen=True)
class MotionVerdict:
    moved_m: float          # total planar path length over the pose track (HARD channel)
    hard_moved: bool        # pose-delta says the robot moved (the authority)
    vision_witness: str | None  # the SOFT temporal narrator: PASS|FAIL|ABSTAIN|None
    agree: bool
    disagreement: bool      # hard-vs-vision conflict -> red-flag (the product)
    note: str


def path_length(pose_track) -> float:
    """Total planar (xy) path length over the ordered pose track (dicts with x/y, or (x,y[,…])s)."""
    pts = []
    for p in pose_track:
        if isinstance(p, dict):
            pts.append((float(p.get("x", 0.0)), float(p.get("y", 0.0))))
        else:
            pts.append((float(p[0]), float(p[1])))
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def cross_check(pose_track, vision_witness: str | None, *, eps: float = DISPLACEMENT_EPS) -> MotionVerdict:
    """Combine the hard pose-delta with the soft temporal witness.

    The hard channel decides ``hard_moved``. DISAGREEMENT (the product) is when the witness contradicts
    it: hard says MOVED but vision did not confirm plausible locomotion (slid/teleport/static), OR hard
    says STATIC but vision claims locomotion (hallucination / render glitch). Vision unavailable ->
    no disagreement (the hard channel stands alone, logged as a coverage gap).
    """
    moved_m = path_length(pose_track)
    hard_moved = moved_m > eps
    if vision_witness is None:
        return MotionVerdict(moved_m, hard_moved, None, agree=True, disagreement=False,
                             note="temporal vision unavailable; pose-delta authoritative")
    vis_locomoted = vision_witness == _PASS
    agree = hard_moved == vis_locomoted
    if agree:
        note = f"agree: pose-delta {'moved' if hard_moved else 'static'} ({moved_m:.2f}m), vision {vision_witness}"
    else:
        note = (f"DISAGREEMENT: pose-delta {'MOVED' if hard_moved else 'STATIC'} ({moved_m:.2f}m) but "
                f"vision {'PASS(locomoted)' if vis_locomoted else vision_witness}")
    return MotionVerdict(moved_m, hard_moved, vision_witness, agree, not agree, note)
