# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Terminal dock — a CLOSED-LOOP controller to a FIXED proven grasp pose, with a
POSE-VERIFICATION GATE.

THE R39/R40 SEAM. FAR (``base.navigate_to``) is a COARSE long-range drive: it un-parks
the dog and brings it to within ~0.8 m of a goal, but with NO terminal-heading control —
it drops the dog at an ARBITRARY pose (probe-observed: heading ~169 deg off, overshot,
oblique). From that pose the d435 cannot frame the cans and perception mislocalizes the
target (R38/D52). The PROVEN colour grasp (D47) GROUNDS only when the dog starts HEAD-ON
from the room centerline facing the table.

R40 root cause (D54): the dock was NOT repeatable (~1/3). The previous dock ran a FIXED
SEQUENCE (drive-to-pre-dock -> drive-straight-in -> face -> recenter) and the quadruped
GAIT DRIFTS, so the sequence ended at an arbitrary residual pose ~2/3 of the time (R39
t3: heading 86 deg, x back from the table, camera off the cans). Six prior open-loop
attempts (turn/drive sandwiches) all failed for the same reason.

THE FIX — a true CLOSED-LOOP controller + a strict GATE:

  - ``terminal_dock`` now ITERATES an outer loop. Each iteration MEASURES the live pose
    (get_position/get_heading) and CORRECTS toward the FIXED proven grasp pose:
        1. correct heading to FACE the target xy (turn-in-place, closed-loop damped)
        2. drive to the target xy in closed-loop steered steps (re-measure each step)
        3. final heading -> +X (toward the table), closed-loop damped
        4. lateral re-center onto the dock_y centerline (closed-loop sidestep)
    After each iteration it re-measures and tests TOLERANCE; it repeats up to an
    iteration budget. Because every leg re-reads the live pose, accumulated gait drift
    is corrected rather than compounded — the whole point the open-loop sequence missed.

  - ``terminal_dock`` returns a structured :class:`DockResult` (converged bool + final
    pose + the per-axis errors). ``dock_converged(result, ...)`` is the GATE the caller
    uses: heading within ~±12 deg of +X (so the d435 frames the table), |y - centerline|
    < ~8 cm, AND x in the perceive band. If the dock does NOT converge within the budget
    the caller ABORTS the grasp cleanly ("dock_not_converged") — it NEVER perceives or
    grasps from a bad pose. A reliable dock + a strict gate = either a head-on perceive
    (-> likely GROUNDED) or an honest RAN, never a false/garbage grasp (the R39 t3
    spurious-grounded class is structurally impossible).

Benign / no-op when the dog is ALREADY at the dock pose (the scripted-from-spawn path,
where FAR is never run): the first measurement is already within tolerance, the loop
exits at iteration 0 issuing no motion — so the proven scripted grasp (D34-D51) does NOT
regress, and a ``converged=True`` gate lets the grasp proceed unchanged.

World-agnostic: uses only the base's duck-typed ``walk`` / ``get_position`` /
``get_heading`` surface. NON-cognitive — the verify spine (vcli/cognitive/) is never
touched.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# --- Dock convergence tolerances (the GATE) ---------------------------------
# After the dock the final pose must satisfy ALL of these for the grasp to proceed.
# Heading must be within ~±12 deg of the dock heading (+X), so the forward-mounted
# d435 frames the table (not the wall/floor). Wider than the in-loop facing deadband
# (the gate is the acceptance band; the loop drives TIGHTER than the gate so a
# converged dock clears it with margin).
_GATE_HEADING_TOL_RAD = math.radians(12.0)   # ±12 deg of +X
# Lateral: |y - dock_y centerline| must be within 8 cm (inter-can spacing is 22 cm, so
# 8 cm cannot frame a neighbour).
_GATE_LATERAL_TOL_M = 0.08
# Longitudinal (x) perceive band: the dog's x must sit in the proven afar-perceive
# sweet spot around the dock_x. Generous half-width — FAR's arrival + the dock leave
# the dog within this band; outside it (e.g. R39 t3 x=9.74, 0.26 m back) the camera
# framing degrades. Measured against dock_x.
_GATE_X_BAND_M = 0.30

