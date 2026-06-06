# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Playground (INC4) — LIVE wiring of a playground scenario into the engine.

Covers the scenario selector added to the CLI:
- ``--scenario tabletop`` resolves the playground world (via the lazy registry
  hook) and, wired through the engine exactly as ``main()`` does, makes the
  engine's verifier namespace carry the playground predicates
  (detect_objects / holding_object / arm_at_home / placed_count).
- The assertions go THROUGH the engine (parse_args -> _resolve_active_world ->
  init_vgg/_build_verifier_namespace), never by importing the playground into
  the kernel under test.
- An unknown scenario id fails LOUD with the valid set.
- The default (no --scenario) path is byte-unchanged: agent -> robot, none -> dev.

No MuJoCo / network — the arm is a deterministic fake.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from vector_os_nano.vcli.cli import _resolve_active_world, parse_args


# ---------------------------------------------------------------------------
# Deterministic fake arm (no MuJoCo) — same oracle surface the predicates read.
# ---------------------------------------------------------------------------


class FakeArm:
    def __init__(
        self,
        objects: dict[str, list[float]],
        joints: list[float],
        ee: list[float],
        connected: bool = True,
    ) -> None:
        self._objects = objects
        self._joints = list(joints)
        self._ee = list(ee)
        self._connected = connected

    def get_object_positions(self) -> dict[str, list[float]]:
        return {k: list(v) for k, v in self._objects.items()}

    def get_joint_positions(self) -> list[float]:
        return list(self._joints)

    def fk(self, joint_positions: list[float]):
        return list(self._ee), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _fake_arm_agent() -> SimpleNamespace:
    from vector_os_nano.playground.verify.arm_predicates import _HOME_JOINTS

    arm = FakeArm(
        objects={"mug": [0.22, 0.05, 0.06], "banana": [0.12, 0.12, 0.06]},
        joints=list(_HOME_JOINTS),
        ee=[0.2, 0.0, 0.2],
    )
    return SimpleNamespace(_arm=arm, _gripper=None)


def _make_engine():
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.intent_router import IntentRouter
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry

    class _MockBackend:
        def call(self, messages, tools, system, max_tokens, on_text=None):
            class _R:
                text = "{}"

            return _R()

    return VectorEngine(
        backend=_MockBackend(),
        registry=CategorizedToolRegistry(),
        system_prompt=[],
        intent_router=IntentRouter(),
    )


_PLAYGROUND_PREDICATES = {
    "detect_objects",
    "describe_scene",
    "holding_object",
    "arm_at_home",
    "placed_count",
}


# ---------------------------------------------------------------------------
# --scenario selects the playground world (asserted through the engine).
# ---------------------------------------------------------------------------


class TestScenarioSelectsPlayground:
    def test_resolved_world_is_playground(self) -> None:
        args = parse_args(["--scenario", "tabletop"])
        world = _resolve_active_world(args, agent=None)
        # Assert via the class name / contract, not by importing PlaygroundWorld
        # as a type the kernel would have to know — the world is a duck-typed
        # contract object resolved through the registry.
        assert type(world).__name__ == "PlaygroundWorld"
        assert world.name == "tabletop"
        assert world.is_robot() is True

    def test_engine_namespace_carries_playground_predicates(self) -> None:
        """The selected world, wired into the engine like main() does, makes the
        BUILT verifier namespace contain the playground predicates."""
        args = parse_args(["--scenario", "tabletop"])
        agent = _fake_arm_agent()
        world = _resolve_active_world(args, agent)

        eng = _make_engine()
        # init_vgg(world=...) is the production path that sets engine._world
        # BEFORE the verifier namespace is built. Use it directly so the test
        # exercises the same wiring main() relies on.
        eng.init_vgg(agent=agent, world=world)
        assert type(eng._world).__name__ == "PlaygroundWorld"

        ns = eng._build_verifier_namespace(agent)
        assert _PLAYGROUND_PREDICATES <= set(ns)

    def test_playground_predicates_evaluate_through_goal_verifier(self) -> None:
        """End-to-end: predicates from the selected scenario evaluate through the
        real GoalVerifier off the engine's merged namespace."""
        from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier

        args = parse_args(["--scenario", "tabletop"])
        agent = _fake_arm_agent()
        world = _resolve_active_world(args, agent)
        eng = _make_engine()
        eng.init_vgg(agent=agent, world=world)
        ns = eng._build_verifier_namespace(agent)

        gv = GoalVerifier(ns)
        # The playground oracle replaced the engine's empty detect_objects stub.
        assert gv.verify("len(detect_objects()) > 0") is True
        assert gv.verify("arm_at_home()") is True
        assert gv.verify("holding_object()") is False  # no gripper holding


# ---------------------------------------------------------------------------
# Unknown scenario id fails loud (never a silent fallback).
# ---------------------------------------------------------------------------


class TestUnknownScenarioFailsLoud:
    def test_unknown_id_raises_keyerror_with_valid_set(self) -> None:
        args = parse_args(["--scenario", "does-not-exist"])
        with pytest.raises(KeyError) as exc_info:
            _resolve_active_world(args, agent=None)
        msg = str(exc_info.value)
        assert "does-not-exist" in msg
        # The valid set is surfaced so the failure is actionable.
        assert "tabletop" in msg


# ---------------------------------------------------------------------------
# Default (no --scenario) path is unchanged: agent -> robot, none -> dev.
# ---------------------------------------------------------------------------


class TestDefaultUnchanged:
    def test_no_scenario_no_agent_resolves_dev(self) -> None:
        args = parse_args([])
        world = _resolve_active_world(args, agent=None)
        assert type(world).__name__ == "DevWorld"
        assert world.is_robot() is False

    def test_no_scenario_with_agent_resolves_robot(self) -> None:
        args = parse_args([])
        agent: Any = SimpleNamespace(_arm=None, _base=None)
        world = _resolve_active_world(args, agent)
        assert type(world).__name__ == "RobotWorld"
        assert world.is_robot() is True

    def test_default_matches_resolve_world(self) -> None:
        """The no-scenario branch is exactly resolve_world(agent)."""
        from vector_os_nano.vcli.worlds import resolve_world

        args = parse_args([])
        agent: Any = SimpleNamespace(_arm=None, _base=None)
        assert (
            type(_resolve_active_world(args, agent)).__name__
            == type(resolve_world(agent)).__name__
        )
        assert (
            type(_resolve_active_world(args, None)).__name__
            == type(resolve_world(None)).__name__
        )
