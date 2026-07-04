# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Executable drift-guard for Invariant 7 over the CAUSATION-BASELINE contract.

``actor_causation.py`` is an enumerated honest-verify SPINE path (loop/check.sh
``SPINE``). Its ``ActorBaseline`` is a FROZEN snapshot of the actor's
commanded-motion counters + pose, captured BEFORE a step runs and compared with a
fresh capture AFTER the step to grade causation (fix 5 — the staleness trap). The
whole point of the snapshot is that "advancing the live robot after capture cannot
mutate the baseline": it is ground truth the actor is NOT allowed to author.

If ``frozen=True`` were dropped from ``ActorBaseline`` — or a NEW causation
dataclass added to this spine module without it — the baseline snapshot would
become mutable and an actor code path could rewrite the captured pose/counters
after the fact, silently defeating the causation grade (an Inv-1 breach). The
verdict contract (test_verdict_frozen), the acceptance verdict/decision contract
(test_acceptance_verdict_frozen) and the four cognitive types (test_level41) all
had introspection frozen-guards; this spine module — the causation baseline that
the other guards' verdicts DEPEND on — had none. This closes that gap.

The guard binds real ground truth: it introspects every dataclass DEFINED in the
actor_causation module (``__dataclass_params__`` + a live ``FrozenInstanceError``),
so it fires on a regression to ANY current or future causation dataclass, not a
hardcoded list. Offline, LLM-free — the import graph and dataclass metadata are
not something the actor can author around.
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from vector_os_nano.vcli.cognitive import actor_causation as ac_mod
from vector_os_nano.vcli.cognitive.actor_causation import ActorBaseline


def _module_dataclasses() -> list[type]:
    """Every dataclass DEFINED in the actor_causation module (not merely imported)."""
    return [
        obj
        for _, obj in inspect.getmembers(ac_mod, inspect.isclass)
        if dataclasses.is_dataclass(obj) and obj.__module__ == ac_mod.__name__
    ]


def test_module_defines_the_expected_baseline_contract() -> None:
    """Sanity: the introspection actually finds the type it guards.

    Without this, a rename that removed ``ActorBaseline`` from the module would
    make the parametrized guard below vacuously pass over an empty set.
    """
    found = {cls.__name__ for cls in _module_dataclasses()}
    assert "ActorBaseline" in found, (
        f"actor_causation no longer defines the ActorBaseline contract; found {found!r}"
    )


@pytest.mark.parametrize(
    "cls", _module_dataclasses(), ids=lambda c: c.__name__
)
def test_every_causation_dataclass_is_frozen(cls: type) -> None:
    """Invariant 7: every causation-contract dataclass declares ``frozen=True``.

    A NEW causation dataclass added without ``frozen=True`` — or a frozen drop on
    an existing one — goes RED here before the mutable snapshot can ship.
    """
    params = getattr(cls, "__dataclass_params__", None)
    assert params is not None and params.frozen, (
        f"{cls.__name__} in the causation-baseline spine module is not frozen "
        "(Invariant 7): a mutable snapshot lets an actor rewrite the causation "
        "baseline after capture."
    )


def test_actor_baseline_rejects_mutation_at_runtime() -> None:
    """Live proof the freeze holds — construct a baseline and try to mutate it.

    All fields default to ``None`` so the snapshot builds with no args; assigning
    to a field must raise ``FrozenInstanceError``. This catches a freeze that is
    declared but defeated (e.g. a stray ``__setattr__`` override).
    """
    baseline = ActorBaseline()
    with pytest.raises(dataclasses.FrozenInstanceError):
        baseline.base_pos = (1.0, 2.0, 3.0)  # type: ignore[misc]
