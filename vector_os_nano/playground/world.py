# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""PlaygroundWorld — a parallel-track world for tabletop arm scenarios.

The playground is a SEPARATE world track (ADR-008). It integrates with the
kernel ONLY across the versioned public contract: the four registrations (tools,
verify namespace, decompose vocab, persona) plus the verified-loop observation
surface. The dependency edge is strictly ONE-WAY: this package imports the kernel
(``vcli.worlds.base``) + ``hardware``/``skills``; the kernel never imports the
playground except through the world registry's lazy hook.

For now the playground reuses the robot persona and single-sources its decompose
vocabulary from the skill registry (like ``RobotWorld``). Its distinct, owned
contribution is the verify namespace: deterministic sim-oracle predicates over
the connected arm + the scenario's known objects.
"""

from __future__ import annotations

from typing import Any

from vector_os_nano.playground.catalog import TABLETOP
from vector_os_nano.playground.scenario import Scenario
from vector_os_nano.playground.verify.arm_predicates import (
    make_arm_at_home,
    make_holding_object,
    make_placed_count,
)
from vector_os_nano.playground.verify.scene_predicates import (
    make_detect_objects,
    make_describe_scene,
)
from vector_os_nano.vcli.prompt import ROBOT_ROLE_PROMPT, ROBOT_TOOL_INSTRUCTIONS


class PlaygroundWorld:
    """Tabletop arm world for a playground preset scenario.

    Defaults to the bundled ``tabletop`` scenario. A different scenario can be
    injected at construction (the named registry resolves preset scenes later).
    """

    def __init__(self, scenario: Scenario | None = None) -> None:
        self._scenario: Scenario = scenario if scenario is not None else TABLETOP
        # The registry name doubles as the scenario id so resolution is 1:1.
        self.name: str = self._scenario.id

    @property
    def scenario(self) -> Scenario:
        return self._scenario

    def is_robot(self) -> bool:
        # An arm scenario drives (simulated) robot hardware.
        return True

    def persona_blocks(self) -> tuple[str, str]:
        # Reuse the robot persona for now; a playground-specific persona is a
        # later increment if the tabletop task needs distinct tool instructions.
        return ROBOT_ROLE_PROMPT, ROBOT_TOOL_INSTRUCTIONS

    def register_tools(self, registry: Any, agent: Any) -> None:
        # Arm/skill tools are registered by the CLI from discover_* + wrap_skills,
        # exactly as the robot path. No playground-specific tools yet.
        return None

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        """Return the playground's deterministic sim-oracle verify predicates.

        The engine (INC2) merges these on top of its dev/robot bindings and the
        empty perception stubs, so ``detect_objects`` / ``describe_scene`` here
        REPLACE the stubs while the playground world is active. All predicates
        are bound to *agent* + the scenario's known objects and fail safe when
        the arm is unavailable.
        """
        objects = self._scenario.object_names
        return {
            "detect_objects": make_detect_objects(agent, objects),
            "describe_scene": make_describe_scene(agent, objects),
            "holding_object": make_holding_object(agent),
            "arm_at_home": make_arm_at_home(agent),
            # The scenario's drop-zone (when defined) becomes the DEFAULT region
            # for placed_count(), so a sub-goal can verify against the scene-named
            # region without hand-passing raw coordinates.
            "placed_count": make_placed_count(
                agent, default_region=self._scenario.place_region
            ),
        }

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        # No-op for now: the playground keeps the kernel's skill/primitive routing.
        return None

    def decompose_vocab(self) -> None:
        # None => the engine derives the vocab from the live skill registry
        # (see derive_vocab_from_registry), single-sourcing the action space.
        return None

    def derive_vocab_from_registry(self) -> bool:
        # Single-source the decompose vocabulary from the skill registry, like
        # RobotWorld — no hand-authored, split-brain vocab.
        return True