# --- Closed-loop control tuning ---------------------------------------------
# Outer-loop iteration budget: how many MEASURE -> CORRECT passes before giving up and
# returning converged=False (the gate then aborts the grasp honestly). 4 is generous —
# a clean arrival converges in 1-2; a bad 86-deg/back-from-table arrival in 2-3.
_DOCK_MAX_ITERS = 4
# Planar-position deadband: below this the dog is "at" the dock point (drive leg done).
_DOCK_POS_DEADBAND_M = 0.10
# In-loop facing deadband (~6 deg) — TIGHTER than the gate's ±12 deg so a converged
# dock clears the gate with margin. The public no-op gate (already-docked check) uses
# the looser _DOCK_NOOP_YAW_RAD so a scripted-from-spawn dog triggers no motion.
_DOCK_FACE_DEADBAND_RAD = math.radians(6.0)
_DOCK_NOOP_YAW_RAD = 0.16        # ~9 deg — the benign already-docked yaw gate

# Closed-loop steered drive to the target xy (the proven _approach_object pattern). The
# gait curves and drifts under a big open-loop turn-then-walk, so we drive in SHORT
# steered steps: each step re-reads the live pose, steers vyaw proportional to the
# bearing error AND advances vx (zeroed while badly mis-headed), so heading + position
# errors close together instead of accumulating.
_DOCK_STEP_VX = 0.45           # m/s nominal forward speed per step
_DOCK_STEP_VYAW_GAIN = 1.5     # proportional yaw correction
_DOCK_STEP_VYAW_MAX = 0.6      # rad/s clamp on the per-step yaw correction
_DOCK_STEP_MIN_S = 0.6         # min per-step duration
_DOCK_STEP_MAX_S = 1.4         # max per-step duration
_DOCK_BIG_YAW_RAD = 0.7        # above this bearing error, TURN IN PLACE (vx=0) — do
                               # NOT creep, or the dog ORBITS a nearby mis-headed point
                               # instead of reaching it.
_DOCK_DRIVE_MAX_STEPS = 30     # max steered steps per drive leg
# R42 (D55): outer-loop DRIVE re-entry band. The face-xy + drive legs run only when the
# dog is at least this far from the dock point. Wider than _DOCK_POS_DEADBAND_M (0.10) so
# the small lateral drift the re-center leg leaves does NOT re-arm a drive whose target
# bearing is degenerate (≈±180° when sitting on the point) — that degeneracy was the
# orbit/oscillation that stopped the dock converging (R42 live: hd_err stuck at 90°).
# Inside this band, residual position error is closed by the lateral re-center, not a drive.
_DOCK_DRIVE_REENTRY_M = 0.30

# Closed-loop turn-in-place to a target heading: damped residual increments. A single
# open-loop turn overshoots (the gait keeps yawing past the command), so turn a damped
# fraction of the live residual each step until within the deadband.
#
# R42 (D55): the prior gain=0.6 over only 6 steps could NOT close a large heading
# residual (a near-180° re-face after the drive leg) — each step shed 60% of the
# residual but ran out of steps with ~tens of degrees left, and the outer loop then
# re-faced the target XY (degenerate ±180° bearing when the dog sits ON the point) and
# ORBITED, so the dock oscillated between hd≈1.8 and hd≈2.3 and never settled to +X
# (verified live: 4 iters, final hd_err=90°, converged=False → 0/4 grasp). Fix: a higher
# gain (0.85, still <1 so the gait's residual yaw doesn't overshoot) AND more steps
# (12) so even a 180° residual closes inside one facing call.
_DOCK_FACE_VYAW = 0.5          # rad/s turn-in-place
_DOCK_FACE_GAIN = 0.85         # damp the residual (raised from 0.6 so a big re-face closes)
_DOCK_FACE_MAX_S = 1.0
_DOCK_FACE_MAX_STEPS = 12      # raised from 6 — enough to close a ~180° residual

