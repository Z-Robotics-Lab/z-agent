# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""World / scenario resolution registry — the kernel's world discovery seam.

The kernel must never hard-import a concrete *domain* world (robot scenes, the
playground, ...) at module load. This registry is the indirection that keeps the
one-way dependency edge intact: a world/scenario registers a zero-arg *factory*
(or is registered behind a LAZY import callable), and the kernel resolves a world
by name or from a connected agent without ever importing the domain package
itself.

Two resolution modes:

1. Agent-driven (back-compat): a connected agent selects the robot world;
   otherwise the default dev world. ``resolve_world(agent)`` preserves the exact
   prior behaviour as a thin wrapper over this registry.
2. Named: ``resolve_world_named("dev" | "robot" | <scenario id>)`` instantiates a
   registered world/scenario by id. Used by the playground's preset scenes
   (registered later, parallel track) and by anything that wants an explicit
   world independent of an agent.

The two kernel worlds (``dev``, ``robot``) self-register via deferred imports the
first time the registry is used, so the registry module does not import them at
its own module load. Domain worlds register through a lazy callable so the
``vcli`` package never hard-imports a domain world.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from vector_os_nano.vcli.worlds.base import World

# A factory builds a fresh world instance. Worlds are cheap, stateless shims, so
# the registry stores factories (not singletons) and resolution returns a new
# instance per call — matching the prior ``RobotWorld()`` / ``DevWorld()`` calls.
WorldFactory = Callable[[], "World"]

# Sentinel ids for the two kernel worlds. The agent-driven resolver maps to these.
DEV_WORLD = "dev"
ROBOT_WORLD = "robot"


class WorldRegistry:
    """A small name -> world-factory registry with agent-driven resolution.

    Registration is additive: ``register(name, factory)`` binds a factory under a
    name. ``resolve(name)`` instantiates it, failing loud with the valid set when
    the name is unknown. ``resolve_for_agent(agent)`` reproduces the legacy
    selection (robot world when an agent is connected, else dev world).
    """

    def __init__(self) -> None:
        self._factories: dict[str, WorldFactory] = {}

    def register(self, name: str, factory: WorldFactory, *, replace: bool = False) -> None:
        """Register *factory* under *name*.

        Re-registering an existing name is rejected (fail loud) unless
        ``replace=True`` — this prevents a domain world from silently shadowing a
        kernel world. Names are case-sensitive ids.
        """
        if not name or not isinstance(name, str):
            raise ValueError(f"world name must be a non-empty str, got {name!r}")
        if not callable(factory):
            raise TypeError(f"world factory for {name!r} must be callable")
        if name in self._factories and not replace:
            raise ValueError(
                f"world {name!r} already registered; pass replace=True to override"
            )
        self._factories[name] = factory

    def is_registered(self, name: str) -> bool:
        """True if *name* has a registered factory (after kernel bootstrap)."""
        _ensure_builtin_worlds(self)
        return name in self._factories

    def names(self) -> tuple[str, ...]:
        """Return the sorted tuple of registered world/scenario names."""
        _ensure_builtin_worlds(self)
        return tuple(sorted(self._factories))

    def resolve(self, name: str) -> "World":
        """Instantiate the world/scenario registered under *name*.

        Fails loud with the valid set when *name* is unknown — never a silent
        fallback to another domain's world.
        """
        _ensure_builtin_worlds(self)
        try:
            factory = self._factories[name]
        except KeyError:
            valid = ", ".join(sorted(self._factories)) or "<none>"
            raise KeyError(
                f"unknown world/scenario {name!r}; valid: {valid}"
            ) from None
        return factory()

    def resolve_for_agent(self, agent: Any = None) -> "World":
        """Select a world from an agent (back-compat behaviour).

        A connected agent selects the robot world; otherwise the default dev
        world. Resolution goes through the named registry so both worlds share one
        source of truth.
        """
        name = ROBOT_WORLD if agent is not None else DEV_WORLD
        return self.resolve(name)


def _ensure_builtin_worlds(registry: "WorldRegistry") -> None:
    """Lazily register the two kernel worlds into *registry* (idempotent).

    Deferred import keeps the registry module free of concrete-world imports at
    module load. ``dev``/``robot`` live in the same ``worlds`` package as this
    file, so importing them does not cross the kernel/domain boundary; domain
    worlds (playground, robot scenes) register through their own lazy callables.
    """
    if DEV_WORLD in registry._factories and ROBOT_WORLD in registry._factories:
        return
    from vector_os_nano.vcli.worlds.dev import DevWorld
    from vector_os_nano.vcli.worlds.robot import RobotWorld

    if DEV_WORLD not in registry._factories:
        registry.register(DEV_WORLD, DevWorld)
    if ROBOT_WORLD not in registry._factories:
        registry.register(ROBOT_WORLD, RobotWorld)


# Process-wide default registry. The kernel and (later) the playground register
# into this instance. Tests that need isolation construct their own WorldRegistry.
_DEFAULT_REGISTRY = WorldRegistry()


def get_world_registry() -> WorldRegistry:
    """Return the process-wide default world registry (kernel bootstrap applied)."""
    _ensure_builtin_worlds(_DEFAULT_REGISTRY)
    return _DEFAULT_REGISTRY


def resolve_world(agent: Any = None) -> "World":
    """Select the active world (back-compat thin wrapper over the registry).

    A connected robot agent selects the robot world; otherwise the default dev
    world (the cross-platform, robot-free general agent). Preserves the exact
    prior public behaviour for ``cli.py`` and ``tools/sim_tool.py``.
    """
    return get_world_registry().resolve_for_agent(agent)


def resolve_world_named(name: str) -> "World":
    """Resolve a registered world/scenario by id, failing loud on an unknown name."""
    return get_world_registry().resolve(name)
