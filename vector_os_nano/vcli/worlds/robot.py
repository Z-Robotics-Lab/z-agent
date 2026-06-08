# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Robot world shim.

Phase A keeps the robot path working exactly as before: this shim is the
registration *surface* (persona + "use kernel defaults" for vocab), while the
robot verify namespace and skill tools continue to be built by the engine/CLI
as today. It deliberately imports nothing robot-specific at module load.
"""

from __future__ import annotations

from typing import Any

from vector_os_nano.vcli.prompt import ROBOT_ROLE_PROMPT, ROBOT_TOOL_INSTRUCTIONS


class RobotWorld:
    """Adapter for the robot domain (Go2 / SO-101 / Piper)."""

    name = "robot"

    def is_robot(self) -> bool:
        return True

    def persona_blocks(self) -> tuple[str, str]:
        return ROBOT_ROLE_PROMPT, ROBOT_TOOL_INSTRUCTIONS

    def register_tools(self, registry: Any, agent: Any) -> None:
        # Robot/diag/sim tools are registered by the CLI from discover_*; skill
        # wrappers are added via wrap_skills(agent) at startup. No-op here in
        # Phase A (the full robot-world migration is Phase C).
        return None

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        # Ground the verifier on the SIM arm's deterministic oracle. The engine
        # builds its dev/robot bindings + empty perception stubs first
        # (engine._build_verifier_namespace), then merges THIS on top — so when a
        # sim arm is present these predicates REPLACE the stubs (detect_objects->[],
        # describe_scene->"") with real ground-truth lookups, and the planner's
        # verify allowlist (derived from this namespace) gains the arm predicates.
        #
        # Single-sourced from the kernel-side arm_sim_oracle (ADR-008 C1 / kernel
        # rule 3); lazily imported here so the module load stays robot-free per the
        # file's stated intent. object_names=() => all scene objects (the plain
        # robot world has no Scenario to declare a known-set).
        arm = getattr(agent, "_arm", None)
        if arm is None or not hasattr(arm, "get_object_positions"):
            # Real-hardware / no-arm path: contribute nothing, leaving the engine
            # namespace byte-identical (Stage 3 VLM grounding is a separate future
            # concern — not the sim oracle).
            return {}
        from vector_os_nano.vcli.worlds.arm_sim_oracle import (
            make_arm_at_home,
            make_describe_scene,
            make_detect_objects,
            make_holding_object,
            make_placed_count,
        )

        return {
            "detect_objects": make_detect_objects(agent, ()),
            "describe_scene": make_describe_scene(agent, ()),
            "holding_object": make_holding_object(agent),
            "arm_at_home": make_arm_at_home(agent),
            "placed_count": make_placed_count(agent),
        }

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        # No-op in C.1 — the robot path keeps its skill/primitive routing,
        # byte-identical. C.3 registers detectors / planners / VLA policies here.
        return None

    def decompose_vocab(self) -> None:
        # None => the engine derives the vocab from the live skill registry
        # (see derive_vocab_from_registry); falls back to GoalDecomposer class
        # defaults if no registry/namespace is available.
        return None

    def derive_vocab_from_registry(self) -> bool:
        # Single-source the decompose vocabulary from the skill registry so the
        # prompt, the validator allowlist, and the params-help can never drift.
        # Serves both go2 (has_base=True) and the arm (has_base=False); the
        # engine inspects the agent to decide has_base.
        return True