# Closed-loop lateral re-center onto the dock_y centerline (body-frame vy sidestep).
_DOCK_LATERAL_DEADBAND_M = 0.05  # m; within this the lateral step is a no-op
_DOCK_LATERAL_VY = 0.25          # m/s sidestep speed
_DOCK_LATERAL_MAX_STEPS = 4      # max sidestep commands

# R42 (D55): HOLONOMIC body-frame fine-positioning. FAR drops the dog PAST the dock point
# (observed: arrives at x≈10.6-10.7 for a dock_x=10.0), so the residual is a SMALL
# BACKWARD + sideways correction. The old path faced that ~172° bearing (a full turn in
# place), drove one step, then turned ~172° back to +X — and the gait drift across two
# big turns dominated, so x never closed (live: x_err stuck ~0.53 m, dog spun without
# net progress). The quadruped is holonomic (proxy walk takes vx, vy), so once it is
# already squared near +X we close the residual DIRECTLY with body-frame vx (reverse if
# behind) + vy (strafe) WITHOUT turning away from the table — no orbit, heading preserved.
_DOCK_BODY_DEADBAND_M = 0.06     # m; residual below this needs no body nudge
_DOCK_BODY_SPEED = 0.25          # m/s body-frame fine speed (gentle, avoids overshoot)
_DOCK_BODY_MAX_STEPS = 6         # max body-frame fine steps per iteration
_DOCK_BODY_FACE_GATE_RAD = math.radians(25.0)  # only nudge holonomically when within
                                  # this of dock_hd (else a normal face+drive is better)


@dataclass(frozen=True)
class DockResult:
    """Structured outcome of a terminal dock — the input to the pose gate.

    ``ran`` is False only when the base lacks the walk/pose surface (caller then
    proceeds unchanged, no regression). ``converged`` is the gate verdict: True iff
    the final pose is within ALL tolerances (heading within ±12 deg of +X, |y -
    centerline| < 8 cm, x in the perceive band). ``final_pose`` is the measured
    ``(x, y, heading)`` after the last correction; the ``*_err`` fields are the
    per-axis residuals (radians / metres) for diagnostics.
    """

    ran: bool
    converged: bool
    final_pose: tuple[float, float, float] | None = None
    heading_err: float = float("inf")   # |heading - dock_heading|, rad
    lateral_err: float = float("inf")    # |y - dock_y|, m
    x_err: float = float("inf")          # |x - dock_x|, m
    iterations: int = 0


def dock_converged(
    result: DockResult,
    *,
    heading_tol: float = _GATE_HEADING_TOL_RAD,
    lateral_tol: float = _GATE_LATERAL_TOL_M,
    x_band: float = _GATE_X_BAND_M,
) -> bool:
    """The POSE-VERIFICATION GATE. True iff the dock landed a perceivable head-on pose.

    A grasp may proceed ONLY when this returns True: heading within ``heading_tol`` of
    the dock heading (+X), |y - centerline| < ``lateral_tol``, AND x within ``x_band``
    of the dock x. If False the caller MUST abort the grasp cleanly ("dock_not_
    converged") rather than perceive from a bad pose. A dock that did not ``ran`` (no
    base surface) is treated as NOT a converged dock here, but the caller decides
    whether to proceed (scripted-from-spawn passes no dock_pose and never reaches the
    gate); when the dock ``ran`` and was a benign no-op, ``converged`` is already True.
    """
    if not result.ran:
        return False
    return (
        result.heading_err <= heading_tol
        and result.lateral_err <= lateral_tol
        and result.x_err <= x_band
    )


def _wrap(a: float) -> float:
    """Wrap an angle to [-pi, pi]."""
    return math.atan2(math.sin(a), math.cos(a))


def _has_surface(base: Any) -> bool:
    walk = getattr(base, "walk", None)
    get_pos = getattr(base, "get_position", None)
    get_hd = getattr(base, "get_heading", None)
    return callable(walk) and callable(get_pos) and callable(get_hd)


def _measure(base: Any) -> tuple[float, float, float] | None:
    """Read the live ``(x, y, heading)``; None if the base cannot report a pose."""
    try:
        pos = base.get_position()
        hd = float(base.get_heading())
        return (float(pos[0]), float(pos[1]), hd)
    except Exception as exc:  # noqa: BLE001 — no live pose -> caller skips, never fabricates
        logger.debug("[DOCK] pose read failed (%s)", exc)
        return None


