# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""place_near — the DETERMINISTIC relational proximity oracle (R321/E112).

The THIRD deterministic hard channel in the pose/place family, after pose_upright (orientation,
E109) and pose_height (height, E110). Those read a body's OWN pose; the placement geometry that is
already deterministic is ABSOLUTE-region containment — make_placed_count / make_resting_on_receptacle
(D106) grade "is the object inside THIS box". The one placement flavor with NO deterministic channel
is RELATIONAL: "put A NEAR B", "the bottle next to the box". Today only the VLM judge grades that.

But the GEOMETRY of "near" is exactly the wrong job for a VLM. Invariant 1: verify grades on a
deterministic predicate reading GROUND TRUTH THE ACTOR CANNOT AUTHOR. Two objects' sim world
positions ARE that ground truth — the actor issues NL/policy commands, it cannot forge where the
bodies end up. So the correct proximity verifier is this hard channel; a VLM is strictly weaker and
foreshortening/occlusion make its distance reads unreliable. The VLM earns its keep on the OTHER half
— IDENTITY (which scene object is "the box"): give this oracle two already-resolved positions and it
answers the geometric question the VLM cannot.

`separation(a, b, planar)` = Euclidean distance; planar=True uses xy only (ground-plane "next to",
the default — z stacking is usually irrelevant to "beside"), planar=False uses full xyz.
`proximity_margin` = radius - separation (signed meters: +ve inside the radius with slack, -ve FAR by
that much, 0 at the edge — the same signed-margin idiom as pose_height's height_dev, so a verdict
carries its margin and is never a knife-edge boolean). `classify` bands it NEAR / FAR.

Sensor floor: non-finite coordinates, malformed (<2-component, or planar=False without a z) positions,
and a non-positive/non-finite radius all fail LOUD — never let a bad reading become a false verdict.
"near" has no single physical constant (it is task-defined); DEFAULT_RADIUS is a CLI convenience only,
and the rubric/caller owns the real value.

Scope: RELATIONAL proximity only — deliberately orthogonal to pose (own-body) and to region
containment (absolute box). NOT a spine file: tools/, pure math, no sim, no network, no
config/*rubric*.yaml. LANDING this into the verify spine (acceptance/ + rubric) is honest-verify-spine
semantics = a CEO gate (relational near(a,b), frontier; sibling of the G-318-1 pose pair).
Usage:
    python tools/acceptance/place_near.py <ax> <ay> [az] --to <bx> <by> [bz] [--radius 0.5] [--full]
"""
from __future__ import annotations

import argparse
import math

NEAR = "NEAR"
FAR = "FAR"
DEFAULT_RADIUS = 0.5


def _checked_xy_z(pos, want_z: bool):
    """Return validated (x, y, z_or_None) from a position sequence, or fail loud.

    Requires at least 2 finite components (x, y). When *want_z* (full xyz distance), also requires a
    finite 3rd component. Rejects NaN/inf on every component used — a bad coordinate must never slip
    through into a false NEAR/FAR (sensor-validation floor).
    """
    try:
        comps = [float(c) for c in pos]
    except (TypeError, ValueError):
        raise ValueError(f"position must be a sequence of numbers: {pos!r}")
    if len(comps) < 2:
        raise ValueError(f"position needs at least (x, y): {pos!r}")
    if want_z and len(comps) < 3:
        raise ValueError(f"full (planar=False) distance needs a z component: {pos!r}")
    used = comps[:3] if want_z else comps[:2]
    for c in used:
        if not math.isfinite(c):
            raise ValueError(f"non-finite coordinate in position: {pos!r}")
    return comps[0], comps[1], (comps[2] if want_z else None)


def separation(pos_a, pos_b, planar: bool = True) -> float:
    """Euclidean distance between two positions, in meters.

    planar=True (default): ground-plane xy distance, ignoring z — the natural "next to" reading.
    planar=False: full xyz distance. Fails loud on non-finite or malformed positions.
    """
    ax, ay, az = _checked_xy_z(pos_a, want_z=not planar)
    bx, by, bz = _checked_xy_z(pos_b, want_z=not planar)
    dx, dy = ax - bx, ay - by
    if planar:
        return math.hypot(dx, dy)
    return math.sqrt(dx * dx + dy * dy + (az - bz) * (az - bz))


def proximity_margin(pos_a, pos_b, radius: float = DEFAULT_RADIUS, planar: bool = True) -> float:
    """Signed slack to the proximity radius: radius - separation, in meters.

    +ve = inside the radius (NEAR, with this much margin), -ve = FAR by that much, 0 = exactly at
    the edge. Same signed-margin idiom as pose_height.height_dev so a verdict is never knife-edge.
    """
    return _checked_radius(radius) - separation(pos_a, pos_b, planar)


def classify(pos_a, pos_b, radius: float = DEFAULT_RADIUS, planar: bool = True) -> str:
    """NEAR iff separation <= radius (edge inclusive), else FAR.

    radius is task-defined ("beside" on a table is centimeters; "near the pallet" is a meter) and
    must be a positive finite distance — a non-positive/non-finite radius fails loud, never a
    vacuous FAR.
    """
    return NEAR if separation(pos_a, pos_b, planar) <= _checked_radius(radius) else FAR


def _checked_radius(radius: float) -> float:
    r = float(radius)
    if not math.isfinite(r) or r <= 0.0:
        raise ValueError(f"radius must be a positive finite distance: {radius!r}")
    return r


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deterministic relational proximity oracle")
    ap.add_argument("a", nargs="+", type=float, metavar="AX AY [AZ]", help="position of object A")
    ap.add_argument("--to", nargs="+", type=float, required=True, metavar="BX BY [BZ]",
                    help="position of object B")
    ap.add_argument("--radius", type=float, default=DEFAULT_RADIUS)
    ap.add_argument("--full", action="store_true", help="use full xyz distance (default: planar xy)")
    args = ap.parse_args(argv)
    planar = not args.full
    sep = separation(args.a, args.to, planar)
    margin = proximity_margin(args.a, args.to, args.radius, planar)
    verdict = classify(args.a, args.to, args.radius, planar)
    plane = "xy" if planar else "xyz"
    print(f"separation={sep:.3f}m ({plane}) margin={margin:+.3f}m -> {verdict} (radius={args.radius})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
