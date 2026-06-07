# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Playground E-1 — a SECOND embodiment: the Go2 quadruped (mobile base).

Proves the playground/seam generalizes beyond the arm. Covers:
- the base predicates (at_position / facing / visited) against a FAKE base
  exposing get_position / get_heading,
- fail-safe behaviour when the base is absent / not connected (never raises),
- the world registry wiring (resolve_world_named("go2_room") -> a has_base
  PlaygroundWorld) and the --scenario launch path,
- a kernel-integration test: the go2 PlaygroundWorld wired into VectorEngine, the
  base predicates evaluated THROUGH the real GoalVerifier off the merged
  namespace (the "test with vector-os-nano" gate),
- the decompose vocab: with a connected base the engine puts the base primitives
  (walk_forward/turn/scan_360) AND go2 skills in vocab; an arm-only agent never
  sees them,
- the existing ARM scenarios stay unaffected (predicate sets do not bleed).

No MuJoCo / network — the base is a deterministic fake.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from vector_os_nano.playground import PlaygroundWorld, register_scenarios
from vector_os_nano.playground.catalog import GO2_ROOM, get_scenario
from vector_os_nano.playground.verify.base_predicates import _FACING_TOL_RAD


# ---------------------------------------------------------------------------
# Deterministic fakes (no MuJoCo)
# ---------------------------------------------------------------------------


class FakeBase:
    """A deterministic stand-in for MuJoCoGo2's oracle surface.

    Exposes the two state queries the base predicates read: get_position (xyz)
    and get_heading (yaw radians). Like MuJoCoGo2 it carries a ``_connected``
    flag the predicates respect.
    """

    def __init__(
        self,
        position: list[float],
        heading: float,
        connected: bool = True,
    ) -> None:
        self._position = list(position)
        self._heading = float(heading)
        self._connected = connected

    def get_position(self) -> list[float]:
        if not self._connected:
            raise RuntimeError("FakeBase: not connected")
        return list(self._position)

    def get_heading(self) -> float:
        if not self._connected:
            raise RuntimeError("FakeBase: not connected")
        return self._heading


def _go2_world() -> PlaygroundWorld:
    return PlaygroundWorld(GO2_ROOM)


def _base_agent(base: Any = None) -> SimpleNamespace:
    return SimpleNamespace(_base=base)


# ---------------------------------------------------------------------------
# Scenario / world contract
# ---------------------------------------------------------------------------


class TestGo2Scenario:
    def test_scenario_registered_and_has_base(self) -> None:
        register_scenarios()  # idempotent
        from vector_os_nano.vcli.worlds.registry import resolve_world_named

        world = resolve_world_named("go2_room")
        assert type(world).__name__ == "PlaygroundWorld"
        assert world.name == "go2_room"
        assert world.is_robot() is True
        assert world.has_base() is True
        assert world.embodiment == "go2"

    def test_arm_scenario_reports_no_base(self) -> None:
        # The arm scenario must NOT claim a base — embodiments don't bleed.
        assert PlaygroundWorld().has_base() is False
        assert PlaygroundWorld().embodiment == "arm"

    def test_go2_scenario_has_named_rooms(self) -> None:
        scen = get_scenario("go2_room")
        assert "kitchen" in scen.rooms
        # Each room is a 4-tuple (x_min, y_min, x_max, y_max).
        assert all(len(box) == 4 for box in scen.rooms.values())

    def test_decompose_vocab_single_sourced(self) -> None:
        world = _go2_world()
        assert world.decompose_vocab() is None
        assert world.derive_vocab_from_registry() is True


# ---------------------------------------------------------------------------
# Base predicates: at_position
# ---------------------------------------------------------------------------


