# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Playground — a parallel-track world package for tabletop arm scenarios.

ADR-008: the playground is a SEPARATE world track. It integrates with the kernel
only across the versioned public contract (tools, verify namespace, decompose
vocab, persona + the verified-loop observation surface). The dependency edge is
strictly ONE-WAY: this package imports the kernel (``vcli.worlds.*``) and
``hardware``/``skills``; the kernel NEVER imports the playground except through
the world registry's lazy hook.

Importing this package registers its preset scenarios into the process-wide world
registry (one factory per scenario id), so the kernel can ``resolve_world_named``
a playground scene without ever hard-importing this package. Registration is
idempotent and additive.
"""

from __future__ import annotations

from vector_os_nano.playground.catalog import SCENARIOS, get_scenario
from vector_os_nano.playground.scenario import Scenario
from vector_os_nano.playground.world import PlaygroundWorld

__all__ = [
    "PlaygroundWorld",
    "Scenario",
    "SCENARIOS",
    "get_scenario",
    "register_scenarios",
]


def _make_world_factory(scenario_id: str):
    """Return a zero-arg factory building a PlaygroundWorld for *scenario_id*.

    The factory resolves the scenario at call time (fail-loud on unknown id), so
    it never closes over a stale Scenario instance.
    """

    def factory() -> PlaygroundWorld:
        return PlaygroundWorld(get_scenario(scenario_id))

    return factory


def register_scenarios(registry: object | None = None) -> None:
    """Register every playground scenario into the world registry (idempotent).

    Each scenario id becomes a registered world name whose factory builds a
    ``PlaygroundWorld`` for that scenario. Re-registration is a no-op (existing
    names are skipped) so importing the package twice — or alongside the kernel's
    own bootstrap — never raises. Defaults to the process-wide registry.
    """
    if registry is None:
        from vector_os_nano.vcli.worlds.registry import get_world_registry

        registry = get_world_registry()

    is_registered = getattr(registry, "is_registered", None)
    register = getattr(registry, "register", None)
    if not callable(register):
        return
    for scenario_id in SCENARIOS:
        if callable(is_registered) and is_registered(scenario_id):
            continue
        register(scenario_id, _make_world_factory(scenario_id))


# Lazy-hook registration: importing the playground package wires its scenarios
# into the kernel's registry. The kernel does NOT import this package, so this
# runs only when the playground track is explicitly loaded — keeping the
# dependency edge one-way.
register_scenarios()
