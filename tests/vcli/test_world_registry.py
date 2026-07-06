# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""World/scenario resolution registry (SHARED PRELUDE 2).

Covers: agent-driven resolution (dev when no agent, robot when an agent is
present), named lookup of a registered world/scenario, fail-loud on unknown
names, register/replace semantics, and ``resolve_world()`` back-compat parity
with the agent-driven path.

No network, no robot deps — worlds are stateless shims.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from zeno.vcli.worlds import (
    DevWorld,
    RobotWorld,
    WorldRegistry,
    get_world_registry,
    resolve_world,
    resolve_world_named,
)
from zeno.vcli.worlds.registry import DEV_WORLD, ROBOT_WORLD


# ---------------------------------------------------------------------------
# Agent-driven resolution (back-compat behaviour)
# ---------------------------------------------------------------------------


class TestAgentDrivenResolution:
    def test_no_agent_resolves_dev(self) -> None:
        world = resolve_world(None)
        assert world.name == "dev"
        assert world.is_robot() is False
        assert isinstance(world, DevWorld)

    def test_agent_resolves_robot(self) -> None:
        world = resolve_world(SimpleNamespace())
        assert world.name == "robot"
        assert world.is_robot() is True
        assert isinstance(world, RobotWorld)

    def test_registry_resolve_for_agent_matches_wrapper(self) -> None:
        reg = get_world_registry()
        assert reg.resolve_for_agent(None).name == resolve_world(None).name
        assert reg.resolve_for_agent(SimpleNamespace()).name == resolve_world(SimpleNamespace()).name

    def test_resolution_returns_fresh_instances(self) -> None:
        # Factories, not singletons: each call yields a new world instance.
        assert resolve_world(None) is not resolve_world(None)


# ---------------------------------------------------------------------------
# Named resolution
# ---------------------------------------------------------------------------


class TestNamedResolution:
    def test_named_dev_and_robot(self) -> None:
        assert resolve_world_named(DEV_WORLD).name == "dev"
        assert resolve_world_named(ROBOT_WORLD).name == "robot"
        assert isinstance(resolve_world_named(DEV_WORLD), DevWorld)
        assert isinstance(resolve_world_named(ROBOT_WORLD), RobotWorld)

    def test_builtin_worlds_listed(self) -> None:
        names = get_world_registry().names()
        assert "dev" in names
        assert "robot" in names

    def test_unknown_name_fails_loud_with_valid_set(self) -> None:
        with pytest.raises(KeyError) as exc:
            resolve_world_named("nope")
        msg = str(exc.value)
        assert "nope" in msg
        # Valid set is surfaced — never a silent fallback.
        assert "dev" in msg and "robot" in msg


# ---------------------------------------------------------------------------
# Registration semantics (isolated registry — does not touch the default one)
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_register_and_resolve_named_scenario(self) -> None:
        reg = WorldRegistry()
        # A playground-style preset scene registers a factory; the registry
        # resolves it by id without importing any domain package here.
        sentinel = DevWorld()
        reg.register("playground:tabletop", lambda: sentinel)
        assert reg.resolve("playground:tabletop") is sentinel
        assert "playground:tabletop" in reg.names()

    def test_isolated_registry_still_bootstraps_builtins(self) -> None:
        reg = WorldRegistry()
        assert reg.resolve(DEV_WORLD).name == "dev"
        assert reg.resolve(ROBOT_WORLD).name == "robot"

    def test_duplicate_registration_rejected(self) -> None:
        reg = WorldRegistry()
        reg.register("scene", DevWorld)
        with pytest.raises(ValueError):
            reg.register("scene", RobotWorld)

    def test_duplicate_registration_replace_allowed(self) -> None:
        reg = WorldRegistry()
        reg.register("scene", DevWorld)
        reg.register("scene", RobotWorld, replace=True)
        assert reg.resolve("scene").name == "robot"

    def test_register_rejects_empty_name(self) -> None:
        reg = WorldRegistry()
        with pytest.raises(ValueError):
            reg.register("", DevWorld)

    def test_register_rejects_non_callable_factory(self) -> None:
        reg = WorldRegistry()
        with pytest.raises(TypeError):
            reg.register("scene", object())  # type: ignore[arg-type]

    def test_is_registered(self) -> None:
        reg = WorldRegistry()
        assert reg.is_registered(DEV_WORLD) is True
        assert reg.is_registered("unregistered-scene") is False
