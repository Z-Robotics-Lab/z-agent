# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Sim-clock helpers for wall-timer controllers driving a simulation.

A controller ticking on a WALL-clock timer (e.g. a 20 Hz ROS2 timer) but
commanding a simulation whose physics advance in SIM time must integrate its
velocity ramps / accumulators against actual sim-dt, not fixed per-tick
constants: when the physics daemon is compute-bound (sim/wall < 1, e.g.
~0.65x with GUI + RViz on one machine), fixed per-tick increments slew the
command profile faster in the plant's own time than it was tuned for and
destabilize e.g. an MPC gait.
"""

from __future__ import annotations


def sim_tick_dt(
    now_sim: float | None,
    last_sim: float | None,
    nominal_dt: float,
    max_ticks: float = 4.0,
) -> float:
    """Sim-time elapsed between two controller ticks, for dt-scaled ramps.

    - ``now_sim is None`` (no readable sim clock — real hardware, clock
      error) or ``last_sim is None`` (first tick) -> ``nominal_dt``
      (the original wall-tick behavior).
    - Backwards jump (sim reset) -> ``nominal_dt``.
    - Paused/stalled sim -> ``0.0`` (ramps freeze along with the gait).
    - Clamped to ``max_ticks * nominal_dt`` so a stall/hiccup cannot slew
      commands violently on the tick after it resolves.
    """
    if now_sim is None or last_sim is None:
        return nominal_dt
    dt = now_sim - last_sim
    if dt < 0.0:
        return nominal_dt
    return min(dt, max_ticks * nominal_dt)
