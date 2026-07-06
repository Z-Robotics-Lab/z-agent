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

from zeno.vcli.worlds import DecomposeVocab, World
from zeno.vcli.worlds.registry import WorldRegistry

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
import zeno.vcli.engine  # the domain-general kernel
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
    probe = _LEAK_PROBE.replace("zeno.vcli.engine", module).format(markers=markers)
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
        "zeno.vcli.engine", _CONCRETE_WORLD_MARKERS
    )
    assert leaked == [], (
        "importing the kernel engine eagerly loaded concrete world module(s) "
        f"{leaked!r}; worlds must load only on resolution (Invariant 4 — the "
        "kernel never imports a world at module load)"
    )


def test_cli_entry_import_leaks_no_concrete_world() -> None:
    """Importing the CLI entry module must not load any concrete world (Invariant 4).

    ``vcli.cli`` is the *acceptance-face* module — the bare ``zeno`` REPL is
    built from it. Guarding the engine alone is not enough: the property that
    matters operationally is that importing the thing the user actually launches
    stays world-free (worlds load only when one is resolved for a session).
    """
    leaked = _concrete_worlds_loaded_by_importing(
        "zeno.vcli.cli", _CONCRETE_WORLD_MARKERS
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
        "zeno.vcli.worlds.registry", ("playground",)
    )
    assert leaked == [], (
        f"importing the world registry seam leaked domain world(s) {leaked!r}"
    )


# ---------------------------------------------------------------------------
# Invariant 4 — ALLOWLIST guard (denylist ``_CONCRETE_WORLD_MARKERS`` is
# stale-prone: a brand-new ``worlds/<newthing>.py`` concrete world escapes it
# silently, exactly the hardcoded-list failure mode fixed for the verdict
# contracts in E152/E153). The robust complement flips the polarity: importing
# the kernel/CLI must leak NOTHING under ``vcli.worlds.*`` except the explicit
# SEAM allowlist. Any future concrete world/oracle that leaks goes RED with no
# marker edit required. Ground truth = the import graph the actor cannot author;
# strictly STRICTER than the denylist (Invariant 1 — the moat only tightens).
# ---------------------------------------------------------------------------

# The ONLY ``vcli.worlds`` modules the kernel/CLI may eagerly load: the package
# itself (a PEP 562 lazy ``__getattr__`` shim — no concrete world at load) and
# the two seam modules (base = the World Protocol, registry = discovery). Every
# other ``vcli.worlds.*`` module is a concrete world or an embodiment oracle and
# must load ONLY on resolution.
_WORLDS_SEAM_ALLOWLIST = frozenset(
    {
        "zeno.vcli.worlds",
        "zeno.vcli.worlds.base",
        "zeno.vcli.worlds.registry",
    }
)

_WORLDS_SUBMODULE_PROBE = r"""
import sys
import {module}
loaded = sorted(
    m for m in sys.modules
    if m == "zeno.vcli.worlds"
    or m.startswith("zeno.vcli.worlds.")
)
print("\n".join(loaded))
"""


def _worlds_modules_loaded_by_importing(module: str) -> list[str]:
    """Every ``vcli.worlds*`` module present after importing *module* clean.

    Fresh interpreter, so the answer reflects a pristine ``sys.modules`` rather
    than whatever the pytest session already imported.
    """
    probe = _WORLDS_SUBMODULE_PROBE.format(module=module)
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


def _worlds_leak_outside_seam(module: str) -> tuple[list[str], list[str]]:
    """Return ``(all_loaded, outside_seam)`` for a clean import of *module*."""
    loaded = _worlds_modules_loaded_by_importing(module)
    outside = [m for m in loaded if m not in _WORLDS_SEAM_ALLOWLIST]
    return loaded, outside


def test_kernel_import_leaks_no_worlds_module_outside_the_seam() -> None:
    """Kernel import loads ONLY the seam — auto-covers future worlds (Invariant 4).

    Unlike the denylist above, this catches a concrete world with ANY name (a new
    ``worlds/mars_rover.py`` or a new ``*_oracle.py``) without editing a marker
    list — the guard tracks the actual package, not a memorised enumeration.
    """
    loaded, outside = _worlds_leak_outside_seam("zeno.vcli.engine")
    # Anti-vacuous: the seam MUST have loaded (proves the probe ran and the
    # import graph was actually walked — an empty result is only meaningful when
    # we know imports happened).
    assert loaded, "probe loaded no vcli.worlds module at all — import likely failed"
    assert outside == [], (
        "importing the kernel engine eagerly loaded a NON-seam vcli.worlds "
        f"module {outside!r}; only the seam {sorted(_WORLDS_SEAM_ALLOWLIST)} may "
        "load at kernel import — concrete worlds/oracles load on resolution "
        "(Invariant 4, allowlist guard)"
    )