def _errors(
    pose: tuple[float, float, float],
    dock_xy: tuple[float, float],
    dock_hd: float,
) -> tuple[float, float, float]:
    """Per-axis residuals ``(|heading-dock_hd|, |y-dock_y|, |x-dock_x|)``.

    Lateral is the world-y offset projected perpendicular to the dock heading, so it is
    correct at any dock heading; for a +X dock it collapses to ``|y - dock_y|``.
    """
    x, y, hd = pose
    dx = dock_xy[0] - x
    dy = dock_xy[1] - y
    heading_err = abs(_wrap(dock_hd - hd))
    lateral_err = abs(-dx * math.sin(dock_hd) + dy * math.cos(dock_hd))
    x_err = abs(x - dock_xy[0])
    return heading_err, lateral_err, x_err


def terminal_dock(
    base: Any,
    dock_xy: tuple[float, float],
    dock_heading: float,
    *,
    pos_deadband: float = _DOCK_POS_DEADBAND_M,
    yaw_deadband: float = _DOCK_NOOP_YAW_RAD,
    max_iters: int = _DOCK_MAX_ITERS,
    heading_tol: float = _GATE_HEADING_TOL_RAD,
    lateral_tol: float = _GATE_LATERAL_TOL_M,
    x_band: float = _GATE_X_BAND_M,
    on_progress: Any = None,
) -> DockResult:
    """CLOSED-LOOP drive the base to a FIXED ``(dock_xy, dock_heading)`` pose.

    Iterates an outer MEASURE -> CORRECT loop until the final pose is within ALL the
    gate tolerances or ``max_iters`` is exhausted. Each iteration: face the target xy
    -> closed-loop drive onto it -> face the dock heading (+X) -> lateral re-center.
    Every leg re-reads the live pose, so accumulated quadruped gait drift is corrected,
    not compounded (the open-loop sequence's failure mode).

    Args:
        base: a base exposing ``walk(vx, vy, vyaw, duration)`` / ``get_position()`` /
            ``get_heading()`` (duck-typed).
        dock_xy: the FIXED proven table-approach point ``(x, y)`` in world frame (NOT
            can-relative — the dog need not perceive the can to dock to it).
        dock_heading: the world yaw to face at the dock point (radians). Facing the
            cans is +X -> ``0.0``.
        pos_deadband: stop a drive leg once within this many metres of ``dock_xy``.
        yaw_deadband: the already-docked no-op gate (a scripted-from-spawn dog within
            this faces no turn).
        max_iters: outer MEASURE -> CORRECT iteration budget before giving up.
        heading_tol / lateral_tol / x_band: the gate tolerances (see ``dock_converged``).
        on_progress: optional ``callable(str)`` for human-readable progress.

    Returns:
        A :class:`DockResult`. ``ran=False`` iff the base lacks the surface (caller
        proceeds unchanged). Otherwise ``converged`` is the gate verdict and the caller
        MUST abort the grasp when it is False.
    """
    if not _has_surface(base):
        logger.debug("[DOCK] base lacks walk/get_position/get_heading — skip dock")
        return DockResult(ran=False, converged=False)

    dx_goal, dy_goal = float(dock_xy[0]), float(dock_xy[1])
    dock_hd = float(dock_heading)

    pose = _measure(base)
    if pose is None:
        return DockResult(ran=False, converged=False)

    # Already at the dock pose (scripted-from-spawn path)? Benign no-op: measure,
    # report converged, issue no motion. The proven grasp does not regress.
    heading_err, lateral_err, x_err = _errors(pose, dock_xy, dock_hd)
    gap0 = math.hypot(dx_goal - pose[0], dy_goal - pose[1])
    if gap0 <= pos_deadband and heading_err <= yaw_deadband:
        logger.info("[DOCK] already docked (gap=%.2fm face=%.0fdeg) — no-op",
                    gap0, math.degrees(heading_err))
        converged = (
            heading_err <= heading_tol and lateral_err <= lateral_tol and x_err <= x_band
        )
        return DockResult(
            ran=True, converged=converged, final_pose=pose,
            heading_err=heading_err, lateral_err=lateral_err, x_err=x_err, iterations=0,
        )

    if on_progress:
        on_progress(
            f"dock: closed-loop from ({pose[0]:.2f},{pose[1]:.2f}) hd={pose[2]:.2f} "
            f"-> ({dx_goal:.2f},{dy_goal:.2f}) hd={dock_hd:.2f} (budget {max_iters})")
    logger.info(
        "[DOCK] closed-loop ( %.2f, %.2f ) hd=%.2f -> dock ( %.2f, %.2f ) hd=%.2f budget=%d",
        pose[0], pose[1], pose[2], dx_goal, dy_goal, dock_hd, max_iters)

    iters = 0
    for it in range(max_iters):
        iters = it + 1
        # 1. face the target xy so the drive leg goes straight toward it (not orbit).
        pose = _measure(base)
        if pose is None:
            break
        bearing = math.atan2(dy_goal - pose[1], dx_goal - pose[0])
        gap = math.hypot(dx_goal - pose[0], dy_goal - pose[1])
        # R42 (D55): only DRIVE when the dog is meaningfully far from the point. Once it
        # is essentially ON the point (gap within _DOCK_DRIVE_REENTRY_M, a band wider
        # than the deadband), re-facing the target XY produces a DEGENERATE ±180°
        # bearing — the dog then orbits the point and FIGHTS the final-heading leg below
        # (the prior oscillation: hd stuck spinning, never settling to +X). At that range
        # the residual position error is closed by the LATERAL re-center (step 4), not by
        # a drive, so we skip straight to the final facing. The drive leg re-arms only if
        # a later iteration drifts the dog back outside the re-entry band.
        if gap > _DOCK_DRIVE_REENTRY_M:
            _face_heading(base, bearing, _DOCK_FACE_DEADBAND_RAD, on_progress)
            # 2. closed-loop steered drive onto the target xy.
            _drive_to_point(base, dx_goal, dy_goal, pos_deadband, on_progress)
        # 3. final facing -> dock heading (+X), closed-loop damped. ALWAYS run this — it
        # is the leg that lands the head-on +X pose the gate requires.
        _face_heading(base, dock_hd, _DOCK_FACE_DEADBAND_RAD, on_progress)
        # 4. R42 (D55): HOLONOMIC fine-positioning. Now squared near +X, close the
        # residual (dx, dy) — typically a small BACKWARD + sideways correction because
        # FAR overshoots the dock point — with body-frame vx/vy and NO turning away from
        # the table. This replaces the old "turn 172° to face the target, drive, turn
        # 172° back" that the gait drift defeated (the x_err-stuck oscillation). Subsumes
        # the lateral re-center (vy is one of its axes).
        _body_fine_position(base, dock_xy, dock_hd, on_progress)
        # 5. Re-square to +X after the body nudge (the strafe adds a little yaw); cheap
        # no-op when already squared. Ends the iteration head-on within the gate band.
        _face_heading(base, dock_hd, _DOCK_FACE_DEADBAND_RAD, on_progress)

        pose = _measure(base)
        if pose is None:
            break
        heading_err, lateral_err, x_err = _errors(pose, dock_xy, dock_hd)
        within = (
            heading_err <= heading_tol and lateral_err <= lateral_tol and x_err <= x_band
        )
        if on_progress:
            on_progress(
                f"dock: iter {iters} pose ({pose[0]:.2f},{pose[1]:.2f}) hd={pose[2]:.2f} "
                f"errs hd={math.degrees(heading_err):.0f}deg y={lateral_err:.3f}m "
                f"x={x_err:.3f}m within={within}")
        logger.info(
            "[DOCK] iter %d pose ( %.2f, %.2f ) hd=%.2f err hd=%.0fdeg y=%.3fm x=%.3fm within=%s",
            iters, pose[0], pose[1], pose[2], math.degrees(heading_err),
            lateral_err, x_err, within)
        if within:
            break

    converged = (
        pose is not None
        and heading_err <= heading_tol
        and lateral_err <= lateral_tol
        and x_err <= x_band
    )
    logger.info(
        "[DOCK] FINAL converged=%s after %d iter(s) err hd=%.0fdeg y=%.3fm x=%.3fm",
        converged, iters, math.degrees(heading_err), lateral_err, x_err)
    return DockResult(
        ran=True, converged=bool(converged), final_pose=pose,
        heading_err=heading_err, lateral_err=lateral_err, x_err=x_err, iterations=iters,
    )


