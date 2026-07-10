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
    """Bind a ``moved(min_m)`` predicate that captures a start pose on first call.

    True once the base has displaced >= ``min_m`` from where ``moved`` first
    sampled the pose — a monotonic "did it actually move" check on odometry.
    Fail-safe False when no base is wired.
    """
    origin: dict[str, tuple[float, float]] = {}

    def moved(min_m: float = 0.1) -> bool:
        base = getattr(agent, "_base", None) if agent is not None else None
        if base is None:
            return False
        try:
            pos = base.get_position()
            here = (float(pos[0]), float(pos[1]))
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False
        if "start" not in origin:
            origin["start"] = here
            return False
        sx, sy = origin["start"]
        return math.hypot(here[0] - sx, here[1] - sy) >= float(min_m)

    return moved


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
            age = base.odom_age_s() if hasattr(base, "odom_age_s") else None
            if age is not None:
                return float(age) < 3.0
            return base.get_position() is not None
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return stack_ready
