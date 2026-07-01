# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Bring-your-own **world** — plug a new embodiment/domain into the kernel.

This is the North Star made runnable: a world (an embodiment/domain adapter)
that lives ENTIRELY in this file — not in the kernel package — registers into
the kernel's world seam and is driven through every contribution point WITHOUT
editing a single kernel file (constitution Invariant 3: worlds are CONFIG, not
code; Invariant 4: the kernel never imports a world at module load).

A ``World`` contributes five things to the domain-general kernel:

1. a **persona** (role prompt + tool instructions),
2. **tools** (registered into the kernel's tool registry under a category),
3. a **verify namespace** — ground-truth predicates the verifier grades against
   (the moat: the actor cannot author these, Invariant 1),
4. **capabilities** — routable ``(input -> output)`` units (a policy, a skill),
5. a **decompose vocabulary** — what the planner is taught about this world.

Nothing here subclasses or imports a concrete kernel world. The world satisfies
the ``World`` Protocol structurally (duck typing) and plugs into the *public*
seam only: ``get_world_registry()`` / ``resolve_world_named()`` / the ``World``
and ``DecomposeVocab`` types re-exported from ``vector_os_nano.vcli.worlds``.

Run it (no robot, no simulator, no LLM required)::

    python examples/byo_world.py

It prints proof that each seam fired and exits 0. The executable guard in
``tests/vcli/test_plug_and_play_boundary.py`` runs this file to keep the
plug-and-play promise from bit-rotting.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

# The ONLY kernel imports a world author needs: the seam. No concrete world, no
# engine internals, no editing kernel code.
from vector_os_nano.vcli.worlds import (
    DecomposeVocab,
    World,
    get_world_registry,
    resolve_world_named,
)

WORLD_ID = "byo:sorter-arm"


class SorterArmWorld:
    """A third-party 'warehouse sorter arm' world — defined outside the kernel.

    Imagine a fixed arm over a conveyor that sorts parcels into bins. All the
    kernel needs is the five contributions below; it has never heard of this
    class and does not import it.
    """

    name = WORLD_ID

    def is_robot(self) -> bool:
        # Drives (simulated/physical) hardware, so the kernel treats it as a
        # robot world (robot persona, skill routing, ...).
        return True

    def persona_blocks(self) -> tuple[str, str]:
        role = "You operate the Sorter warehouse arm over a parcel conveyor."
        tools = "Call sorter_drop(bin) to release the held parcel into a bin."
        return (role, tools)

    def register_tools(self, registry: Any, agent: Any) -> None:
        # Contribute a domain tool. The kernel's general/code tools are added by
        # the CLI regardless of world; a world adds only its own here.
        registry.register(SimpleNamespace(name="sorter_drop"), category="sorter")

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        # Ground-truth predicates the verifier grades sub-goals against. These
        # read the world's real state (here, the agent's parcel_bin), which the
        # actor cannot author — this is the moat (Invariant 1).
        return {
            "parcel_in_bin": lambda bin_id: agent.parcel_bin == bin_id,
            "arm_empty": lambda: agent.parcel_bin is not None,
        }

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        # A routable capability with a typed (input -> output) contract — a skill,
        # a policy, a detector. The kernel routes sub-goals to it.
        registry.register(SimpleNamespace(name="sorter_sort_policy"))

    def decompose_vocab(self) -> DecomposeVocab | None:
        # What the planner is taught about this world: its intro + the verify
        # functions a sub-goal's ``verify`` expression may call.
        return DecomposeVocab(
            planner_intro="Sort each parcel on the conveyor into its target bin.",
            verify_functions=frozenset({"parcel_in_bin", "arm_empty"}),
            examples='sort parcel to bin A -> verify: parcel_in_bin("A")',
        )

    def derive_vocab_from_registry(self) -> bool:
        # We supply an explicit decompose_vocab() above, so no registry-derivation.
        return False


def register() -> None:
    """Register the BYO world into the process-wide kernel registry.

    A single public call — no kernel file is touched. In a real deployment this
    would live in your package's import side-effect or an entry point.
    """
    registry = get_world_registry()
    # replace=True so re-running the example (or the test importing it twice) is
    # idempotent rather than failing loud on the second register.
    registry.register(WORLD_ID, SorterArmWorld, replace=True)


def main() -> int:
    print("Bring-your-own world — plugging into the kernel with ZERO kernel edits\n")

    # 1) The world is a structural World — no kernel subclass/import needed.
    world_instance = SorterArmWorld()
    assert isinstance(world_instance, World), "must satisfy the World Protocol"
    print(f"  [ok] {WORLD_ID!r} satisfies the World Protocol structurally")

    # 2) Register into, and resolve back out of, the public kernel seam.
    register()
    assert WORLD_ID in get_world_registry().names()
    world = resolve_world_named(WORLD_ID)
    assert world.name == WORLD_ID and world.is_robot()
    print(f"  [ok] registered and resolved {WORLD_ID!r} via the public registry")

    # 3) Drive every contribution point against plain fakes (kernel stand-ins).
    tool_registry = SimpleNamespace(
        _tools=[],
        register=lambda tool, category="default": tool_registry._tools.append(
            (category, tool.name)
        ),
    )
    cap_registry = SimpleNamespace(
        _caps=[], register=lambda cap: cap_registry._caps.append(cap.name)
    )
    # The world's own ground-truth state (kernel never authors this).
    agent = SimpleNamespace(parcel_bin=None)

    role, tools = world.persona_blocks()
    assert "Sorter" in role and "sorter_drop" in tools
    print(f"  [ok] persona: {role}")

    world.register_tools(tool_registry, agent)
    assert ("sorter", "sorter_drop") in tool_registry._tools
    print(f"  [ok] tools:   {tool_registry._tools}")

    ns = world.build_verify_namespace(agent)
    # Moat: the predicate reads real state; it flips only when the arm really acts.
    assert ns["parcel_in_bin"]("A") is False  # nothing sorted yet
    agent.parcel_bin = "A"  # the actor 'drops' the parcel into bin A
    assert ns["parcel_in_bin"]("A") is True
    print(f"  [ok] verify:  parcel_in_bin('A') -> True after a real drop")

    world.register_capabilities(cap_registry, agent, backend=object())
    assert "sorter_sort_policy" in cap_registry._caps
    print(f"  [ok] caps:    {cap_registry._caps}")

    vocab = world.decompose_vocab()
    assert vocab is not None and "parcel_in_bin" in vocab.verify_functions
    assert "verify_functions" in vocab.as_kwargs()  # feeds the planner, no kernel import
    print(f"  [ok] vocab:   verify_functions={sorted(vocab.verify_functions)}")

    print("\n  All five seams fired. A brand-new world plugged in with ZERO kernel edits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
