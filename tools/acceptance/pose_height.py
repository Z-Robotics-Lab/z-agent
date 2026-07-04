# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""pose_height — the DETERMINISTIC root-height pose oracle (R319/E110).

The companion to pose_upright (R318/E109). That oracle reads ORIENTATION from the sim root
quaternion and catches 3 of the 4 R316 fault topologies (upright, back-topple, side-topple). The
4th — a go2 sunk THROUGH the floor — keeps an upright orientation (upright_cosine ~ +1); only its
root-z betrays the fault. That exact `sunk_floor` frame is where minicpm-v SPLIT by framing
(STANDING under neutral framing, FALLEN under fault framing — E108): no robust VLM read exists.

But height, like orientation, is exactly the wrong job for a VLM. Invariant 1: verify grades on a
deterministic predicate reading GROUND TRUTH THE ACTOR CANNOT AUTHOR. The sim root-z IS that ground
truth — the actor issues NL/policy commands, it cannot forge the body's world height. So the correct
height verifier is this hard channel; a VLM is strictly weaker. VLM eyes earn their keep only where
NO deterministic channel exists (object identity / placement semantics — the CONFIRMED vlm-judge use).

`height_dev(root_z, stance_z)` = root_z - stance_z, the signed vertical deviation in meters (0 at
the nominal standing height, negative sunk, positive airborne). `classify` bands it: SUNK below
-tol, AIRBORNE above +tol, NOMINAL within. stance_z defaults to the go2 keyframe height 0.35 m
(mujoco_go2.py:397 qpos z / :1273). Sensor-floor: NaN/inf root_z and a non-positive stance fail loud.

Scope: HEIGHT only — deliberately orthogonal to pose_upright's ORIENTATION. Together they read all
4 R316 fault topologies deterministically; keeping them as two clean predicates is why each stays a
3-line channel. NOT a spine file: tools/, pure math, no sim, no network, no config/*rubric*.yaml.
LANDING either into the verify spine (acceptance/ + rubric) is honest-verify-spine semantics = a CEO
gate (G-318-1 covers the pair).
Usage:
    python tools/acceptance/pose_height.py <root_z> [--stance-z 0.35] [--tol 0.12]
"""
from __future__ import annotations

import argparse
import math

SUNK = "SUNK"
NOMINAL = "NOMINAL"
AIRBORNE = "AIRBORNE"
DEFAULT_STANCE_Z = 0.35
DEFAULT_TOL = 0.12


def height_dev(root_z, stance_z: float = DEFAULT_STANCE_Z) -> float:
    """Signed vertical deviation of the body root from nominal standing height, in meters.

    +ve = above stance (airborne), -ve = below (sunk), 0 = at stance. Rejects a non-finite root_z
    (NaN/inf) and a non-positive stance height — fail loud, never let a bad reading become a false
    verdict (sensor-validation floor).
    """
    z = float(root_z)
    s = float(stance_z)
    if not math.isfinite(z):
        raise ValueError(f"non-finite root_z: {root_z!r}")
    if not math.isfinite(s) or s <= 0.0:
        raise ValueError(f"stance_z must be a positive finite height: {stance_z!r}")
    return z - s


def classify(root_z, stance_z: float = DEFAULT_STANCE_Z, tol: float = DEFAULT_TOL) -> str:
    """SUNK if the root sits > tol below stance, AIRBORNE if > tol above, else NOMINAL.

    tol=0.12 m absorbs a standing go2's crouch/bob while flagging the R316 sunk_floor case
    (~0.28 m below stance). A negative tolerance is nonsense and fails loud.
    """
    if not math.isfinite(float(tol)) or float(tol) < 0.0:
        raise ValueError(f"tol must be a non-negative finite distance: {tol!r}")
    dev = height_dev(root_z, stance_z)
    if dev < -tol:
        return SUNK
    if dev > tol:
        return AIRBORNE
    return NOMINAL


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deterministic root-height pose oracle")
    ap.add_argument("root_z", type=float, metavar="ROOT_Z")
    ap.add_argument("--stance-z", type=float, default=DEFAULT_STANCE_Z)
    ap.add_argument("--tol", type=float, default=DEFAULT_TOL)
    args = ap.parse_args(argv)
    dev = height_dev(args.root_z, args.stance_z)
    verdict = classify(args.root_z, args.stance_z, args.tol)
    print(f"height_dev={dev:+.3f}m (stance={args.stance_z:.3f}) -> {verdict} (tol={args.tol})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