class TestAtPosition:
    def test_true_at_target(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.0, 0.5, 0.3], heading=0.0))
        )
        assert ns["at_position"](2.0, 0.5) is True

    def test_true_within_tolerance(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.2, 0.5, 0.3], heading=0.0))
        )
        # 0.2 m off, default tol is 0.5 m -> within.
        assert ns["at_position"](2.0, 0.5) is True

    def test_false_outside_tolerance(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[5.0, 5.0, 0.3], heading=0.0))
        )
        assert ns["at_position"](2.0, 0.5) is False

    def test_explicit_tol_respected(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.4, 0.5, 0.3], heading=0.0))
        )
        # 0.4 m off: outside a tight 0.1 m tol, inside a loose 1.0 m tol.
        assert ns["at_position"](2.0, 0.5, 0.1) is False
        assert ns["at_position"](2.0, 0.5, 1.0) is True

    def test_bad_args_fail_safe(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.0, 0.5, 0.3], heading=0.0))
        )
        assert ns["at_position"]("x", None) is False


# ---------------------------------------------------------------------------
# Base predicates: facing
# ---------------------------------------------------------------------------


class TestFacing:
    def test_true_at_heading(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[0.0, 0.0, 0.3], heading=math.pi / 2))
        )
        assert ns["facing"](math.pi / 2) is True

    def test_wraps_across_pi_seam(self) -> None:
        # Heading just past +pi vs target just past -pi: ~0 actual delta.
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[0.0, 0.0, 0.3], heading=math.pi - 0.05))
        )
        assert ns["facing"](-math.pi + 0.05) is True

    def test_false_when_off_heading(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[0.0, 0.0, 0.3], heading=0.0))
        )
        assert ns["facing"](math.pi) is False

    def test_default_tol(self) -> None:
        # A small offset under the 20-deg default tol passes.
        off = _FACING_TOL_RAD * 0.5
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[0.0, 0.0, 0.3], heading=off))
        )
        assert ns["facing"](0.0) is True


# ---------------------------------------------------------------------------
# Base predicates: visited
# ---------------------------------------------------------------------------


class TestVisited:
    def test_true_inside_named_room(self) -> None:
        # kitchen box is (1, -1, 4, 1); (2, 0) is inside.
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.0, 0.0, 0.3], heading=0.0))
        )
        assert ns["visited"]("kitchen") is True

    def test_false_outside_named_room(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.0, 0.0, 0.3], heading=0.0))
        )
        # bedroom box is (1, 1, 4, 4); (2, 0) is NOT inside.
        assert ns["visited"]("bedroom") is False

    def test_unknown_room_fails_safe(self) -> None:
        ns = _go2_world().build_verify_namespace(
            _base_agent(FakeBase(position=[2.0, 0.0, 0.3], heading=0.0))
        )
        # An unknown room name is NOT silently treated as "anywhere".
        assert ns["visited"]("atlantis") is False


# ---------------------------------------------------------------------------
# Fail-safe: no base / not connected / raising oracle => never raises
# ---------------------------------------------------------------------------


class TestFailSafe:
    @pytest.mark.parametrize("agent", [None, SimpleNamespace(_base=None)])
    def test_predicates_fail_safe_without_base(self, agent: Any) -> None:
        ns = _go2_world().build_verify_namespace(agent)
        assert ns["at_position"](0.0, 0.0) is False
        assert ns["facing"](0.0) is False
        assert ns["visited"]("kitchen") is False

    def test_predicates_fail_safe_when_disconnected(self) -> None:
        base = FakeBase(position=[2.0, 0.0, 0.3], heading=0.0, connected=False)
        ns = _go2_world().build_verify_namespace(_base_agent(base))
        assert ns["at_position"](2.0, 0.0) is False
        assert ns["facing"](0.0) is False
        assert ns["visited"]("kitchen") is False

    def test_predicates_fail_safe_when_oracle_raises(self) -> None:
        class BoomBase:
            _connected = True

            def get_position(self):
                raise RuntimeError("sim exploded")

            def get_heading(self):
                raise RuntimeError("sim exploded")

        ns = _go2_world().build_verify_namespace(_base_agent(BoomBase()))
        assert ns["at_position"](0.0, 0.0) is False
        assert ns["facing"](0.0) is False
        assert ns["visited"]("kitchen") is False


# ---------------------------------------------------------------------------
# Kernel integration: predicates through the real GoalVerifier + the engine
# ---------------------------------------------------------------------------


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