def test_cli_entry_import_leaks_no_worlds_module_outside_the_seam() -> None:
    """The acceptance-face CLI entry loads ONLY the seam (Invariant 4, allowlist)."""
    loaded, outside = _worlds_leak_outside_seam("zeno.vcli.cli")
    assert loaded, "probe loaded no vcli.worlds module at all — import likely failed"
    assert outside == [], (
        "importing the CLI entry module eagerly loaded a NON-seam vcli.worlds "
        f"module {outside!r}; the acceptance-face entry point must stay world-free "
        "until a world is resolved (Invariant 4, allowlist guard)"
    )


def test_allowlist_guard_fires_on_a_real_concrete_world_leak() -> None:
    """DISCRIM (live, no mock): importing a real concrete world DOES trip the guard.

    Proves the allowlist assertion is not vacuously green. ``worlds.dev`` is a
    genuine concrete world; importing it must surface a non-seam module — so a
    real kernel-side leak of any concrete world would be caught identically.
    """
    loaded, outside = _worlds_leak_outside_seam("zeno.vcli.worlds.dev")
    assert "zeno.vcli.worlds.dev" in loaded
    assert "zeno.vcli.worlds.dev" in outside, (
        "the allowlist filter failed to flag a genuinely-leaked concrete world — "
        "the guard would be vacuous"
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
    from zeno.vcli.cognitive.evidence_classifier import classify_verify_expr

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
    from zeno.vcli.cognitive.evidence_classifier import (
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
    from zeno.vcli.cognitive.evidence_classifier import classify_verify_expr

    live = _byo_oracle_names()
    # short-circuit: an oracle OR'd with a truthy constant is not gated by the oracle
    assert classify_verify_expr("acme_is_gripping() == True or True", live) == "RAN"
    # self-tautology: oracle compared against itself proves no goal
    assert (
        classify_verify_expr("acme_is_gripping() == acme_is_gripping()", live) == "RAN"
    )
    # a name absent from the live namespace cannot ground, even as pred() == True
    assert classify_verify_expr("not_contributed() == True", frozenset()) == "RAN"


# ---------------------------------------------------------------------------
# Invariant 1 (moat) × plug-and-play Verify — the RUNTIME DELIVERY seam.
# The tests above prove the frozen CLASSIFIER grades a BYO expr, but they feed
# it a hand-built oracle set (``_byo_oracle_names``). That a BYO world's
# predicate actually REACHES that classifier through the REAL engine namespace
# builder — ``verify_oracle_names`` -> ``engine._build_verifier_namespace`` ->
# ``_merge_world_verify_namespace`` -> ``world.build_verify_namespace`` — and
# then clears the DONE-GATE (``evidence_passed``) was, until here, asserted only
# by reading the code. These exercise the whole path end-to-end, offline and
# LLM-free, with a BYO world wired into a REAL engine and ZERO kernel edits: the
# North Star's "bring a verify-predicate" claim proven at the RUNTIME level, not
# just the classifier level. The ground truth (the import/merge graph and the
# frozen done-gate) is not something the actor can author.
# ---------------------------------------------------------------------------


def _byo_agent(gripping: bool = True) -> SimpleNamespace:
    """A plain fake agent the BYO world's predicate reads its ground truth from.

    ``_base``/``_spatial_memory`` are None so ``_build_verifier_namespace`` adds
    only its domain-general dev stubs before merging the world contribution — the
    BYO predicate is the only robot-flavoured oracle in the namespace, which is
    exactly the isolation this proof wants.
    """
    return SimpleNamespace(gripping=gripping, _base=None, _spatial_memory=None)


def _engine_with_byo_world(world: Any) -> Any:
    """A REAL engine with a BYO world wired in exactly as a resolved session does.

    ``VectorEngine.__init__`` only stores its backend (never calls it during
    namespace construction), so a trivial fake backend keeps this offline and
    LLM-free while ``_build_verifier_namespace`` / ``_merge_world_verify_namespace``
    run the genuine kernel code.
    """
    from zeno.vcli.engine import VectorEngine

    engine = VectorEngine(backend=SimpleNamespace())
    engine._world = world  # the one line a resolved session wires; no kernel edit
    return engine


def test_byo_predicate_reaches_oracle_names_through_the_real_engine_seam() -> None:
    """The REAL ``verify_oracle_names`` surfaces a BYO world's predicate name.

    Not the hand-built ``_byo_oracle_names`` set the classifier tests use — this
    drives ``verify_oracle_names(agent, engine)`` against a real engine whose
    ``_world`` is the synthetic BYO world, so the name only reaches the oracle set
    if ``_merge_world_verify_namespace`` actually merges ``build_verify_namespace``
    (engine.py). If that merge regressed, the name would be missing and this goes
    RED — closing the "asserted by code-reading" gap E116 left.
    """
    from zeno.vcli.cognitive.trace_store import verify_oracle_names

    engine = _engine_with_byo_world(_AcmeArmWorld())
    names = verify_oracle_names(_byo_agent(), engine)
    assert "acme_is_gripping" in names, (
        "the BYO world's build_verify_namespace name did not survive the real "
        "engine namespace builder; the plug-and-play verify delivery seam regressed"
    )


def test_byo_predicate_passes_the_done_gate_end_to_end_zero_kernel_edit() -> None:
    """A BYO predicate clears ``evidence_passed`` through the real runtime path.

    Full chain, no kernel edit: real engine namespace -> real
    ``verify_oracle_names`` -> real ``classify_step_evidence`` (GROUNDED) -> real
    ``evidence_passed`` (True). This is the North Star claim ("bring a
    verify-predicate") proven at the DONE-GATE, one level above E116's classifier.
    """
    from zeno.vcli.cognitive.trace_store import (
        classify_step_evidence,
        evidence_passed,
        verify_oracle_names,
    )
    from zeno.vcli.cognitive.types import (
        ExecutionTrace,
        GoalTree,
        StepRecord,
        SubGoal,
    )

    engine = _engine_with_byo_world(_AcmeArmWorld())
    oracle_names = verify_oracle_names(_byo_agent(gripping=True), engine)

    sg = SubGoal(
        name="s1", description="close the acme gripper",
        verify="acme_is_gripping() == True", strategy="acme_grip",
    )
    step = StepRecord(
        sub_goal_name="s1", strategy="acme_grip",
        success=True, verify_result=True, duration_sec=0.1,
    )
    tree = GoalTree(goal="close the acme gripper", sub_goals=(sg,))
    trace = ExecutionTrace(
        goal_tree=tree, steps=(step,), success=True, total_duration_sec=0.1,
    )

    assert classify_step_evidence(step, sg, oracle_names) == "GROUNDED"
    assert evidence_passed(trace, oracle_names) is True


def test_byo_predicate_done_gate_moat_holds_under_actor_causation() -> None:
    """The done-gate's actor-causation downgrade governs a BYO predicate too.

    The strongest moat probe: a step whose BYO verify would otherwise GROUND
    (``verify_result`` True, oracle consumed) but whose actor did NOT cause the
    state change (``ActorCaused.UNCAUSED`` — a satisfied-at-baseline no-op) must
    DOWNGRADE to RAN and FAIL ``evidence_passed``. If "bring a verify-predicate"
    let a satisfied-at-baseline state pass, it would be a self-certifying grade
    (Invariant 1). Non-tautological: ``verify_result`` stays True — only causation
    changes the verdict.
    """
    from zeno.vcli.cognitive.actor_causation import ActorCaused
    from zeno.vcli.cognitive.trace_store import (
        classify_step_evidence,
        evidence_passed,
        verify_oracle_names,
    )
    from zeno.vcli.cognitive.types import (
        ExecutionTrace,
        GoalTree,
        StepRecord,
        SubGoal,
    )

    engine = _engine_with_byo_world(_AcmeArmWorld())
    oracle_names = verify_oracle_names(_byo_agent(gripping=True), engine)

    sg = SubGoal(
        name="s1", description="close the acme gripper",
        verify="acme_is_gripping() == True", strategy="acme_grip",
    )
    step = StepRecord(
        sub_goal_name="s1", strategy="acme_grip",
        success=True, verify_result=True, duration_sec=0.1,
        actor_caused=ActorCaused.UNCAUSED,
    )
    tree = GoalTree(goal="close the acme gripper", sub_goals=(sg,))
    trace = ExecutionTrace(
        goal_tree=tree, steps=(step,), success=True, total_duration_sec=0.1,
    )

    assert classify_step_evidence(step, sg, oracle_names) == "RAN"
    assert evidence_passed(trace, oracle_names) is False


def test_byo_predicate_delivery_fails_closed_without_an_engine() -> None:
    """No engine -> no namespace -> the BYO predicate cannot ground (moat stricter).

    ``verify_oracle_names(agent, None)`` fails closed to ``frozenset()`` (rule 5),
    so even the grounding idiom ``pred() == True`` classifies RAN. The delivery
    seam can only ever make verification STRICTER when the namespace is absent —
    never a spurious pass.
    """
    from zeno.vcli.cognitive.evidence_classifier import classify_verify_expr
    from zeno.vcli.cognitive.trace_store import verify_oracle_names

    names = verify_oracle_names(_byo_agent(), None)
    assert names == frozenset()
    assert classify_verify_expr("acme_is_gripping() == True", names) == "RAN"
