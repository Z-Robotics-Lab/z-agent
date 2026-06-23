# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Terminal dock — dead-reckon to a FIXED proven approach pose before a grasp.

THE R39 SEAM. FAR (``base.navigate_to``) is a COARSE long-range drive: it un-parks
the dog and brings it to within ~0.8 m of a goal, but at an ARBITRARY terminal
heading, often overshot/oblique (probe-confirmed: arrives ~169 deg off, framing the
floor/wall). From that pose the d435 cannot frame the cans and perception
mislocalizes the target (R38/D52: 0.4-0.87 m off → IK unreachable).

The fix is a deterministic TERMINAL DOCK that runs AFTER FAR's coarse arrival and
BEFORE perceiving: dead-reckon the dog (using ``get_position``/``get_heading`` +
the open-loop ``walk`` primitive — NOT FAR) to a FIXED, PROVEN table-approach pose
``(x, y, heading)`` from which the proven colour grasp (D47) GROUNDS. The dock target
is FIXED (the known scripted-from-spawn pose), NOT can-relative — so there is no
chicken-and-egg: the dog does not need to perceive the can to dock to it.

Geometry of a dock (open-loop, three phases, each a ``walk`` command):
    1. TURN to the bearing toward (dock_x, dock_y)   — point at the dock point
    2. WALK forward the planar distance to it        — translate onto it
    3. TURN-in-place to ``dock_heading``             — face the cans (+X)

Iterated a few times to close dead-reckoning error (the open-loop gait drifts).
Benign / near no-op when the dog is ALREADY at the dock pose (e.g. the
scripted-from-spawn path, where FAR is never run): all three phases fall below their
deadbands and issue no material motion — so the proven scripted grasp (D34-D51) does
NOT regress.