class TestKernelIntegration:
    def test_base_predicates_via_goal_verifier(self) -> None:
        from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier

        base = FakeBase(position=[2.0, 0.0, 0.3], heading=0.0)
        agent = _base_agent(base)
        eng = _make_engine()
        eng.init_vgg(agent=agent, world=_go2_world())
        assert type(eng._world).__name__ == "PlaygroundWorld"

        ns = eng._build_verifier_namespace(agent)
        # Base predicates are present (and the arm-only stubs were not injected
        # by the go2 world).
        assert {"at_position", "facing", "visited"} <= set(ns)

        gv = GoalVerifier(ns)
        assert gv.verify("at_position(2.0, 0.0)") is True
        assert gv.verify("facing(0.0)") is True
        assert gv.verify("visited('kitchen')") is True
        assert gv.verify("visited('bedroom')") is False

    def test_resolved_via_scenario_flag(self) -> None:
        """The --scenario launch path resolves the go2 playground world."""
        from vector_os_nano.vcli.cli import _resolve_active_world, parse_args

        args = parse_args(["--scenario", "go2_room"])
        world = _resolve_active_world(args, agent=_base_agent(None))
        assert type(world).__name__ == "PlaygroundWorld"
        assert world.name == "go2_room"
        assert world.has_base() is True


# ---------------------------------------------------------------------------
# Decompose vocab: base primitives + go2 skills are in-vocab with a base agent;
# an arm-only agent never sees them (mechanism is agent-driven, not world-driven).
# ---------------------------------------------------------------------------


class _FakeSkill:
    def __init__(self, name: str, description: str) -> None:
        self._schema = {"name": name, "description": description, "parameters": {}}

    def to_schema(self) -> dict:
        return dict(self._schema)


class _FakeSkillRegistry:
    """Minimal skill registry exposing to_schemas() like the real one."""

    def __init__(self, schemas: list[dict]) -> None:
        self._schemas = schemas

    def to_schemas(self) -> list[dict]:
        return [dict(s) for s in self._schemas]


class TestDecomposeVocabRouting:
    def _schemas(self) -> list[dict]:
        # Stand in for skills/go2 explore + look discovered from the registry.
        return [
            {"name": "explore", "description": "Explore the environment", "parameters": {}},
            {"name": "look", "description": "Look in a direction", "parameters": {}},
        ]

    def test_base_agent_gets_base_primitives_and_go2_skills(self) -> None:
        eng = _make_engine()
        eng._world = _go2_world()
        reg = _FakeSkillRegistry(self._schemas())
        agent = _base_agent(FakeBase(position=[0.0, 0.0, 0.3], heading=0.0))

        # has_base=True path: base primitives present, go2 skills present.
        kwargs = eng._build_registry_vocab_kwargs(reg, agent, has_base=True)
        strategies = set(kwargs["strategies"])
        assert {"walk_forward", "turn", "scan_360"} <= strategies
        assert {"explore_skill", "look_skill"} <= strategies

    def test_arm_agent_never_sees_base_primitives(self) -> None:
        eng = _make_engine()
        eng._world = PlaygroundWorld()  # arm scenario
        reg = _FakeSkillRegistry(self._schemas())
        agent = SimpleNamespace(_arm=None, _base=None)

        kwargs = eng._build_registry_vocab_kwargs(reg, agent, has_base=False)
        strategies = set(kwargs["strategies"])
        assert not ({"walk_forward", "turn", "scan_360"} & strategies)


# ---------------------------------------------------------------------------
# Arm scenarios stay unaffected (regression guard).
# ---------------------------------------------------------------------------


class TestArmUnaffected:
    def test_arm_scenario_predicate_set_unchanged(self) -> None:
        ns = PlaygroundWorld().build_verify_namespace(SimpleNamespace(_arm=None))
        assert {
            "detect_objects",
            "describe_scene",
            "holding_object",
            "arm_at_home",
            "placed_count",
        } <= set(ns)
        # No base predicates leak into an arm scenario.
        assert not ({"at_position", "facing", "visited"} & set(ns))
