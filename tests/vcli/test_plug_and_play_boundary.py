# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Executable guard for the North Star's load-bearing plug-and-play claim.

Two constitution invariants are asserted here as *tests*, not prose:

* **Invariant 4** — the kernel never imports a concrete world at module load.
  Importing the kernel engine must not transitively pull in any concrete world
  module (a domain world like the playground, *or* the built-in dev/robot
  worlds). Concrete worlds must load only when a world is actually resolved.
  This is checked in a FRESH subprocess so the result reflects a clean
  ``sys.modules``, not whatever the pytest session already imported.

* **Invariant 3** — embodiments/worlds are CONFIG, not code: a brand-new
  "bring-your-own" world plugs into the kernel seam (registry + World Protocol)
  and is fully driven WITHOUT editing a single kernel file. The synthetic world
  below lives entirely in this test; if it registers, resolves, and every
  Protocol method is exercised against plain fakes, the seam is genuinely
  open (no kernel edit required to add a world).

Both checks are offline and LLM-free: the ground truth is the import graph and
the Protocol contract, neither of which the actor can author.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]

from vector_os_nano.vcli.worlds import DecomposeVocab, World
from vector_os_nano.vcli.worlds.registry import WorldRegistry

# ---------------------------------------------------------------------------
# Invariant 4 — kernel import purity (fresh-interpreter, no concrete-world leak)
# ---------------------------------------------------------------------------

# Substrings that identify a CONCRETE world module. The seam itself
# (``worlds``/``worlds.base``/``worlds.registry``) is allowed to load — it is
# the indirection that keeps the boundary intact — but a concrete world
# (dev/robot/go2 scenes/playground) must not load merely from importing the
# kernel.
_CONCRETE_WORLD_MARKERS = (
    "vcli.worlds.dev",
    "vcli.worlds.robot",
    "vcli.worlds.go2",
    "vcli.worlds.scene",
    "playground",
)

_LEAK_PROBE = r"""
import sys
import vector_os_nano.vcli.engine  # the domain-general kernel
markers = {markers!r}
leaked = sorted(
    m for m in sys.modules
    if any(k in m for k in markers)
)
print("\n".join(leaked))
"""


def _concrete_worlds_loaded_by_importing(module: str, markers: tuple[str, ...]) -> list[str]:
    """Return concrete-world modules present after importing *module* clean.

    Runs in a fresh interpreter so the answer is not contaminated by the pytest
    session's already-populated ``sys.modules``.
    """
    probe = _LEAK_PROBE.replace("vector_os_nano.vcli.engine", module).format(markers=markers)
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"probe import of {module!r} failed:\n{result.stderr}"
    )
    return [ln for ln in result.stdout.splitlines() if ln.strip()]


def test_kernel_import_leaks_no_concrete_world() -> None:
    """Importing the kernel engine must not load any concrete world (Invariant 4)."""
    leaked = _concrete_worlds_loaded_by_importing(
        "vector_os_nano.vcli.engine", _CONCRETE_WORLD_MARKERS
    )
    assert leaked == [], (
        "importing the kernel engine eagerly loaded concrete world module(s) "
        f"{leaked!r}; worlds must load only on resolution (Invariant 4 — the "
        "kernel never imports a world at module load)"
    )


def test_cli_entry_import_leaks_no_concrete_world() -> None:
    """Importing the CLI entry module must not load any concrete world (Invariant 4).

    ``vcli.cli`` is the *acceptance-face* module — the bare ``vector-cli`` REPL is
    built from it. Guarding the engine alone is not enough: the property that
    matters operationally is that importing the thing the user actually launches
    stays world-free (worlds load only when one is resolved for a session).
    """
    leaked = _concrete_worlds_loaded_by_importing(
        "vector_os_nano.vcli.cli", _CONCRETE_WORLD_MARKERS
    )
    assert leaked == [], (
        "importing the CLI entry module eagerly loaded concrete world module(s) "
        f"{leaked!r}; the acceptance-face entry point must stay world-free until a "
        "world is resolved (Invariant 4)"
    )


def test_no_domain_world_leaks_from_the_worlds_seam() -> None:
    """Importing the worlds SEAM (base/registry) must not drag in a domain world.

    Importing ``worlds.registry`` (the discovery seam) must be resolvable
    without loading the playground or any other domain/BYO world. The two kernel
    worlds (dev/robot) are permitted to load lazily on USE, but not the domain
    packages — that is what keeps a third-party world truly optional.
    """
    leaked = _concrete_worlds_loaded_by_importing(
        "vector_os_nano.vcli.worlds.registry", ("playground",)
    )
    assert leaked == [], (
        f"importing the world registry seam leaked domain world(s) {leaked!r}"
    )


# ---------------------------------------------------------------------------
# Invariant 3 — a bring-your-own world plugs in with ZERO kernel edits
# ---------------------------------------------------------------------------