def _drive_to_point(base: Any, dx_goal: float, dy_goal: float,
                    pos_deadband: float, on_progress: Any) -> None:
    """Closed-loop steered drive to (dx_goal, dy_goal): short combined vx+vyaw steps."""
    for step in range(_DOCK_DRIVE_MAX_STEPS):
        pose = _measure(base)
        if pose is None:
            return
        gap = math.hypot(dx_goal - pose[0], dy_goal - pose[1])
        if gap <= pos_deadband:
            logger.debug("[DOCK] reached dock point step=%d gap=%.2fm", step, gap)
            return
        bearing = math.atan2(dy_goal - pose[1], dx_goal - pose[0])
        yaw_err = _wrap(bearing - pose[2])
        vyaw = max(-_DOCK_STEP_VYAW_MAX,
                   min(_DOCK_STEP_VYAW_MAX, yaw_err * _DOCK_STEP_VYAW_GAIN))
        if abs(yaw_err) >= _DOCK_BIG_YAW_RAD:
            # Badly mis-headed: TURN IN PLACE (vx=0). Creeping here makes the dog orbit
            # a nearby point it isn't facing instead of reaching it.
            vx = 0.0
            dur = min(_DOCK_STEP_MAX_S,
                      max(_DOCK_STEP_MIN_S, abs(yaw_err) / _DOCK_STEP_VYAW_MAX))
        else:
            vx = _DOCK_STEP_VX
            dur = max(_DOCK_STEP_MIN_S, min(_DOCK_STEP_MAX_S, gap / max(vx, 1e-3)))
        if on_progress:
            on_progress(f"dock: drive {gap:.2f}m, yaw {math.degrees(yaw_err):.0f}deg "
                        f"({'turn' if vx == 0.0 else 'fwd'})")
        _safe_walk(base, vx=vx, vyaw=vyaw, duration=dur)


