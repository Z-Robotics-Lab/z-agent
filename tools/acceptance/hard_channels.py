# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""hard_channels — the AGENT-BOUND verify-namespace form of the deterministic hard-channel family (R323/E114).

R318-R322 proved four deterministic hard channels as pure-math cores (pose_upright E109,
pose_height E110, place_near E112, heading_facing E113): each grades a geometric fact off
GROUND TRUTH the actor cannot author (Invariant 1). A core takes raw numbers, but the moat
consumes bool predicates that READ that ground truth off the connected base themselves — the
``World.build_verify_namespace`` contract, whose reference implementation is
``vcli/worlds/go2_sim_oracle.make_*`` (``def pred(...) -> bool``, fail-safe to ``False``, reads
``_get_base(agent).get_position()/get_heading()``). This module packages all four cores into
exactly that shape, so landing them is ONE conformant merge into the robot world's verify
namespace — a single CEO gate, not four prose gates.

WHY AN AGENT-BOUND LAYER, NOT A FIFTH ORACLE: it adds no new geometry. It reuses the tested
cores verbatim (imported, never re-derived) and binds them to the real GT seam, turning four
scattered pure-math scripts + four separate spine gates into one reviewable ready-to-land unit.

LANDING (mined + red-teamed R323 — ALL FOUR land on the EXISTING base API, no interface change):
  hardware/base.py already exposes get_position() -> [x,y,z], get_heading() -> yaw, and
  get_odometry() -> Odometry(qw,qx,qy,qz) — a full root quaternion. (A first read missed the
  quaternion and wrongly deferred upright to an interface gate; the red-team on get_odometry
  corrected it.) So every channel binds with zero interface change:
    - upright(thresh)               reads quat   = get_odometry() (qw,qx,qy,qz) (pose_upright E109)
    - nominal_height(stance_z, tol) reads root z = get_position()[2]            (pose_height  E110)
    - near(x, y, z, radius, planar) reads own xyz= get_position(), vs a target  (place_near   E112)
    - facing_target(x, y, tol_deg)  reads xyz+yaw= get_position()+get_heading() (heading_facing E113)
  So the WHOLE quartet lands as ONE verify-namespace merge = a single CEO gate, no interface gate.
  IDENTITY ("which scene object is the target") stays the VLM/D182 grounder's job — the target
  point handed to near/facing_target is the RESOLVED grounding; these grade geometry only.

MOAT SEMANTICS: each predicate reads the base's REAL pose (the actor issues NL/policy, it cannot
forge where the base ends up) and fails safe to ``False`` on no base / disconnected / bad args /
unreadable GT — never a false PASS. Strictly stronger than the sim oracle's existing
``at_position``/``facing``, which take actor-supplied coords/heading: these read GT positions,
add height, and face a TARGET rather than an absolute compass heading.

NOT a spine file: tools/, pure wiring over tested cores, no sim / no network at import. LANDING
this (or its three predicates) into acceptance/ + the robot verify namespace + rubric is
honest-verify-spine semantics = a CEO gate.
Usage (unified dispatcher over the four landing channels):
    python tools/acceptance/hard_channels.py upright <w> <x> <y> <z> [--thresh 0.5]
    python tools/acceptance/hard_channels.py height <root_z> [--stance-z 0.35] [--tol 0.12]
    python tools/acceptance/hard_channels.py near <ax> <ay> [az] --to <bx> <by> [bz] [--radius 0.5] [--full]
    python tools/acceptance/hard_channels.py facing --at <rx> <ry> --to <tx> <ty> (--yaw <rad>|--quat w x y z) [--tol-deg 45]
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable

_DIR = Path(__file__).resolve().parent


def _load(name: str):
    """Load a sibling pure-math core by path (mirrors the unit-test loader — no package import)."""
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pose_upright = _load("pose_upright")
pose_height = _load("pose_height")
place_near = _load("place_near")
heading_facing = _load("heading_facing")


# --- ground-truth reads off the connected base (byte-for-byte the go2_sim_oracle pattern) ---
def _get_base(agent: Any) -> Any | None:
    """Return the connected base reachable from *agent*, or None (fail-safe)."""
    if agent is None:
        return None
    base = getattr(agent, "_base", None)
    if base is None:
        return None
    if getattr(base, "_connected", True) is False:
        return None
    return base


def _base_position(base: Any) -> list[float] | None:
    try:
        pos = base.get_position()
        return [float(pos[0]), float(pos[1]), float(pos[2])]
    except Exception:  # noqa: BLE001 — fail safe, never a false PASS
        return None


def _base_heading(base: Any) -> float | None:
    try:
        return float(base.get_heading())
    except Exception:  # noqa: BLE001
        return None


def _base_quat(base: Any) -> tuple[float, float, float, float] | None:
    """Return the base root quaternion (w, x, y, z) off get_odometry(), or None (fail-safe)."""
    try:
        odom = base.get_odometry()
        return (float(odom.qw), float(odom.qx), float(odom.qy), float(odom.qz))
    except Exception:  # noqa: BLE001
        return None


