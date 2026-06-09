# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Playground (INC3) — deterministic sim-oracle verify predicates.

Covers:
- the arm predicates (holding_object / arm_at_home / placed_count) against a
  FAKE arm exposing get_object_positions / get_joint_positions / fk,
- the scene predicates (detect_objects / describe_scene) returning the same
  shapes the engine stubs use,
- fail-safe behaviour when the arm is absent / not connected (never raises),
- the world registry wiring (resolve_world_named -> PlaygroundWorld),
- a kernel-integration test: PlaygroundWorld wired into VectorEngine, the merged
  verifier namespace evaluated THROUGH the real GoalVerifier (the "test with
  vector-os-nano" gate).

No MuJoCo / network — the arm is a deterministic fake.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from vector_os_nano.playground import PlaygroundWorld, register_scenarios
from vector_os_nano.playground.catalog import TABLETOP
from vector_os_nano.playground.verify.arm_predicates import _HOME_JOINTS


# ---------------------------------------------------------------------------
# Deterministic fakes (no MuJoCo)
# ---------------------------------------------------------------------------


class FakeArm:
    """A deterministic stand-in for MuJoCoArm's oracle surface.

    Exposes the three oracle methods the predicates read: get_object_positions,
    get_joint_positions, fk. EE position is supplied directly (FK is a pure
    lookup here — the predicates only need a deterministic xyz).
    """

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
        # Deterministic: EE is fixed regardless of the queried joints.
        return list(self._ee), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


class FakeGripper:
    def __init__(self, holding: bool) -> None:
        self._holding = holding

    def is_holding(self) -> bool:
        return self._holding


def _agent(arm: Any = None, gripper: Any = None) -> SimpleNamespace:
    return SimpleNamespace(_arm=arm, _gripper=gripper)


_HOME = list(_HOME_JOINTS)


# ---------------------------------------------------------------------------
# Home-pose single-source agreement
# ---------------------------------------------------------------------------


def test_home_pose_matches_home_skill_default() -> None:
    """The verify home pose must agree with the home SKILL's motion default."""
    from vector_os_nano.skills.home import _DEFAULT_HOME_JOINTS

    assert list(_HOME_JOINTS) == list(_DEFAULT_HOME_JOINTS)


# ---------------------------------------------------------------------------
# arm_at_home
# ---------------------------------------------------------------------------


class TestArmAtHome:
    def test_true_at_home(self) -> None:
        arm = FakeArm(objects={}, joints=_HOME, ee=[0.2, 0.0, 0.2])
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        assert ns["arm_at_home"]() is True

    def test_within_tolerance(self) -> None:
        jittered = [j + 0.05 for j in _HOME]  # < 0.10 tol
        arm = FakeArm(objects={}, joints=jittered, ee=[0.2, 0.0, 0.2])
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        assert ns["arm_at_home"]() is True

    def test_false_away_from_home(self) -> None:
        away = [j + 0.5 for j in _HOME]
        arm = FakeArm(objects={}, joints=away, ee=[0.2, 0.0, 0.2])
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        assert ns["arm_at_home"]() is False

    def test_false_wrong_dof_count(self) -> None:
        arm = FakeArm(objects={}, joints=_HOME[:3], ee=[0.2, 0.0, 0.2])
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        assert ns["arm_at_home"]() is False


# ---------------------------------------------------------------------------
# holding_object
# ---------------------------------------------------------------------------


class TestHoldingObject:
    def test_true_when_lifted_near_ee_and_gripper_closed(self) -> None:
        ee = [0.20, 0.10, 0.25]
        arm = FakeArm(
            objects={"mug": [0.21, 0.10, 0.24]},  # lifted (z>0.10), near EE
            joints=_HOME,
            ee=ee,
        )
        ns = PlaygroundWorld().build_verify_namespace(
            _agent(arm, FakeGripper(holding=True))
        )
        assert ns["holding_object"]() is True

    def test_false_when_gripper_open(self) -> None:
        ee = [0.20, 0.10, 0.25]
        arm = FakeArm(objects={"mug": [0.21, 0.10, 0.24]}, joints=_HOME, ee=ee)
        ns = PlaygroundWorld().build_verify_namespace(
            _agent(arm, FakeGripper(holding=False))
        )
        assert ns["holding_object"]() is False

    def test_false_when_object_on_table(self) -> None:
        # Object near EE in xy but resting on the table (z below lift height).
        ee = [0.20, 0.10, 0.06]
        arm = FakeArm(objects={"mug": [0.21, 0.10, 0.06]}, joints=_HOME, ee=ee)
        ns = PlaygroundWorld().build_verify_namespace(
            _agent(arm, FakeGripper(holding=True))
        )
        assert ns["holding_object"]() is False

    def test_false_when_object_far_from_ee(self) -> None:
        ee = [0.20, 0.10, 0.25]
        arm = FakeArm(objects={"mug": [0.60, 0.50, 0.24]}, joints=_HOME, ee=ee)
        ns = PlaygroundWorld().build_verify_namespace(
            _agent(arm, FakeGripper(holding=True))
        )
        assert ns["holding_object"]() is False

    def test_false_without_gripper(self) -> None:
        ee = [0.20, 0.10, 0.25]
        arm = FakeArm(objects={"mug": [0.21, 0.10, 0.24]}, joints=_HOME, ee=ee)
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm, gripper=None))
        assert ns["holding_object"]() is False


