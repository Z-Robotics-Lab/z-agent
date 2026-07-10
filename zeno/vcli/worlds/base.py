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
    # The '## Loop Example' (foreach) section of the decompose prompt — the ONE
    # class-default block a world previously could NOT override, so its
    # detect_objects() teaching leaked into every world's prompt (field
    # forensics 2026-07-10, go2w_real). Additive field, LAST, defaulted (Inv-7):
    #   None (default) -> keep the GoalDecomposer class default (byte-identical
    #                     for every world that does not set it);
    #   ""             -> SUPPRESS the section (a world with no list-producing
    #                     step must not be taught a loop shape built on foreign
    #                     predicates);
    #   non-empty str  -> replace the example text with the world's own.
    foreach_example: str | None = None

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
            "foreach_example": self.foreach_example,
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

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        """Register this world's routable capabilities (Phase C).

        A *capability* is anything a sub-goal can be routed to with a typed
        ``(input -> output)`` contract: a chat LLM, a detector, a planner, a VLA
        policy, a skill, an atomic action. The dev world registers the chat
        capability (over *backend*); the robot world registers specialized models
        (C.3). Default: no-op — the kernel keeps its built-in
        skill/primitive/code/tool branches, so a world that registers nothing
        routes exactly as before. Must not import heavy deps at module load.
        """
        ...

    def decompose_vocab(self) -> "DecomposeVocab | None":
        """Return the GoalDecomposer vocabulary, or None to use kernel defaults.

        The robot world returns None so the decomposer keeps its existing
        robot defaults (derived from the skill registry).
        """
        ...

    def derive_vocab_from_registry(self) -> bool:
        """Opt into engine-side decompose-vocab derivation from the skill registry.

        When True (and ``decompose_vocab()`` returns None), the engine builds the
        decomposer vocabulary from ``skill_registry.to_schemas()`` plus the verify
        namespace, so the prompt, the validator allowlist, and the params-help are
        single-sourced and can never drift. Default False: the world either
        injects an explicit ``decompose_vocab()`` or keeps the decomposer's class
        defaults.
        """
        ...

    # ----- OPTIONAL hooks (duck-typed) --------------------------------------
    # def verify_namespace_deny(self) -> "Iterable[str]":
    #     """Names to REMOVE from the engine-built verifier namespace (opt-OUT).
    #
    #     Applied by ``engine._apply_world_verify_deny`` AFTER the world merge,
    #     so it can only REMOVE names — strictly stricter, never looser (Inv-1).
    #     Use it to strip the engine's sim-ish perception/world stubs
    #     (describe_scene/detect_objects/certainty/...) on a world that does not
    #     serve them, so ``verify_oracle_names`` never advertises a predicate
    #     that would evaluate stub-falsy. Omit the hook for the exact current
    #     namespace (dev/go2w-sim/robot are byte-identical without it).
    #     """
    #
    # The four hooks below are NOT part of the required Protocol surface: they
    # are looked up with ``getattr(world, "<hook>", None)`` by the CLI, so a world
    # that omits them is byte-identical to today. They let a *bring-your-own*
    # world (e.g. go2w) be a first-class embodiment provider WITHOUT --sim and run
    # its own lifecycle — with ZERO kernel edits. A ``Protocol`` cannot express
    # "optional method", so they are documented here rather than declared with
    # ``...`` bodies (which would make them mandatory for ``isinstance``).
    #
    # def build_embodiment(self) -> Any:
    #     """Return the AGENT object this world drives, or None to use no agent.
    #
    #     Called by the CLI (``_init_agent``) when ``--world`` selects this world
    #     and no ``--sim``/``--sim-go2`` is given: the returned object becomes the
    #     session's agent (the same slot a MuJoCo Agent fills). Duck-typed — it
    #     need only expose whatever the session reads (``_base``, ``_arm``,
    #     ``_skill_registry``, ``_spatial_memory`` — all optional). Omit the hook
    #     (or return None) to keep the no-agent dev-style session.
    #     """
    #
    # def setup(self, agent: Any) -> None:
    #     """One-time activation side-effects, called AFTER the world is resolved.
    #
    #     Runs once at session start with the resolved agent (which may be the
    #     object ``build_embodiment`` returned, or None). Best-effort — a failure
    #     is warned and swallowed so a broken setup never blocks the REPL. Use for
    #     connecting a bridge, warming a cache, etc. Omit for no setup.
    #     """
    #
    # def health(self) -> dict[str, Any]:
    #     """Return a JSON-serialisable health/status snapshot for this world.
    #
    #     Declared for BYO worlds to expose liveness (bridge reachable, sim up).
    #     NOT wired into any call site yet — reserved surface; a future health
    #     probe / status command reads it. Omit if there is nothing to report.
    #     """
    #
    # def teardown(self) -> None:
    #     """Release resources at session exit (mirror of ``setup``).
    #
    #     Called on REPL shutdown. Best-effort — a failure is warned and swallowed
    #     so teardown never masks the real exit. Use to disconnect a bridge, close
    #     a context, etc. Omit for no teardown.
    #     """