def _face_heading(base: Any, target_hd: float, yaw_deadband: float,
                  on_progress: Any) -> None:
    """Closed-loop turn-in-place to ``target_hd``: damped residual increments.

    A single open-loop turn overshoots (the gait keeps yawing past the command), so
    turn a damped fraction of the live residual each step until within the deadband.
    """
    for _ in range(_DOCK_FACE_MAX_STEPS):
        pose = _measure(base)
        if pose is None:
            return
        face_err = _wrap(target_hd - pose[2])
        if abs(face_err) <= yaw_deadband:
            return
        turn = face_err * _DOCK_FACE_GAIN
        dur = min(_DOCK_FACE_MAX_S, abs(turn) / _DOCK_FACE_VYAW)
        vyaw = _DOCK_FACE_VYAW if turn > 0 else -_DOCK_FACE_VYAW
        if on_progress:
            on_progress(f"dock: face residual {math.degrees(face_err):.0f}deg")
        _safe_walk(base, vyaw=vyaw, duration=dur)


def _recenter_lateral(
    base: Any,
    dock_xy: tuple[float, float],
    dock_hd: float,
    on_progress: Any,
) -> None:
    """Sidestep (body-frame vy) to re-center the dog's y on the dock_y centerline.

    Closes the perpendicular-to-heading offset from the dock centerline (R39 t2:
    y=3.18 vs target 3.0 framed the wrong object at 22 cm inter-can spacing). The
    world-y offset is projected perpendicular to the dock heading, so this is correct
    at any dock heading. Benign no-op when already within the deadband; errors are
    swallowed via _safe_walk so a base glitch cannot abort the dock.
    """
    dock_y = float(dock_xy[1])
    for _ in range(_DOCK_LATERAL_MAX_STEPS):
        pose = _measure(base)
        if pose is None:
            return
        dx = float(dock_xy[0]) - pose[0]
        dy = dock_y - pose[1]
        lateral = -dx * math.sin(pose[2]) + dy * math.cos(pose[2])
        if abs(lateral) <= _DOCK_LATERAL_DEADBAND_M:
            return  # already on centerline — benign no-op
        vy = _DOCK_LATERAL_VY if lateral > 0 else -_DOCK_LATERAL_VY
        dur = min(1.0, abs(lateral) / _DOCK_LATERAL_VY)
        if on_progress:
            on_progress(f"dock: lateral re-center {lateral:.3f}m (vy={vy:.2f})")
        logger.debug("[DOCK] lateral re-center lateral=%.3fm vy=%.2f dur=%.2fs",
                     lateral, vy, dur)
        _safe_walk(base, vx=0.0, vy=vy, vyaw=0.0, duration=dur)


