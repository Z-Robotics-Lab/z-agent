# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real verify predicates — the odometry oracle (Inv-1).

On hardware there is NO ``/gt``: the only ground truth is ``/state_estimation``
odometry, which ``Go2WHardware`` caches and exposes via ``get_position()``. These
predicates read that pose and NOTHING the actor authored. Both are fail-safe: a
missing base returns False (a missing oracle must never fake-pass — this is the
verifier-sandbox boundary, so it may never raise into the verifier either).
"""

from __future__ import annotations

import math
from typing import Any, Callable

from zeno.vcli.worlds.go2w_real_skills import CFG


def make_at(agent: Any) -> Callable[..., bool]:
    """Bind an ``at(x, y, tol=0.8)`` predicate to the agent's hardware base.

    True iff the robot's odometry position is within ``tol`` metres of the
    map-frame (x, y). Fail-safe False when no base is wired.
    """

    def at(x: float, y: float, tol: float = CFG.arrival_tol_m) -> bool:
        base = getattr(agent, "_base", None) if agent is not None else None
        if base is None:
            return False
        try:
            pos = base.get_position()
            return math.hypot(float(pos[0]) - x, float(pos[1]) - y) < tol
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return at


def make_explore_finished(agent: Any) -> Callable[..., bool]:
    """Bind ``explore_finished()`` to the agent's explore manager.

    True iff TARE ITSELF published exploration_finish=True on
    ``/exploration_finish`` during the current explore session — the planner's
    own completion signal, not anything the actor authored. Combine with
    ``explored_progress()`` to reject a 'finished' run that never left the
    spawn. Fail-safe False when no manager is wired or it errors.
    """

    def explore_finished() -> bool:
        mgr = getattr(agent, "_explore", None) if agent is not None else None
        if mgr is None:
            return False
        try:
            return bool(mgr.explore_finished())
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return explore_finished


def make_explored_progress(agent: Any) -> Callable[..., float]:
    """Bind ``explored_progress()`` — meters travelled during the explore run.

    The INDEPENDENT progress oracle: odometry travel distance integrated by
    the explore manager (monotone within a session; frozen after stop). Lets
    verify distinguish 'finished because done' from 'finished while parked'.
    Fail-safe 0.0 when no manager is wired or it errors (a missing oracle
    must never fake progress).
    """

    def explored_progress() -> float:
        mgr = getattr(agent, "_explore", None) if agent is not None else None
        if mgr is None:
            return 0.0
        try:
            return float(mgr.explored_progress())
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return 0.0

    return explored_progress


def make_moved(agent: Any) -> Callable[..., bool]:
    """Bind ``moved(min_m=0.1)`` — did the LAST move command actually displace?

    Grades the distance between the live odometry position and the DRIVER's
    ``move_anchor_xy`` — the position the driver itself sampled from odometry
    when the last ``navigate_to()``/``walk()`` started commanding. The actor
    can trigger a move but cannot author either side of the compare (Inv-1).

    Anchor semantics are call-order independent — twin of the turned() fix
    (field trace 2026-07-13): the original first-verify-call origin capture
    sampled the POST-walk pose (verify runs AFTER the skill) and returned
    False by construction, so the model re-ran the walk — double physical
    motion; and because the closure lived for the whole session, later checks
    graded displacement from a session-old origin, letting a guard-eaten walk
    fake-pass off earlier motion. Now: True on the FIRST check after a
    completed move, stable under repeated checks, False when no move was ever
    commanded or the guard ate the commands. Fail-safe False on any error.
    """

    def moved(min_m: float = 0.1) -> bool:
        base = getattr(agent, "_base", None) if agent is not None else None
        if base is None:
            return False
        try:
            anchor = getattr(base, "move_anchor_xy", None)
            if anchor is None:
                return False
            pos = base.get_position()
            return math.hypot(
                float(pos[0]) - float(anchor[0]),
                float(pos[1]) - float(anchor[1]),
            ) >= float(min_m)
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return moved


def make_turned(agent: Any) -> Callable[..., bool]:
    """Bind ``turned(min_deg=30)`` — did the LAST turn command actually rotate?

    Grades the |wrapped| delta between live odometry yaw and the DRIVER's
    ``rotate_anchor_yaw`` — the heading the driver itself sampled from
    odometry when the last ``rotate()`` started commanding. The actor can
    trigger a rotation but cannot author either side of the compare (Inv-1).

    Anchor semantics are call-order independent — field trace 2026-07-13:
    the original first-verify-call origin capture sampled the POST-turn
    heading (verify runs AFTER the skill), graded False, and the model
    re-ran the turn: 90° of physical rotation for a 45° ask. Now: True on
    the FIRST check after a completed turn, stable under repeated checks,
    False when no rotation was ever commanded or the guard ate the commands.
    Wrap-aware: a heading crossing ±pi grades as the small turn it is; the
    wrapped delta can never exceed 180° — a 掉头 verifies with min_deg < 180
    (e.g. turned(108) for a 180° request). Fail-safe False on any error.
    """
    from zeno.vcli.worlds.go2w_real_diag import wrap_angle

    def turned(min_deg: float = 30.0) -> bool:
        base = getattr(agent, "_base", None) if agent is not None else None
        if base is None:
            return False
        try:
            anchor = getattr(base, "rotate_anchor_yaw", None)
            if anchor is None:
                return False
            yaw = float(base.get_heading())
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False
        delta = wrap_angle(yaw - float(anchor))
        return abs(math.degrees(delta)) >= float(min_deg)

    return turned


def make_stack_ready(agent: Any) -> Callable[[], bool]:
    """Bind ``stack_ready()`` — True iff fresh odometry is flowing (< 3 s old).

    The honest lifecycle oracle: the nav stack is "up" exactly when the pose
    stream everything else trusts is alive. Fail-safe False (no driver, not
    connected, stale, or any error) — the verifier sandbox never sees a raise.
    """

    def stack_ready() -> bool:
        base = getattr(agent, "_base", None) if agent is not None else None
        if base is None:
            return False
        try:
            if not getattr(base, "is_connected", False):
                return False
            # Recency ONLY: get_position() returns default zeros before any
            # odometry, so it is NOT a liveness signal (field bug 2026-07-10 —
            # a down stack graded ready and the planner skipped bringup).
            age = base.odom_age_s() if hasattr(base, "odom_age_s") else None
            return age is not None and float(age) < 3.0
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return stack_ready
