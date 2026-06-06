# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Hardening of two v1 playground edges (owner-requested after iter 3).

1. ``placed_count(<malformed explicit region>)`` must NOT silently fall back to
   the scenario default region — it fails safe to 0 instead.
2. ``enter_scenario`` must thread ``tool_permission_resolver`` + ``persist_dir``
   into the VGG re-init, mirroring the launch path (so a mid-session switch keeps
   the interactive permission prompt instead of silently auto-denying).
"""
from __future__ import annotations

from typing import Any

from vector_os_nano.playground.verify.arm_predicates import make_placed_count


class _FakeArm:
    _connected = True

    def get_object_positions(self) -> dict[str, list[float]]:
        # Both resting (z < lift height); mug inside the drop-zone, bottle outside.
        return {"mug": [0.30, 0.10, 0.02], "bottle": [0.90, 0.90, 0.02]}


class _FakeAgent:
    def __init__(self) -> None:
        self._arm = _FakeArm()
        self._gripper = None


_DROP_ZONE = (0.20, 0.0, 0.50, 0.25)  # contains mug, not bottle


def test_placed_count_no_arg_uses_scene_default_region() -> None:
    pc = make_placed_count(_FakeAgent(), default_region=_DROP_ZONE)
    assert pc() == 1  # mug in zone, bottle out


def test_placed_count_explicit_valid_region_overrides_default() -> None:
    pc = make_placed_count(_FakeAgent(), default_region=_DROP_ZONE)
    assert pc((0.0, 0.0, 1.0, 1.0)) == 2  # both resting inside the wide region


def test_placed_count_malformed_explicit_region_fails_safe_to_zero() -> None:
    """The hardened behaviour: a malformed EXPLICIT region returns 0, NOT the
    scene default (the pre-hardening bug silently counted against the drop-zone)."""
    pc = make_placed_count(_FakeAgent(), default_region=_DROP_ZONE)
    assert pc("garbage") == 0
    assert pc((1, 2)) == 0  # wrong arity -> malformed -> 0, not the default's 1


class _CapturingEngine:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def init_vgg(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_enter_scenario_threads_resolver_and_persist_dir() -> None:
    from vector_os_nano.vcli.cli import enter_scenario

    eng = _CapturingEngine()
    sentinel_resolver = lambda n, p: True  # noqa: E731
    app_state: dict[str, Any] = {
        "engine": eng,
        "tool_permission_resolver": sentinel_resolver,
        "vgg_step_callback": None,
        "vgg_step_view_callback": None,
        "agent": None,
        "skill_registry": None,
    }

    world = enter_scenario("tabletop", app_state)

    assert eng.kwargs is not None
    # The launch-path resolver is threaded through (not dropped to None).
    assert eng.kwargs.get("tool_permission_resolver") is sentinel_resolver
    # tabletop is a robot world -> learning tier off -> persist_dir None.
    assert world.is_robot() is True
    assert eng.kwargs.get("persist_dir") is None
