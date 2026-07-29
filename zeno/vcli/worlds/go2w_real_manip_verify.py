# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real manip verify predicate — the approach-complete oracle (Inv-1).

``approach_ready()`` reads the manip bridge's approach-reached LATCH — a fact set
from the Z-Mobile-manip FSM's OWN ``/z_manip/task/status`` stream when it leaves
``visual_servo`` for a handoff phase (base stopped at the standoff, before ANY arm
motion). The actor can trigger an approach but cannot author the FSM's phase
transition, so this is honest ground truth (same contract as ``route_reached()``).

Perception output (the VLM find_object bearing) is NEVER verify evidence (Inv-1);
approach is proven ONLY by this FSM-latched phase fact. Fail-safe: a missing
bridge returns False and never raises into the verifier sandbox (a missing oracle
must never fake-pass).
"""

from __future__ import annotations

from typing import Any, Callable

from zeno.vcli.cognitive.evidence_classifier import predicate_oracle


def _bridge_of(agent: Any) -> Any:
    """The manip bridge from the agent (embodiment ``_manip``, then base ride)."""
    if agent is None:
        return None
    bridge = getattr(agent, "_manip", None)
    if bridge is not None:
        return bridge
    return getattr(getattr(agent, "_base", None), "manip_bridge", None)


def make_approach_ready(agent: Any) -> Callable[[], bool]:
    """Bind ``approach_ready()`` to the agent's manip bridge.

    True iff the LAST approach reached the servo→grasp handoff (the FSM left
    ``visual_servo`` with the base stopped at the standoff), latched by the bridge
    from the task-status stream and held until the next task. Fail-safe False when
    no bridge is wired or it errors.
    """

    def approach_ready() -> bool:
        bridge = _bridge_of(agent)
        if bridge is None:
            return False
        try:
            return bool(bridge.approach_reached())
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return predicate_oracle(approach_ready)


def make_manip_stack_up(agent: Any) -> Callable[[], bool]:
    """Bind ``manip_stack_up()`` — True iff the task FSM is publishing status NOW.

    Reads the live ROS-graph publisher count on ``/z_manip/task/status`` through
    the bridge (a pure read; the bringup skill is responsible for having
    connected the bridge). The actor can run ``manip start`` but cannot author
    the FSM's own publisher into the DDS graph, so this is honest ground truth
    (same contract as ``stack_ready()``). Fail-safe False without a bridge / on
    error.
    """

    def manip_stack_up() -> bool:
        bridge = _bridge_of(agent)
        if bridge is None:
            return False
        try:
            return int(bridge.status_publisher_count()) > 0
        except Exception:  # noqa: BLE001 — verifier sandbox, fail-safe
            return False

    return predicate_oracle(manip_stack_up)
