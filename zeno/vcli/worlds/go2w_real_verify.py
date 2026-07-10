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