# ---------------------------------------------------------------------------
# placed_count
# ---------------------------------------------------------------------------


class TestPlacedCount:
    def test_counts_resting_objects_no_region(self) -> None:
        arm = FakeArm(
            objects={
                "mug": [0.21, 0.10, 0.06],  # resting
                "banana": [0.12, 0.12, 0.06],  # resting
                "bottle": [0.30, 0.12, 0.30],  # lifted -> not placed
            },
            joints=_HOME,
            ee=[0.2, 0.0, 0.2],
        )
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        assert ns["placed_count"]() == 2

    def test_counts_only_in_region(self) -> None:
        arm = FakeArm(
            objects={
                "mug": [0.21, 0.10, 0.06],  # inside region
                "banana": [0.80, 0.80, 0.06],  # outside region
            },
            joints=_HOME,
            ee=[0.2, 0.0, 0.2],
        )
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        # region (x_min, y_min, x_max, y_max)
        assert ns["placed_count"]((0.0, 0.0, 0.4, 0.4)) == 1

    def test_malformed_explicit_region_fails_safe_to_zero(self) -> None:
        arm = FakeArm(
            objects={"mug": [0.21, 0.10, 0.06]},
            joints=_HOME,
            ee=[0.2, 0.0, 0.2],
        )
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        # Hardened contract: a malformed EXPLICIT region must not raise AND must
        # not widen to count-all (that would let a verify gate falsely PASS). It
        # fails safe to 0, rather than silently adopting any other region.
        assert ns["placed_count"]("not-a-region") == 0


# ---------------------------------------------------------------------------
# detect_objects / describe_scene (scene oracle)
# ---------------------------------------------------------------------------


class TestSceneOracle:
    def _arm(self) -> FakeArm:
        return FakeArm(
            objects={
                "mug": [0.22, 0.05, 0.06],
                "banana": [0.12, 0.12, 0.06],
                "ghost": [9.0, 9.0, 9.0],  # not a known scenario object
            },
            joints=_HOME,
            ee=[0.2, 0.0, 0.2],
        )

    def test_detect_objects_shape_is_list_of_dict(self) -> None:
        ns = PlaygroundWorld().build_verify_namespace(_agent(self._arm()))
        objs = ns["detect_objects"]()
        assert isinstance(objs, list)
        assert all(isinstance(o, dict) for o in objs)
        names = {o["name"] for o in objs}
        # Only known scenario objects; the stray body is filtered out.
        assert names == {"mug", "banana"}
        assert all({"name", "x", "y", "z"} <= set(o) for o in objs)

    def test_detect_objects_query_filters(self) -> None:
        ns = PlaygroundWorld().build_verify_namespace(_agent(self._arm()))
        objs = ns["detect_objects"]("mug")
        assert [o["name"] for o in objs] == ["mug"]

    def test_describe_scene_is_nonempty_str(self) -> None:
        ns = PlaygroundWorld().build_verify_namespace(_agent(self._arm()))
        desc = ns["describe_scene"]()
        assert isinstance(desc, str)
        assert "mug" in desc and "banana" in desc


# ---------------------------------------------------------------------------
# Fail-safe: no arm / not connected => stub-shaped values, never raises
# ---------------------------------------------------------------------------


