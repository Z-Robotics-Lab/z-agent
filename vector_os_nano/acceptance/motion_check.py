# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Motion cross-check (ADR-002 Stage 3): pair the DETERMINISTIC pose-delta with the temporal VLM.

The GT pose track over the per-step strip is the HARD channel — the authority on WHETHER the robot
translated. The temporal VLM is the SOFT narrator — it only adds plausibility (gait vs slide vs
teleport) and raises a DISAGREEMENT flag. Vision is NEVER the sole motion judge; it can flag, never
decide. (Complementary to the verdict's per-physics-step ``actor_causation`` gate, which is what
actually grades the StepRecords; this is a strip-level cross-check of the rendered motion.)

The "did it move" signal is MAX EXCURSION from the start pose — robust to odometry jitter (a
stationary robot stays ~0, unlike a cumulative path length) AND it still catches a there-and-back
walk (the farthest point counts). Non-finite poses (a blown-up sim) are filtered, never read as 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Strip-level planar displacement below which the robot is treated as NOT having translated. Coarser
# than vcli.cognitive.actor_causation.DISPLACEMENT_EPS (0.02, the per-physics-step verdict gate),
# because the strip is sampled once per VGG step and carries more odometry noise.
DISPLACEMENT_EPS: float = 0.05

_PASS = "PASS"


@dataclass(frozen=True)
class MotionVerdict:
    moved_m: float          # max excursion from the start pose (HARD channel — the authority)
    path_m: float           # cumulative path length (informational; jitter-sensitive)
    hard_moved: bool        # the pose track says the robot translated (the authority)
    vision_witness: str | None  # the SOFT temporal narrator: PASS|FAIL|ABSTAIN|None
    agree: bool
    disagreement: bool      # hard-vs-vision conflict -> red-flag (the product)
    note: str


def _finite_points(pose_track) -> list[tuple[float, float]]:
    """Extract finite (x, y) points (dicts with x/y, or (x,y[,…])s); drop NaN/inf (broken sim)."""
    pts: list[tuple[float, float]] = []
    for p in pose_track:
        try:
            if isinstance(p, dict):
                x, y = float(p.get("x", 0.0)), float(p.get("y", 0.0))
            else:
                x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            pts.append((x, y))
    return pts


def path_length(pose_track) -> float:
    """Total planar path length over the ordered pose track (cumulative; jitter-sensitive)."""
    pts = _finite_points(pose_track)
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def max_excursion(pose_track) -> float:
    """Farthest planar distance any frame reached from the START pose — the robust 'did it translate'
    signal (jitter stays ~0; a there-and-back walk still counts via its farthest point)."""
    pts = _finite_points(pose_track)
    if len(pts) < 2:
        return 0.0
    a = pts[0]
    return max(math.hypot(p[0] - a[0], p[1] - a[1]) for p in pts)


def cross_check(pose_track, vision_witness: str | None, *, eps: float = DISPLACEMENT_EPS) -> MotionVerdict:
    """Combine the hard pose-delta (max excursion) with the soft temporal witness.

    The hard channel decides ``hard_moved``. DISAGREEMENT (the product) is when the witness contradicts
    it: hard says TRANSLATED but vision did not confirm plausible locomotion (slid/teleport/static), OR
    hard says STATIC but vision claims locomotion (hallucination / render glitch). Vision unavailable ->
    no disagreement (the hard channel stands alone, logged as a coverage gap).
    """
    moved_m = max_excursion(pose_track)
    path_m = path_length(pose_track)
    hard_moved = moved_m > eps
    if vision_witness is None:
        return MotionVerdict(moved_m, path_m, hard_moved, None, agree=True, disagreement=False,
                             note="temporal vision unavailable; pose-delta authoritative")
    vis_locomoted = vision_witness == _PASS
    agree = hard_moved == vis_locomoted
    if agree:
        note = f"agree: pose-delta {'moved' if hard_moved else 'static'} ({moved_m:.2f}m excursion), vision {vision_witness}"
    else:
        note = (f"DISAGREEMENT: pose-delta {'MOVED' if hard_moved else 'STATIC'} ({moved_m:.2f}m excursion) but "
                f"vision {'PASS(locomoted)' if vis_locomoted else vision_witness}")
    return MotionVerdict(moved_m, path_m, hard_moved, vision_witness, agree, not agree, note)
