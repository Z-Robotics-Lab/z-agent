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
# translate phase is skipped (benign no-op when already docked).
_DOCK_POS_DEADBAND_M = 0.12
# Heading deadband for the final facing-turn (~9 deg). A scripted-from-spawn dog
# already faces +X within this, so no real facing turn fires.
_DOCK_YAW_DEADBAND_RAD = 0.16
# CLOSED-LOOP steered-step drive (the proven _approach_object pattern). The dog's
# real gait curves and drifts heavily under a big open-loop turn-then-walk, so we
# drive to the dock point in SHORT steered steps: each step re-reads the live pose,
# steers vyaw proportional to the bearing error AND advances vx (reduced while badly
# mis-headed), so heading + position errors close together instead of accumulating.
_DOCK_STEP_VX = 0.45           # m/s nominal forward speed per step
_DOCK_STEP_VYAW_GAIN = 1.5     # proportional yaw correction
_DOCK_STEP_VYAW_MAX = 0.6      # rad/s clamp on the per-step yaw correction
_DOCK_STEP_MIN_S = 0.6         # min per-step duration
_DOCK_STEP_MAX_S = 1.4         # max per-step duration
_DOCK_BIG_YAW_RAD = 0.5        # above this bearing error, creep slowly (turn first)
_DOCK_CREEP_FACTOR = 0.25      # vx multiplier while badly mis-headed
# Max steered steps to converge onto the dock point (each ~6-15 cm of progress).
_DOCK_MAX_STEPS = 30
# Final facing turn (face the cans): CLOSED-LOOP turn-in-place to the dock heading.
# A single open-loop turn overshoots badly — the gait curves and keeps yawing past
# the command (real-sim: a "face -144deg" command landed ~108 deg the wrong side).
# So turn in short, re-measured increments: each iteration re-reads the live heading
# and turns the RESIDUAL error (a fraction of it, capped) until within the deadband.
_DOCK_FACE_VYAW = 0.6          # rad/s turn-in-place (gentle — less overshoot)
_DOCK_FACE_GAIN = 0.6          # turn only this fraction of the residual per step
_DOCK_FACE_MAX_S = 1.2         # cap a single facing-turn increment
_DOCK_FACE_MAX_STEPS = 8       # iterations to converge the heading
# A pure-yaw turn-in-place still DRIFTS the dog forward (the gait curves), so the
# facing turn pushes the dog off the dock point (real-sim: facing drifted x 10.0→
# 10.55, too close to the table → the d435 looks OVER the cans). So alternate:
# drive to the point, then face, then RE-CHECK both and repeat until BOTH converge.
_DOCK_OUTER_ITERS = 4


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
    max_steps: int = _DOCK_MAX_STEPS,
    on_progress: Any = None,
) -> bool:
    """Drive the base to a FIXED ``(dock_xy, dock_heading)`` pose, then face it.

    CLOSED-LOOP steered-step drive (the proven _approach_object pattern): the dog's
    real gait curves and drifts heavily under a big open-loop turn-then-walk, so the
    dock drives to the dock point in SHORT steered steps — each step re-reads the
    live pose and issues ONE ``walk(vx, vyaw)`` whose yaw closes the bearing error
    and whose forward speed advances toward the point (reduced while badly mis-
    headed). Heading + position errors close together rather than accumulating. A
    final turn-in-place faces ``dock_heading`` (the cans, +X).

    Args:
        base: a base exposing ``walk(vx, vy, vyaw, duration)`` /
            ``get_position()`` / ``get_heading()`` (duck-typed).
        dock_xy: the FIXED proven table-approach point ``(x, y)`` in world frame
            (NOT can-relative). For the go2+piper room this is the spawn standoff
            on the centerline, back from the cans, from which the proven grasp
            GROUNDS.
        dock_heading: the world yaw to face at the dock point (radians). Facing the
            cans is +X → ``0.0``.
        pos_deadband: stop driving once within this many metres of ``dock_xy``.
        yaw_deadband: treat a final-facing yaw error below this (radians) as
            "already facing" (no facing turn).
        max_steps: max steered steps to converge onto the dock point.
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
        "[DOCK] steered drive ( %.2f, %.2f ) hd=%.2f -> dock ( %.2f, %.2f ) hd=%.2f",
        pos[0], pos[1], hd, dx_goal, dy_goal, dock_hd)

    # --- alternate drive-to-point + face-heading until BOTH converge ---------
    # A pure-yaw facing turn drifts the dog forward off the dock point, so a single
    # drive-then-face is not enough — face, then re-drive to undo the drift, repeat.
    converged = False
    for outer in range(_DOCK_OUTER_ITERS):
        _drive_to_point(base, dx_goal, dy_goal, pos_deadband, max_steps, on_progress)
        _face_heading(base, dock_hd, yaw_deadband, on_progress)
        try:
            pos = base.get_position()
            hd = float(base.get_heading())
        except Exception:  # noqa: BLE001
            return True
        gap = math.hypot(dx_goal - pos[0], dy_goal - pos[1])
        face_err = abs(_wrap(dock_hd - hd))
        logger.info("[DOCK] outer %d: gap=%.2fm face_err=%.0fdeg",
                    outer, gap, math.degrees(face_err))
        if gap <= pos_deadband and face_err <= yaw_deadband:
            converged = True
            break

    try:
        pos = base.get_position()
        hd = float(base.get_heading())
        logger.info("[DOCK] final pose ( %.2f, %.2f ) hd=%.2f (target %.2f,%.2f hd=%.2f) converged=%s",
                    pos[0], pos[1], hd, dx_goal, dy_goal, dock_hd, converged)
    except Exception:  # noqa: BLE001
        pass
    return True


def _drive_to_point(base: Any, dx_goal: float, dy_goal: float,
                    pos_deadband: float, max_steps: int, on_progress: Any) -> None:
    """Closed-loop steered drive to (dx_goal, dy_goal): short combined vx+vyaw steps."""
    for step in range(max_steps):
        try:
            pos = base.get_position()
            hd = float(base.get_heading())
        except Exception as exc:  # noqa: BLE001
            logger.debug("[DOCK] pose read failed mid-drive (%s)", exc)
            return
        gap = math.hypot(dx_goal - pos[0], dy_goal - pos[1])
        if gap <= pos_deadband:
            logger.info("[DOCK] reached dock point step=%d gap=%.2fm", step, gap)
            return
        bearing = math.atan2(dy_goal - pos[1], dx_goal - pos[0])
        yaw_err = _wrap(bearing - hd)
        vyaw = max(-_DOCK_STEP_VYAW_MAX,
                   min(_DOCK_STEP_VYAW_MAX, yaw_err * _DOCK_STEP_VYAW_GAIN))
        vx = (_DOCK_STEP_VX if abs(yaw_err) < _DOCK_BIG_YAW_RAD
              else _DOCK_STEP_VX * _DOCK_CREEP_FACTOR)
        dur = max(_DOCK_STEP_MIN_S, min(_DOCK_STEP_MAX_S, gap / max(vx, 1e-3)))
        if on_progress:
            on_progress(f"dock: drive {gap:.2f}m, yaw {math.degrees(yaw_err):.0f}deg")
        _safe_walk(base, vx=vx, vyaw=vyaw, duration=dur)


def _face_heading(base: Any, dock_hd: float, yaw_deadband: float,
                  on_progress: Any) -> None:
    """Closed-loop turn-in-place to ``dock_hd``: damped residual increments.

    A single open-loop turn overshoots (the gait keeps yawing past the command), so
    turn a damped fraction of the live residual each step until within the deadband.
    """
    for _ in range(_DOCK_FACE_MAX_STEPS):
        try:
            hd = float(base.get_heading())
        except Exception:  # noqa: BLE001
            return
        face_err = _wrap(dock_hd - hd)
        if abs(face_err) <= yaw_deadband:
            return
        turn = face_err * _DOCK_FACE_GAIN
        dur = min(_DOCK_FACE_MAX_S, abs(turn) / _DOCK_FACE_VYAW)
        vyaw = _DOCK_FACE_VYAW if turn > 0 else -_DOCK_FACE_VYAW
        if on_progress:
            on_progress(f"dock: face residual {math.degrees(face_err):.0f}deg")
        _safe_walk(base, vyaw=vyaw, duration=dur)


def _safe_walk(base: Any, *, vx: float = 0.0, vy: float = 0.0,
               vyaw: float = 0.0, duration: float = 1.0) -> None:
    """Issue a single ``walk`` command, swallowing base-side errors."""
    try:
        base.walk(vx=vx, vy=vy, vyaw=vyaw, duration=duration)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DOCK] walk raised: %s", exc)