class _AcmeArmWorld:
    """A synthetic third-party world, defined ENTIRELY in this test file.

    It implements the ``World`` Protocol structurally (duck-typed) — nothing in
    the kernel package is edited or subclassed. If the kernel seam can register,
    resolve and drive it, then adding a world is genuinely config/code that
    lives OUTSIDE the kernel (the plug-and-play promise).
    """

    name = "byo:acme-arm"

    def __init__(self) -> None:
        # Records what the world contributed, so the test can assert the seam
        # actually invoked each contribution point.
        self.tools_registered: list[str] = []
        self.capabilities_registered: list[str] = []

    def is_robot(self) -> bool:
        return True

    def persona_blocks(self) -> tuple[str, str]:
        return ("You operate the ACME arm.", "Call acme_grip to close the gripper.")

    def register_tools(self, registry: Any, agent: Any) -> None:
        registry.register(SimpleNamespace(name="acme_grip"), category="acme")
        self.tools_registered.append("acme_grip")

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        # A world contributes its own ground-truth predicates; here a trivial
        # deterministic one the actor cannot author around.
        return {"acme_is_gripping": lambda: agent.gripping}

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        registry.register(SimpleNamespace(name="acme_grasp_policy"))
        self.capabilities_registered.append("acme_grasp_policy")

    def decompose_vocab(self) -> DecomposeVocab | None:
        return DecomposeVocab(
            planner_intro="Drive the ACME arm.",
            verify_functions=frozenset({"acme_is_gripping"}),
        )

    def derive_vocab_from_registry(self) -> bool:
        return False


def test_byo_world_satisfies_the_world_protocol() -> None:
    """The synthetic world is a structural ``World`` — no kernel subclass needed."""
    world = _AcmeArmWorld()
    assert isinstance(world, World), (
        "a third-party world implementing the documented method set must satisfy "
        "the runtime-checkable World Protocol without importing/subclassing kernel code"
    )


def test_byo_world_registers_and_resolves_by_name() -> None:
    """A BYO world registers a factory and resolves by id through the kernel seam."""
    reg = WorldRegistry()  # isolated instance — does not touch the process default
    reg.register("byo:acme-arm", _AcmeArmWorld)

    assert "byo:acme-arm" in reg.names()
    world = reg.resolve("byo:acme-arm")
    assert world.name == "byo:acme-arm"
    assert world.is_robot() is True
    # Fresh instance per resolution (factory semantics), like the kernel worlds.
    assert reg.resolve("byo:acme-arm") is not world


def test_byo_world_is_driven_through_every_contribution_point() -> None:
    """Exercise the full World contract against plain fakes — no kernel edits.

    Registering tools/capabilities, building the verify namespace, the persona
    and the decompose vocab are the five seams a world plugs into. Driving them
    with fakes proves the kernel can operate a world it has never heard of.
    """
    world = _AcmeArmWorld()
    tool_registry = SimpleNamespace(
        _tools=[], register=lambda tool, category="default": tool_registry._tools.append((category, tool.name))
    )
    cap_registry = SimpleNamespace(
        _caps=[], register=lambda cap: cap_registry._caps.append(cap.name)
    )
    agent = SimpleNamespace(gripping=True)

    role, tools = world.persona_blocks()
    assert "ACME" in role and "acme_grip" in tools

    world.register_tools(tool_registry, agent)
    assert ("acme", "acme_grip") in tool_registry._tools

    ns = world.build_verify_namespace(agent)
    assert "acme_is_gripping" in ns and ns["acme_is_gripping"]() is True

    world.register_capabilities(cap_registry, agent, backend=object())
    assert "acme_grasp_policy" in cap_registry._caps

    vocab = world.decompose_vocab()
    assert vocab is not None
    assert "acme_is_gripping" in vocab.verify_functions
    # The vocab converts to GoalDecomposer kwargs without the kernel importing it.
    assert "verify_functions" in vocab.as_kwargs()

    assert world.derive_vocab_from_registry() is False


# ---------------------------------------------------------------------------
# Invariant 3 — the shipped BYO-world EXAMPLE stays runnable (no bit-rot)
# ---------------------------------------------------------------------------


