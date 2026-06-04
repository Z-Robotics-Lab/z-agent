# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""World plugin protocol — the kernel/world seam.

The agent kernel (VectorEngine + VGG + general tools + backends + session +
permissions) is domain-general. A *world* adapts the kernel to a domain by
contributing:

1. a persona (role prompt + tool instructions),
2. tools (into the CategorizedToolRegistry under a category),
3. a verify/primitive namespace (the callables GoalVerifier evaluates
   predicates against),
4. a decompose vocabulary (what the GoalDecomposer prompt teaches).

The default ``DevWorld`` ships with the kernel; ``RobotWorld`` is the robot
adapter. The kernel never imports a concrete world at module load.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class DecomposeVocab:
    """Per-world vocabulary injected into the GoalDecomposer.

    Mirrors the GoalDecomposer constructor's injectable fields. ``as_kwargs``
    yields exactly the keyword arguments GoalDecomposer accepts, so the kernel
    never needs to import this type into the cognitive layer.
    """

    planner_intro: str
    verify_functions: frozenset[str]
    verify_fn_signatures: dict[str, str] = field(default_factory=dict)
    strategy_descriptions: dict[str, str] = field(default_factory=dict)
    strategies: frozenset[str] = frozenset()
    strategy_params_help: str = ""
    examples: str = ""
    fallback_verify: str = "True"

    def as_kwargs(self) -> dict[str, Any]:
        """Return GoalDecomposer keyword arguments for this vocabulary."""
        return {
            "planner_intro": self.planner_intro,
            "verify_functions": self.verify_functions,
            "verify_fn_signatures": dict(self.verify_fn_signatures),
            "strategy_descriptions": dict(self.strategy_descriptions),
            "strategies": self.strategies,
            "strategy_params_help": self.strategy_params_help,
            "examples": self.examples,
            "fallback_verify": self.fallback_verify,
        }


@runtime_checkable
class World(Protocol):
    """A domain adapter for the agent kernel."""

    name: str

    def is_robot(self) -> bool:
        """True if this world drives physical/simulated robot hardware."""
        ...

    def persona_blocks(self) -> tuple[str, str]:
        """Return (role_prompt, tool_instructions) static persona text."""
        ...

    def register_tools(self, registry: Any, agent: Any) -> None:
        """Register this world's tools into the CategorizedToolRegistry.

        The kernel's general tools (code/general) are registered by the CLI
        regardless of world; a world adds its domain tools here. The dev world
        is a no-op. Implementations must not import heavy deps at module load.
        """
        ...

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        """Return the verify/primitive callables for GoalVerifier.

        Always-available, side-effect-free predicates a sub-goal's ``verify``
        expression may call. Merged into the engine's verifier namespace.
        """
        ...

    def decompose_vocab(self) -> "DecomposeVocab | None":
        """Return the GoalDecomposer vocabulary, or None to use kernel defaults.

        The robot world returns None so the decomposer keeps its existing
        robot defaults (derived from the skill registry).
        """
        ...