class TestFailSafe:
    @pytest.mark.parametrize("agent", [None, SimpleNamespace(_arm=None)])
    def test_predicates_fail_safe_without_arm(self, agent: Any) -> None:
        ns = PlaygroundWorld().build_verify_namespace(agent)
        assert ns["detect_objects"]() == []
        assert ns["describe_scene"]() == ""
        assert ns["holding_object"]() is False
        assert ns["arm_at_home"]() is False
        assert ns["placed_count"]() == 0

    def test_predicates_fail_safe_when_disconnected(self) -> None:
        arm = FakeArm(objects={"mug": [0.2, 0.1, 0.2]}, joints=_HOME, ee=[0.2, 0.0, 0.2])
        arm._connected = False
        ns = PlaygroundWorld().build_verify_namespace(_agent(arm))
        assert ns["detect_objects"]() == []
        assert ns["arm_at_home"]() is False

    def test_predicates_fail_safe_when_oracle_raises(self) -> None:
        class BoomArm:
            _connected = True

            def get_object_positions(self):
                raise RuntimeError("sim exploded")

            def get_joint_positions(self):
                raise RuntimeError("sim exploded")

            def fk(self, joints):
                raise RuntimeError("sim exploded")

        ns = PlaygroundWorld().build_verify_namespace(_agent(BoomArm()))
        # A raising oracle must never propagate into the verifier.
        assert ns["detect_objects"]() == []
        assert ns["arm_at_home"]() is False
        assert ns["placed_count"]() == 0


# ---------------------------------------------------------------------------
# World registry wiring (lazy hook)
# ---------------------------------------------------------------------------


class TestRegistryWiring:
    def test_tabletop_resolvable_by_name(self) -> None:
        from vector_os_nano.vcli.worlds.registry import resolve_world_named

        register_scenarios()  # idempotent
        world = resolve_world_named("tabletop")
        assert isinstance(world, PlaygroundWorld)
        assert world.name == "tabletop"
        assert world.is_robot() is True
        assert world.scenario.object_names == TABLETOP.object_names

    def test_register_scenarios_idempotent(self) -> None:
        from vector_os_nano.vcli.worlds.registry import get_world_registry

        register_scenarios()
        register_scenarios()  # must not raise on the second pass
        assert "tabletop" in get_world_registry().names()

    def test_decompose_vocab_single_sourced(self) -> None:
        world = PlaygroundWorld()
        assert world.decompose_vocab() is None
        assert world.derive_vocab_from_registry() is True


# ---------------------------------------------------------------------------
# Kernel integration: predicates through the real GoalVerifier (the gate)
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
    def test_playground_predicates_via_goal_verifier(self) -> None:
        """PlaygroundWorld wired into the engine; predicates evaluate through the
        real GoalVerifier off the merged verifier namespace."""
        from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier

        arm = FakeArm(
            objects={"mug": [0.22, 0.05, 0.06], "banana": [0.12, 0.12, 0.06]},
            joints=_HOME,
            ee=[0.2, 0.0, 0.2],
        )
        agent = _agent(arm)
        eng = _make_engine()
        eng._world = PlaygroundWorld()
        ns = eng._build_verifier_namespace(agent)

        # The playground predicates replaced the engine's empty perception stubs.
        assert "holding_object" in ns and "placed_count" in ns
        gv = GoalVerifier(ns)
        assert gv.verify("len(detect_objects()) > 0") is True
        assert gv.verify("arm_at_home()") is True
        assert gv.verify("placed_count() == 2") is True
        assert gv.verify("holding_object()") is False  # no gripper holding

    def test_engine_resolves_playground_when_wired(self) -> None:
        """With no explicit _world, the engine still merges a world; wiring the
        playground makes its detect_objects override the empty stub."""
        from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier

        arm = FakeArm(
            objects={"mug": [0.22, 0.05, 0.06]}, joints=_HOME, ee=[0.2, 0.0, 0.2]
        )
        eng = _make_engine()
        eng._world = PlaygroundWorld()
        ns = eng._build_verifier_namespace(_agent(arm))
        gv = GoalVerifier(ns)
        # Stub would give [] -> 0; the playground oracle reports the mug.
        assert gv.verify("len(detect_objects('mug')) == 1") is True