World-agnostic: uses only the base's duck-typed ``walk`` / ``get_position`` /
``get_heading`` surface. NON-cognitive — the verify spine (vcli/cognitive/) is never
touched.
"""
from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# --- Dock convergence tuning ------------------------------------------------
# Planar-position deadband: below this the dog is "at" the dock point and the
# turn+walk translate phases are skipped (benign no-op when already docked).
_DOCK_POS_DEADBAND_M = 0.12
# Heading deadband for the bearing-turn and the final facing-turn (~9 deg). A
# scripted-from-spawn dog already faces +X within this, so no real turn fires.
_DOCK_YAW_DEADBAND_RAD = 0.16
# Velocities for the three phases.
_DOCK_TURN_VYAW = 0.8     # rad/s turn-in-place
_DOCK_WALK_VX = 0.5       # m/s forward translate
# Duration caps per single walk command (keep each leg bounded).
_DOCK_TURN_MAX_S = 4.0
_DOCK_WALK_MAX_S = 4.0
# Dead-reckoning is open-loop and drifts; iterate the turn→walk→face cycle a few
# times to converge onto the dock point. Stops early once within the position
# deadband AND facing within the yaw deadband.
_DOCK_MAX_ITERS = 4


def _wrap(a: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def _has_surface(base: Any) -> bool:
    walk = getattr(base, "walk", None)
    get_pos = getattr(base, "get_position", None)
    get_hd = getattr(base, "get_heading", None)
    return callable(walk) and callable(get_pos) and callable(get_hd)


def terminal_dock(
    base: Any,
    dock_xy: tuple[float, float],
    dock_heading: float,
    *,
    pos_deadband: float = _DOCK_POS_DEADBAND_M,
    yaw_deadband: float = _DOCK_YAW_DEADBAND_RAD,
    max_iters: int = _DOCK_MAX_ITERS,
    on_progress: Any = None,
) -> bool:
    """Dead-reckon the base to a FIXED ``(dock_xy, dock_heading)`` pose.

    Args:
        base: a base exposing ``walk(vx, vy, vyaw, duration)`` /
            ``get_position()`` / ``get_heading()`` (duck-typed).
        dock_xy: the FIXED proven table-approach point ``(x, y)`` in world frame
            (NOT can-relative). For the go2+piper room this is the spawn standoff
            on the centerline, back from the cans, from which the proven grasp
            GROUNDS.
        dock_heading: the world yaw to face at the dock point (radians). Facing the
            cans is +X → ``0.0``.
        pos_deadband: stop translating once within this many metres of ``dock_xy``.
        yaw_deadband: treat a yaw error below this (radians) as "already facing".
        max_iters: how many turn→walk→face cycles to close open-loop drift.
        on_progress: optional ``callable(str)`` for human-readable progress.

    Returns:
        True if the dock ran (or was a benign no-op because the dog was already at
        the pose); False if the base lacks the required surface (caller then
        proceeds unchanged — no regression).
    """
    if not _has_surface(base):
        logger.debug("[DOCK] base lacks walk/get_position/get_heading — skip dock")
        return False

    dx_goal, dy_goal = float(dock_xy[0]), float(dock_xy[1])
    dock_hd = float(dock_heading)

    try:
        pos = base.get_position()
        hd = float(base.get_heading())
    except Exception as exc:  # noqa: BLE001 — no live pose → skip, never fabricate
        logger.debug("[DOCK] no live pose/heading (%s) — skip dock", exc)
        return False

    if on_progress:
        on_progress(
            f"dock: from ({pos[0]:.2f},{pos[1]:.2f}) hd={hd:.2f} "
            f"-> ({dx_goal:.2f},{dy_goal:.2f}) hd={dock_hd:.2f}")
    logger.info(
        "[DOCK] dead-reckon ( %.2f, %.2f ) hd=%.2f -> dock ( %.2f, %.2f ) hd=%.2f",
        pos[0], pos[1], hd, dx_goal, dy_goal, dock_hd)

    for it in range(max_iters):
        try:
            pos = base.get_position()
            hd = float(base.get_heading())
        except Exception as exc:  # noqa: BLE001
            logger.debug("[DOCK] pose read failed mid-dock (%s)", exc)
            return True

        gap = math.hypot(dx_goal - pos[0], dy_goal - pos[1])
        face_err = _wrap(dock_hd - hd)

        # Converged: at the dock point AND facing the dock heading.
        if gap <= pos_deadband and abs(face_err) <= yaw_deadband:
            logger.info("[DOCK] converged iter=%d gap=%.2fm face_err=%.2frad", it, gap, face_err)
            break

        # --- phase 1+2: translate onto the dock point (only if materially off) ---
        if gap > pos_deadband:
            bearing = math.atan2(dy_goal - pos[1], dx_goal - pos[0])
            turn = _wrap(bearing - hd)
            # phase 1: turn to the bearing toward the dock point
            if abs(turn) > yaw_deadband:
                dur = min(_DOCK_TURN_MAX_S, abs(turn) / _DOCK_TURN_VYAW)
                vyaw = _DOCK_TURN_VYAW if turn > 0 else -_DOCK_TURN_VYAW
                if on_progress:
                    on_progress(f"dock: turn {math.degrees(turn):.0f}deg to bearing")
                _safe_walk(base, vyaw=vyaw, duration=dur)
                try:
                    hd = float(base.get_heading())
                except Exception:  # noqa: BLE001
                    pass
            # phase 2: walk forward the planar gap (re-read pose after the turn)
            try:
                pos = base.get_position()
            except Exception:  # noqa: BLE001
                return True
            gap = math.hypot(dx_goal - pos[0], dy_goal - pos[1])
            if gap > pos_deadband:
                dur = min(_DOCK_WALK_MAX_S, gap / max(_DOCK_WALK_VX, 1e-3))
                if on_progress:
                    on_progress(f"dock: walk {gap:.2f}m to dock point")
                _safe_walk(base, vx=_DOCK_WALK_VX, duration=dur)

        # --- phase 3: turn-in-place to the dock heading (face the cans) ----------
        try:
            hd = float(base.get_heading())
        except Exception:  # noqa: BLE001
            return True
        face_err = _wrap(dock_hd - hd)
        if abs(face_err) > yaw_deadband:
            dur = min(_DOCK_TURN_MAX_S, abs(face_err) / _DOCK_TURN_VYAW)
            vyaw = _DOCK_TURN_VYAW if face_err > 0 else -_DOCK_TURN_VYAW
            if on_progress:
                on_progress(f"dock: face {math.degrees(face_err):.0f}deg to heading")
            _safe_walk(base, vyaw=vyaw, duration=dur)

    try:
        pos = base.get_position()
        hd = float(base.get_heading())
        logger.info("[DOCK] final pose ( %.2f, %.2f ) hd=%.2f (target %.2f,%.2f hd=%.2f)",
                    pos[0], pos[1], hd, dx_goal, dy_goal, dock_hd)
    except Exception:  # noqa: BLE001
        pass
    return True


def _safe_walk(base: Any, *, vx: float = 0.0, vy: float = 0.0,
               vyaw: float = 0.0, duration: float = 1.0) -> None:
    """Issue a single ``walk`` command, swallowing base-side errors."""
    try:
        base.walk(vx=vx, vy=vy, vyaw=vyaw, duration=duration)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DOCK] walk raised: %s", exc)
