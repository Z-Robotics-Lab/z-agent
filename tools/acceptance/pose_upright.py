# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""pose_upright — the DETERMINISTIC quat-upright pose oracle (R318/E109).

Why this exists: R315-R317 (E105/E107/E108) exhausted the LOCAL-VLM lever for pose. qwen2.5vl is
pose-blind (E105); minicpm-v reads upright + a back-topple but MISSES a left-side topple both
single-frame (E107) and across 4 azimuths (E108) — side-lying is a TOPOLOGY blind spot in the
model, not a camera-angle artifact. So no local VLM is a robust pose 2nd-witness.

But pose is exactly the wrong job for a VLM. Invariant 1: verify grades on a deterministic
predicate reading GROUND TRUTH THE ACTOR CANNOT AUTHOR. The sim root quaternion IS that ground
truth — the actor issues NL/policy commands, it cannot forge the body's world orientation. So the
CORRECT pose verifier is this hard channel, and a VLM is the strictly weaker choice; VLM eyes earn
their keep only where NO deterministic channel exists (object identity / placement semantics —
already the CONFIRMED vlm-judge use). This tool is the hard channel, standalone.

`upright_cosine(quat)` = world-up . (R(quat) . body-up) = the m22 entry of the rotation matrix for
a MuJoCo (w,x,y,z) quaternion: +1 standing, 0 on its side, -1 on its back. `classify` thresholds it.

Scope: ORIENTATION only. A go2 sunk THROUGH the floor keeps an upright orientation (cosine ~ +1)
but a bad root-z — that is a separate deterministic HEIGHT channel (root_z vs stance_z), not this
oracle's job; keeping them separate is why this stays a clean 3-line predicate.

NOT a spine file: tools/, pure math, no sim, no network, no config/*rubric*.yaml. LANDING this into
the verify spine (acceptance/ + rubric) is honest-verify-spine semantics = a CEO gate (G-318-1).
Usage:
    python tools/acceptance/pose_upright.py <w> <x> <y> <z> [--thresh 0.5]
"""
from __future__ import annotations

import argparse
import math

STANDING = "STANDING"
FALLEN = "FALLEN"
DEFAULT_THRESH = 0.5


def upright_cosine(quat) -> float:
    """cos(angle between world-up and the body's up axis) for a MuJoCo (w,x,y,z) quaternion.

    Equals the rotation matrix's m22 = 1 - 2*(x^2 + y^2) after normalization. +1 = perfectly
    upright, 0 = on its side, -1 = upside-down/on its back. Raises on a zero quaternion (fail loud,
    never divide-by-zero into a false verdict).
    """
    w, x, y, z = (float(c) for c in quat)
    n2 = w * w + x * x + y * y + z * z
    if n2 <= 1e-12:
        raise ValueError(f"degenerate (zero) quaternion: {quat!r}")
    # normalize, then m22 of the rotation matrix
    return 1.0 - 2.0 * (x * x + y * y) / n2


def classify(quat, thresh: float = DEFAULT_THRESH) -> str:
    """STANDING iff the upright cosine >= thresh, else FALLEN. thresh=0.5 -> tips past 60deg fall."""
    return STANDING if upright_cosine(quat) >= thresh else FALLEN


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deterministic quat-upright pose oracle")
    ap.add_argument("quat", nargs=4, type=float, metavar=("W", "X", "Y", "Z"))
    ap.add_argument("--thresh", type=float, default=DEFAULT_THRESH)
    args = ap.parse_args(argv)
    cos = upright_cosine(args.quat)
    verdict = classify(args.quat, args.thresh)
    tilt = math.degrees(math.acos(max(-1.0, min(1.0, cos))))
    print(f"upright_cosine={cos:+.4f} tilt={tilt:5.1f}deg -> {verdict} (thresh={args.thresh})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
