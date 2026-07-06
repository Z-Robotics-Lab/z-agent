# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Executable drift-guard for Invariant 7 over the VERDICT CONTRACT dataclasses.

``verdict.py`` defines the JSON-serialized verdict the acceptance face emits and
the ledger records (``VerdictReport`` + its per-step ``StepVerdict``). Invariant 7
requires these frozen dataclasses to STAY frozen and change only additively — an
accidental ``frozen=True`` drop (or a NEW verdict dataclass added un-frozen) would
silently make the verdict contract mutable, letting a caller rewrite a graded
verdict after the fact. Unlike the four cognitive types (guarded in
test_level41) and the embodiment config (guarded in test_embodiment_config), the
verdict contract had NO frozen assertion — this closes that gap.

The guard binds real ground truth: it introspects every dataclass DEFINED in the
verdict module (``__dataclass_params__`` + a live ``FrozenInstanceError``), so it
fires on a regression to ANY current or future verdict dataclass, not a hardcoded
list. Offline, LLM-free — the import graph and dataclass metadata are not
something the actor can author around.
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from zeno.vcli import verdict as verdict_mod
from zeno.vcli.verdict import StepVerdict, VerdictReport


def _verdict_module_dataclasses() -> list[type]:
    """Every dataclass DEFINED in the verdict module (not merely imported)."""
    return [
        obj
        for _, obj in inspect.getmembers(verdict_mod, inspect.isclass)
        if dataclasses.is_dataclass(obj) and obj.__module__ == verdict_mod.__name__
    ]


def test_verdict_module_defines_the_expected_contract_dataclasses() -> None:
    """Sanity: the introspection actually finds the contract types it guards.

    Without this, a rename that removed ``VerdictReport`` from the module would
    make the parametrized guard below vacuously pass over an empty set.
    """
    found = {cls.__name__ for cls in _verdict_module_dataclasses()}
    assert {"VerdictReport", "StepVerdict"} <= found, (
        f"verdict module no longer defines the expected contract dataclasses; found {found!r}"
    )


@pytest.mark.parametrize(
    "cls", _verdict_module_dataclasses(), ids=lambda c: c.__name__
)
def test_every_verdict_dataclass_is_frozen(cls: type) -> None:
    """Invariant 7: every verdict-contract dataclass declares ``frozen=True``.

    A NEW verdict dataclass added without ``frozen=True`` — or a frozen drop on an
    existing one — goes RED here before the mutable contract can ship.
    """
    assert cls.__dataclass_params__.frozen is True, (
        f"{cls.__name__} in verdict.py is not frozen; the verdict contract must be "
        "immutable (Invariant 7 — frozen dataclasses change additively)"
    )


def test_verdict_report_instance_rejects_mutation() -> None:
    """A live ``VerdictReport`` raises on attribute assignment (behavioral proof)."""
    report = VerdictReport.no_trace(goal="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.verified = True  # type: ignore[misc]


def test_step_verdict_instance_rejects_mutation() -> None:
    """A live ``StepVerdict`` raises on attribute assignment (behavioral proof)."""
    sv = StepVerdict(
        name="s1",
        strategy="nav",
        success=True,
        verify="at_position() == True",
        verify_result=True,
        evidence="GROUNDED",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        sv.evidence = "FAILED"  # type: ignore[misc]