# --- the four landing predicates, each a GT-reading bool closure over *agent* ---
def make_upright(agent: Any) -> Callable[..., bool]:
    """``upright(thresh=0.5)`` — True iff the base is STANDING (not toppled).

    Reads the root quaternion off get_odometry() (qw,qx,qy,qz); delegates to pose_upright.classify
    (STANDING/FALLEN via the body-z upright cosine). A side/back topple reads False. Fails safe to
    False.
    """

    def upright(thresh: Any = pose_upright.DEFAULT_THRESH) -> bool:
        base = _get_base(agent)
        if base is None:
            return False
        quat = _base_quat(base)
        if quat is None:
            return False
        try:
            return pose_upright.classify(quat, float(thresh)) == pose_upright.STANDING
        except (TypeError, ValueError):
            return False

    return upright


def make_nominal_height(agent: Any) -> Callable[..., bool]:
    """``nominal_height(stance_z=0.35, tol=0.12)`` — True iff the base root z is NOMINAL.

    Reads root z off get_position(); delegates to pose_height.classify (SUNK/NOMINAL/AIRBORNE).
    A robot sunk through the floor or launched airborne reads False. Fails safe to False.
    """

    def nominal_height(stance_z: Any = pose_height.DEFAULT_STANCE_Z, tol: Any = pose_height.DEFAULT_TOL) -> bool:
        base = _get_base(agent)
        if base is None:
            return False
        pos = _base_position(base)
        if pos is None:
            return False
        try:
            return pose_height.classify(pos[2], float(stance_z), float(tol)) == pose_height.NOMINAL
        except (TypeError, ValueError):
            return False

    return nominal_height


def make_near(agent: Any) -> Callable[..., bool]:
    """``near(x, y, z=None, radius=0.5, planar=True)`` — True iff the base is NEAR a target point.

    Reads own xyz off get_position(); delegates to place_near.classify. Planar (xy) by default;
    pass z and planar=False for full-xyz proximity. The target point is the RESOLVED grounding
    (identity stays the grounder's job). Fails safe to False.
    """

    def near(x: Any, y: Any, z: Any = None, radius: Any = place_near.DEFAULT_RADIUS, planar: bool = True) -> bool:
        base = _get_base(agent)
        if base is None:
            return False
        pos = _base_position(base)
        if pos is None:
            return False
        try:
            target = [float(x), float(y)] if z is None else [float(x), float(y), float(z)]
            own = pos[:2] if (planar or z is None) else pos
            return place_near.classify(own, target, float(radius), planar=planar) == place_near.NEAR
        except (TypeError, ValueError):
            return False

    return near


def make_facing_target(agent: Any) -> Callable[..., bool]:
    """``facing_target(x, y, tol_deg=45)`` — True iff the base heading points at a target point.

    Reads own xy + yaw off get_position()/get_heading(); delegates to heading_facing.classify.
    Distance-orthogonal (orientation only) and reads a target BEHIND the robot as AWAY — the
    case a single-frame VLM cannot give. The target point is the RESOLVED grounding. Fails safe
    to False.
    """

    def facing_target(x: Any, y: Any, tol_deg: Any = heading_facing.DEFAULT_TOL_DEG) -> bool:
        base = _get_base(agent)
        if base is None:
            return False
        pos = _base_position(base)
        yaw = _base_heading(base)
        if pos is None or yaw is None:
            return False
        try:
            return (
                heading_facing.classify(yaw, pos[:2], [float(x), float(y)], float(tol_deg))
                == heading_facing.FACING
            )
        except (TypeError, ValueError):
            return False

    return facing_target


_FACTORIES: dict[str, Callable[[Any], Callable[..., bool]]] = {
    "upright": make_upright,
    "nominal_height": make_nominal_height,
    "near": make_near,
    "facing_target": make_facing_target,
}

_SIGNATURES: dict[str, str] = {
    "upright": "upright(thresh=0.5) -> bool  # base is STANDING (not toppled), from the root quaternion",
    "nominal_height": "nominal_height(stance_z=0.35, tol=0.12) -> bool  # base root z is NOMINAL (not sunk/airborne)",
    "near": "near(x, y, z=None, radius=0.5, planar=True) -> bool  # base is within radius of a target point",
    "facing_target": "facing_target(x, y, tol_deg=45) -> bool  # base heading points at a target point",
}


def verify_signatures() -> dict[str, str]:
    """The DecomposeVocab.verify_fn_signatures entries for the four landing predicates."""
    return dict(_SIGNATURES)


def make_verify_namespace(agent: Any) -> dict[str, Callable[..., bool]]:
    """The drop-in for ``World.build_verify_namespace`` — bind every landing predicate to *agent*."""
    return {name: factory(agent) for name, factory in _FACTORIES.items()}


# --- unified CLI dispatcher over the four landing channels (single entry, back-compat) ---
_CHANNEL_MAINS = {
    "upright": pose_upright._main,
    "height": pose_height._main,
    "near": place_near._main,
    "facing": heading_facing._main,
}


def _main(argv=None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in _CHANNEL_MAINS:
        sys.stderr.write(
            f"usage: hard_channels.py {{{'|'.join(_CHANNEL_MAINS)}}} ...  (got {args[:1] or '[]'})\n"
        )
        return 2
    return _CHANNEL_MAINS[args[0]](args[1:])


if __name__ == "__main__":
    raise SystemExit(_main())
