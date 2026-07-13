# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real route verify predicate — far_planner arrival oracle (Inv-1).

``route_reached()`` reads the route manager's odometry-verified arrival latch
(the robot got within tolerance of the CURRENT goal, measured on
``/state_estimation`` — the pose the local planner estimates, which the actor
cannot forge). Fail-safe: a missing manager returns False and never raises into
the verifier sandbox (a missing oracle must never fake-pass — same contract as
``go2w_real_verify.py``).
"""

from __future__ import annotations

from typing import Any, Callable

from zeno.vcli.cognitive.evidence_classifier import predicate_oracle


def make_route_reached(agent: Any) -> Callable[..., bool]:
    """Bind ``route_reached()`` to the agent's route manager.

    True iff the last ``goto_via_route`` reached its goal (odometry-verified,
    latched for the current goal). Fail-safe False when no manager is wired or
    it errors.
    """

    def route_reached() -> bool:
        mgr = getattr(agent, "_route", None) if agent is not None else None
        if mgr is None:
            return False
        try:
            return bool(mgr.route_reached())
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return predicate_oracle(route_reached)
