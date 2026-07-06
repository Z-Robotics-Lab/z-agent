# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Executable drift-guard for Invariant 7 over the ACCEPTANCE-FACE verdict contract.

Invariant 1 ("Verify is the moat") makes the acceptance package the most
load-bearing verdict surface in the repo: ``gate.decide`` returns the final
``AcceptanceDecision`` (the ADR-002 GT-vs-vision bridge result), ``motion_check``
returns the ``MotionVerdict`` (hard pose-track authority), and ``vision_judge``
returns the ``VisionVerdict`` (the soft witness). All three are frozen dataclasses
and Invariant 7 requires them to STAY frozen and change only additively — an
accidental ``frozen=True`` drop (or a NEW verdict dataclass added un-frozen) would
silently let a caller rewrite a graded acceptance verdict after the fact.

Last round (E152) closed the same gap for ``vcli/verdict.py``; the acceptance
package's OWN verdict/decision contract had NO frozen assertion (test_acceptance_gate
/ test_motion_check / test_vision_judge cover behaviour, not immutability). This
closes that sibling gap — the verify MOAT's verdict types.

The guard binds real ground truth: it introspects every dataclass DEFINED in each
acceptance verdict module (``__dataclass_params__`` + a live ``FrozenInstanceError``),
so it fires on a regression to ANY current or future verdict dataclass, not a
hardcoded list. Offline, LLM-free — the import graph and dataclass metadata are not
something the actor can author around.
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from zeno.acceptance import gate as gate_mod
from zeno.acceptance import motion_check as motion_mod
from zeno.acceptance import vision_judge as vision_mod
from zeno.acceptance.gate import AcceptanceDecision
from zeno.acceptance.motion_check import MotionVerdict
from zeno.acceptance.vision_judge import VisionVerdict

# The modules whose graded verdict/decision dataclasses form the acceptance-face contract.
_VERDICT_MODULES = (gate_mod, motion_mod, vision_mod)


def _module_dataclasses(module) -> list[type]:
    """Every dataclass DEFINED in ``module`` (not merely imported)."""
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if dataclasses.is_dataclass(obj) and obj.__module__ == module.__name__
    ]


def _acceptance_verdict_dataclasses() -> list[type]:
    return [cls for mod in _VERDICT_MODULES for cls in _module_dataclasses(mod)]


def test_acceptance_modules_define_the_expected_verdict_dataclasses() -> None:
    """Sanity: the introspection actually finds the contract types it guards.

    Without this, a rename that removed ``AcceptanceDecision`` from ``gate`` would
    make the parametrized guard below vacuously pass over a shrunken set.
    """
    found = {cls.__name__ for cls in _acceptance_verdict_dataclasses()}
    assert {"AcceptanceDecision", "MotionVerdict", "VisionVerdict"} <= found, (
        f"acceptance verdict modules no longer define the expected contract "
        f"dataclasses; found {found!r}"
    )


@pytest.mark.parametrize(
    "cls", _acceptance_verdict_dataclasses(), ids=lambda c: c.__name__
)
def test_every_acceptance_verdict_dataclass_is_frozen(cls: type) -> None:
    """Invariant 7: every acceptance verdict/decision dataclass declares ``frozen=True``.

    A NEW verdict dataclass added without ``frozen=True`` — or a frozen drop on an
    existing one — goes RED here before the mutable verdict contract can ship.
    """
    assert cls.__dataclass_params__.frozen is True, (
        f"{cls.__name__} in the acceptance package is not frozen; the verify-moat "
        "verdict contract must be immutable (Invariant 7 — frozen dataclasses "
        "change additively)"
    )


def test_acceptance_decision_instance_rejects_mutation() -> None:
    """A live ``AcceptanceDecision`` raises on attribute assignment (behavioral proof)."""
    decision = gate_mod.decide(gt_verified=True, vision_witness="PASS")
    assert isinstance(decision, AcceptanceDecision)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.decision = "REJECT"  # type: ignore[misc]


def test_motion_verdict_instance_rejects_mutation() -> None:
    """A live ``MotionVerdict`` raises on attribute assignment (behavioral proof)."""
    verdict = MotionVerdict(
        moved_m=1.0,
        path_m=1.2,
        hard_moved=True,
        vision_witness="PASS",
        agree=True,
        disagreement=False,
        note="ok",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.hard_moved = False  # type: ignore[misc]


def test_vision_verdict_instance_rejects_mutation() -> None:
    """A live ``VisionVerdict`` raises on attribute assignment (behavioral proof)."""
    verdict = VisionVerdict(
        witness="PASS",
        per_item=(),
        reasoning="scene rendered; robot upright",
        model="test",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        verdict.witness = "FAIL"  # type: ignore[misc]