def test_byo_world_example_runs_clean() -> None:
    """``examples/byo_world.py`` runs end-to-end with ZERO kernel edits, no LLM.

    The example is the user-facing demonstration of the plug-and-play promise: a
    world defined entirely outside the kernel registers, resolves and is driven
    through every seam. Running it here (in a fresh subprocess, no simulator, no
    API key) keeps that artifact honest — if a kernel change breaks the public
    seam the example uses, this goes RED instead of the example silently rotting.
    """
    example = _REPO_ROOT / "examples" / "byo_world.py"
    assert example.is_file(), f"missing BYO-world example at {example}"
    result = subprocess.run(
        [sys.executable, str(example)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(_REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
    )
    assert result.returncode == 0, (
        f"BYO-world example exited {result.returncode}:\n{result.stderr}"
    )
    assert "ZERO kernel edits" in result.stdout, (
        f"example did not print its proof line; stdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# Invariant 1 (moat) × plug-and-play Verify — a BYO predicate is not merely
# PRESENT in the namespace, it is truth-bearingly GRADED by the frozen
# classifier, WITH ZERO KERNEL EDITS. The boundary tests above prove the
# world seam REGISTERS a custom predicate; this proves the verify spine
# ADJUDICATES it — and pins exactly which authoring idioms ground, so a
# contributor is never silently stuck on a RAN verdict.
# ---------------------------------------------------------------------------


def _byo_oracle_names() -> "frozenset[str]":
    """The live verify-namespace names a BYO world contributes.

    Single-sourced from the world's OWN ``build_verify_namespace`` (rule 3 — the
    classifier must grade the exact name the world contributed, never a second
    hand-authored copy). ``_AcmeArmWorld`` contributes ``acme_is_gripping``; we
    add a sibling STATE oracle name to exercise the state-vs-constant idiom.
    """
    world = _AcmeArmWorld()
    contributed = set(world.build_verify_namespace(SimpleNamespace(gripping=True)))
    assert "acme_is_gripping" in contributed
    return frozenset(contributed | {"acme_gripper_pos"})


def test_byo_predicate_is_graded_by_the_frozen_classifier_zero_kernel_edits() -> None:
    """A BYO world's custom verify predicate GROUNDS through the spine classifier.

    The North Star Verify contract is not "the predicate is in a dict" (the
    boundary tests above) but "the predicate GRADES a goal". ``classify_verify_expr``
    is the frozen spine that decides whether a verify expression is truth-bearing
    over a world oracle. Feeding it the BYO namespace names — nothing hardcoded
    into ``_PREDICATE_ORACLES`` — two idioms ground with ZERO kernel edits:

    * a STATE oracle anchored to a constant (``acme_gripper_pos() == 1``), and
    * a bare-boolean predicate made goal-explicit (``acme_is_gripping() == True``).

    Both consume the world's ground truth (which the actor cannot author), so a
    third party's Verify contribution is genuinely load-bearing, not decorative.
    """
    from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr

    live = _byo_oracle_names()
    assert classify_verify_expr("acme_gripper_pos() == 1", live) == "GROUNDED"
    assert classify_verify_expr("acme_is_gripping() == True", live) == "GROUNDED"


def test_byo_bare_predicate_idiom_is_the_zero_edit_boundary() -> None:
    """PIN the boundary: the BARE ``pred()`` idiom does NOT ground for a BYO name.

    Bare-call grounding is reserved for the first-party ``_PREDICATE_ORACLES`` set
    (a deliberate moat: only names KNOWN to be goal-conditioned booleans may ground
    as a bare call — a bare STATE oracle such as ``get_position()`` must never count
    as evidence). A BYO name is not in that hardcoded set, so ``acme_is_gripping()``
    written bare classifies RAN — which is exactly why landing a first-party bare
    predicate (e.g. the go2 quartet, G-323-1) requires the ``_PREDICATE_ORACLES``
    edit, while a BYO contributor stays zero-edit by writing ``pred() == True``.

    This is a CHARACTERIZATION guard, not a wish: if a refactor ever grounds a bare
    BYO call, the moat semantics changed under us and this goes RED first.
    """
    from vector_os_nano.vcli.cognitive.evidence_classifier import (
        _PREDICATE_ORACLES,
        classify_verify_expr,
    )

    live = _byo_oracle_names()
    assert "acme_is_gripping" not in _PREDICATE_ORACLES  # not a first-party predicate
    assert classify_verify_expr("acme_is_gripping()", live) == "RAN"


def test_byo_predicate_grounding_preserves_the_moat() -> None:
    """The plug-and-play seam does NOT loosen the moat for a BYO predicate.

    Every short-circuit / self-tautology hole the classifier closes for first-party
    predicates must stay closed for a BYO one — otherwise "bring a verify-predicate"
    would be a way to smuggle in a self-certifying grade (Invariant 1). Also: a name
    the world never contributed cannot ground even in the grounding idioms.
    """
    from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr

    live = _byo_oracle_names()
    # short-circuit: an oracle OR'd with a truthy constant is not gated by the oracle
    assert classify_verify_expr("acme_is_gripping() == True or True", live) == "RAN"
    # self-tautology: oracle compared against itself proves no goal
    assert (
        classify_verify_expr("acme_is_gripping() == acme_is_gripping()", live) == "RAN"
    )
    # a name absent from the live namespace cannot ground, even as pred() == True
    assert classify_verify_expr("not_contributed() == True", frozenset()) == "RAN"