def _body_fine_position(
    base: Any,
    dock_xy: tuple[float, float],
    dock_hd: float,
    on_progress: Any,
) -> None:
    """Close the residual (dx, dy) HOLONOMICALLY in the body frame, heading preserved.

    Run only when the dog is already squared near ``dock_hd`` (within
    ``_DOCK_BODY_FACE_GATE_RAD``). Projects the world residual onto the body axes and
    issues a single combined ``walk(vx, vy)`` per step — ``vx`` may be NEGATIVE (reverse)
    when the dog overshot the dock point, ``vy`` strafes onto the centerline. Re-measures
    each step (closed loop) and stops within ``_DOCK_BODY_DEADBAND_M``. Never turns, so it
    cannot orbit or drift the heading (the failure mode of the face+drive legs for a small
    backward correction). All errors swallowed via ``_safe_walk``.
    """
    dock_x, dock_y = float(dock_xy[0]), float(dock_xy[1])
    for _ in range(_DOCK_BODY_MAX_STEPS):
        pose = _measure(base)
        if pose is None:
            return
        hd = pose[2]
        # Only fine-position holonomically when already roughly facing the dock heading;
        # a badly mis-headed dog is corrected by the face+drive legs, not here.
        if abs(_wrap(dock_hd - hd)) > _DOCK_BODY_FACE_GATE_RAD:
            return
        dx_w = dock_x - pose[0]
        dy_w = dock_y - pose[1]
        resid = math.hypot(dx_w, dy_w)
        if resid <= _DOCK_BODY_DEADBAND_M:
            return  # at the dock point — done
        # World->body: body-x (forward) is +hd; body-y (left) is +hd+90°.
        cos_h, sin_h = math.cos(hd), math.sin(hd)
        body_fwd = dx_w * cos_h + dy_w * sin_h          # +ve ahead, -ve behind (reverse)
        body_left = -dx_w * sin_h + dy_w * cos_h         # +ve to the dog's left
        # Clamp each body axis to the gentle fine speed (direction preserved).
        vx = max(-_DOCK_BODY_SPEED, min(_DOCK_BODY_SPEED, body_fwd))
        vy = max(-_DOCK_BODY_SPEED, min(_DOCK_BODY_SPEED, body_left))
        dur = min(1.0, max(0.3, resid / _DOCK_BODY_SPEED))
        if on_progress:
            on_progress(f"dock: body-fine fwd={body_fwd:+.2f} left={body_left:+.2f} "
                        f"resid={resid:.3f}m (vx={vx:+.2f} vy={vy:+.2f})")
        logger.debug("[DOCK] body-fine fwd=%.3f left=%.3f resid=%.3fm vx=%.2f vy=%.2f",
                     body_fwd, body_left, resid, vx, vy)
        _safe_walk(base, vx=vx, vy=vy, vyaw=0.0, duration=dur)


def _safe_walk(base: Any, *, vx: float = 0.0, vy: float = 0.0,
               vyaw: float = 0.0, duration: float = 1.0) -> None:
    """Issue a single ``walk`` command, swallowing base-side errors."""
    try:
        base.walk(vx=vx, vy=vy, vyaw=vyaw, duration=duration)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[DOCK] walk raised: %s", exc)
