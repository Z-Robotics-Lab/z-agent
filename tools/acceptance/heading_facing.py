# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""heading_facing — the DETERMINISTIC heading/facing oracle (R322/E113).

The FOURTH deterministic hard channel in the pose/place family, after pose_upright (own
orientation, E109), pose_height (own height, E110) and place_near (object-to-object proximity,
E112). Each of those reads a static fact — how a body is tilted, how high it sits, how far two
bodies are apart. NONE reads whether a robot is TURNED TOWARD a target: the "go to / face the
red thing" question at the heart of VLN (E14 g1 VLN '走到红色的东西那里', D178 near_object).

That question is exactly the wrong job for a VLM. Invariant 1: verify grades on a deterministic
predicate reading GROUND TRUTH THE ACTOR CANNOT AUTHOR. The robot's sim root yaw and the target's
world position ARE that ground truth — the actor issues NL/policy commands, it cannot forge which
way the base ends up pointing. A single-frame VLM reads heading unreliably (foreshortening,
occlusion, and it cannot see behind the robot), so it is the strictly weaker witness; VLM eyes
earn their keep only on IDENTITY ("which scene object is the red thing") — the same division of
labor place_near draws. Hand this oracle a resolved target position and the robot pose and it
answers the geometric question deterministically.

`yaw_from_quat(quat)` = world-z yaw of a MuJoCo (w,x,y,z) root quaternion (roll/pitch do not
leak in). `bearing_to(robot, target)` = atan2(dy, dx), the world angle from robot to target.
`heading_error(yaw, robot, target)` = the SIGNED smallest angle between heading and bearing,
wrapped to [-pi, pi] (so a near-antipodal pair reads its true small error, never ~2pi).
`facing_margin` = tol - |error| in degrees (signed: +ve inside the cone with slack, -ve off by
that much, 0 at the edge — the pose_height/place_near signed-margin idiom, so a verdict is never
a knife-edge boolean). `classify` bands it FACING / AWAY.

Orthogonality (why this is NOT a place_near duplicate): facing depends ONLY on orientation, not
distance — a robot is FACING a target 100 m away and AWAY from one 0.1 m behind it. place_near is
translation-only and orientation-blind; this is orientation-relative and distance-blind. They
COMPOSE to grade "approached AND oriented toward the target" and neither subsumes the other.

Sensor floor: a zero quaternion, non-finite coordinates, a robot coincident with the target
(bearing undefined), and a tol outside (0, 180] all fail LOUD — never let a bad reading become a
false FACING/AWAY.

Scope: heading-relative-to-a-target only — deliberately orthogonal to own-pose (pose_upright/
pose_height) and to proximity (place_near). NOT a spine file: tools/, pure math, no sim, no
network, no config/*rubric*.yaml. LANDING this into the verify spine (acceptance/ + rubric) is
honest-verify-spine semantics = a CEO gate (facing verify-channel; sibling of G-318-1 pose pair
and the relational near(a,b) gate).
Usage:
    python tools/acceptance/heading_facing.py --at <rx> <ry> --to <tx> <ty> \\
        (--yaw <rad> | --quat <w> <x> <y> <z>) [--tol-deg 45]
"""
from __future__ import annotations

import argparse
import math

FACING = "FACING"
AWAY = "AWAY"
DEFAULT_TOL_DEG = 45.0


def yaw_from_quat(quat) -> float:
    """World-z yaw (radians) of a MuJoCo (w, x, y, z) quaternion.

    yaw = atan2(2(wz + xy), w^2 + x^2 - y^2 - z^2) — the ZYX yaw in HOMOGENEOUS form (both
    arguments are degree-2 in the components, so the ratio is scale-invariant: an unnormalized
    quaternion yields the same angle). Roll/pitch do not leak in. Raises on a zero quaternion
    (fail loud, never a bogus 0-yaw from a degenerate reading).
    """
    w, x, y, z = (float(c) for c in quat)
    for c in (w, x, y, z):
        if not math.isfinite(c):
            raise ValueError(f"non-finite quaternion component: {quat!r}")
    if w * w + x * x + y * y + z * z <= 1e-12:
        raise ValueError(f"degenerate (zero) quaternion: {quat!r}")
    return math.atan2(2.0 * (w * z + x * y), w * w + x * x - y * y - z * z)


def _checked_xy(pos):
    """Return validated (x, y) from a position sequence (ignoring any z), or fail loud."""
    try:
        comps = [float(c) for c in pos]
    except (TypeError, ValueError):
        raise ValueError(f"position must be a sequence of numbers: {pos!r}")
    if len(comps) < 2:
        raise ValueError(f"position needs at least (x, y): {pos!r}")
    for c in comps[:2]:
        if not math.isfinite(c):
            raise ValueError(f"non-finite coordinate in position: {pos!r}")
    return comps[0], comps[1]


def bearing_to(robot_pos, target_pos) -> float:
    """World-frame ground-plane angle (radians) from robot to target: atan2(ty-ry, tx-rx).

    Ignores z (a heading is a ground-plane fact). Fails loud when the robot and target share the
    same xy — the bearing is undefined there and must never resolve to a false verdict.
    """
    rx, ry = _checked_xy(robot_pos)
    tx, ty = _checked_xy(target_pos)
    dx, dy = tx - rx, ty - ry
    if math.hypot(dx, dy) <= 1e-12:
        raise ValueError("robot is coincident with the target in xy: bearing undefined")
    return math.atan2(dy, dx)


def _wrap_pi(angle: float) -> float:
    """Wrap an angle to [-pi, pi] via atan2 (numerically robust; never returns ~2pi)."""
    return math.atan2(math.sin(angle), math.cos(angle))


def heading_error(robot_yaw: float, robot_pos, target_pos) -> float:
    """Signed smallest angle (radians, in [-pi, pi]) from the robot heading to the target bearing.

    +ve = the target is to the robot's left (turn CCW to face it), -ve = to the right. Wrapped to
    the shortest arc, so a near-antipodal heading reads its true small error rather than ~2pi.
    """
    y = float(robot_yaw)
    if not math.isfinite(y):
        raise ValueError(f"non-finite robot_yaw: {robot_yaw!r}")
    return _wrap_pi(bearing_to(robot_pos, target_pos) - y)


def _checked_tol_deg(tol_deg: float) -> float:
    t = float(tol_deg)
    if not math.isfinite(t) or t <= 0.0 or t > 180.0:
        raise ValueError(f"tol_deg must be in (0, 180]: {tol_deg!r}")
    return t


def facing_margin(robot_yaw: float, robot_pos, target_pos, tol_deg: float = DEFAULT_TOL_DEG) -> float:
    """Signed slack to the facing cone, in DEGREES: tol - |heading_error|.

    +ve = inside the cone (FACING, with this much margin), -ve = AWAY by that much, 0 = exactly at
    the cone edge. Same signed-margin idiom as pose_height/place_near so a verdict carries its
    margin and is never knife-edge.
    """
    err_deg = abs(math.degrees(heading_error(robot_yaw, robot_pos, target_pos)))
    return _checked_tol_deg(tol_deg) - err_deg


def classify(robot_yaw: float, robot_pos, target_pos, tol_deg: float = DEFAULT_TOL_DEG) -> str:
    """FACING iff |heading_error| <= tol (edge inclusive), else AWAY.

    tol_deg is the half-angle of the facing cone (task-defined: a tight grasp-approach wants a few
    degrees; 'roughly toward' wants tens) and must lie in (0, 180] — a non-positive/non-finite or
    >180 tol fails loud, never a vacuous verdict.
    """
    err_deg = abs(math.degrees(heading_error(robot_yaw, robot_pos, target_pos)))
    return FACING if err_deg <= _checked_tol_deg(tol_deg) else AWAY


def classify_quat(quat, robot_pos, target_pos, tol_deg: float = DEFAULT_TOL_DEG) -> str:
    """classify() taking a MuJoCo (w,x,y,z) root quaternion instead of a raw yaw.

    The convenience seam for real sim ground truth, where the root pose arrives as a quaternion
    (the same source pose_upright/pose_height read).
    """
    return classify(yaw_from_quat(quat), robot_pos, target_pos, tol_deg)


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="deterministic heading/facing oracle")
    ap.add_argument("--at", nargs="+", type=float, required=True, metavar="RX RY [RZ]",
                    help="robot world position")
    ap.add_argument("--to", nargs="+", type=float, required=True, metavar="TX TY [TZ]",
                    help="target world position")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--yaw", type=float, help="robot world yaw in radians")
    src.add_argument("--quat", nargs=4, type=float, metavar=("W", "X", "Y", "Z"),
                     help="robot root quaternion (MuJoCo w,x,y,z)")
    ap.add_argument("--tol-deg", type=float, default=DEFAULT_TOL_DEG)
    args = ap.parse_args(argv)
    yaw = args.yaw if args.yaw is not None else yaw_from_quat(args.quat)
    err = heading_error(yaw, args.at, args.to)
    margin = facing_margin(yaw, args.at, args.to, args.tol_deg)
    verdict = classify(yaw, args.at, args.to, args.tol_deg)
    print(f"heading_error={math.degrees(err):+6.1f}deg margin={margin:+6.1f}deg "
          f"-> {verdict} (tol={args.tol_deg}deg)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
