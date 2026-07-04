# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Executable drift-guard for Invariant 7 over the EMBODIMENT-CONFIG schema.

``embodiments/config.py`` is the plug-and-play morphology loader: it parses each
robot's ``robot.yaml`` into a tree of frozen dataclasses so the generic Stage-2
driver can stand a body up FROM DATA ALONE (Invariant 3 — embodiments are config,
not code). Those dataclasses are the literal "config not code" surface a
third-party robot author's manifest flows into; Invariant 7 requires them to evolve
additively-immutable so one loaded morphology can never be mutated into another at
runtime (e.g. a code path flipping ``CapabilityProfile.has_gripper`` mid-run and
corrupting tool routing, or rewriting a ``SensorSpec`` mount and defeating the
manifest↔driver fidelity mirror).

The existing ``test_go2_loads_and_is_frozen`` only proves the TOP-LEVEL
``EmbodimentConfig`` rejects one assignment; the six nested specs (ModelSpec,
SpawnSpec, SensorSpec, PolicySpec, GraspSpec, CapabilityProfile) had NO frozen
guard — drop ``frozen=True`` from any of them and CI stayed green. This closes that
gap the same way the SPINE frozen contracts are guarded (verdict / acceptance /
cognitive-types / actor_causation): by introspecting EVERY dataclass DEFINED in the
module (``__dataclass_params__`` + a live ``FrozenInstanceError``), so it fires on a
regression to ANY current OR future config dataclass, not a hardcoded list. Offline,
LLM-free — dataclass metadata is not something a world/manifest author can author
around.
"""
from __future__ import annotations

import dataclasses
import inspect

import pytest

from vector_os_nano.embodiments import config as cfg_mod
from vector_os_nano.embodiments.config import load_embodiment_config


def _module_dataclasses() -> list[type]:
    """Every dataclass DEFINED in the config module (not merely imported)."""
    return [
        obj
        for _, obj in inspect.getmembers(cfg_mod, inspect.isclass)
        if dataclasses.is_dataclass(obj) and obj.__module__ == cfg_mod.__name__
    ]


def test_module_defines_the_expected_schema_contract() -> None:
    """Sanity: the introspection actually finds the schema it guards.

    Without this, a rename that removed the specs from the module would make the
    parametrized guard below vacuously pass over an empty (or shrunken) set.
    """
    found = {cls.__name__ for cls in _module_dataclasses()}
    expected = {
        "ModelSpec",
        "SpawnSpec",
        "SensorSpec",
        "PolicySpec",
        "GraspSpec",
        "CapabilityProfile",
        "EmbodimentConfig",
    }
    missing = expected - found
    assert not missing, (
        f"embodiments.config no longer defines schema dataclasses {missing!r}; "
        f"found {found!r}. If a spec was intentionally renamed, update this set."
    )


@pytest.mark.parametrize("cls", _module_dataclasses(), ids=lambda c: c.__name__)
def test_every_config_dataclass_is_frozen(cls: type) -> None:
    """Invariant 7: every embodiment-config dataclass declares ``frozen=True``.

    A NEW config dataclass added without ``frozen=True`` — or a frozen drop on an
    existing spec — goes RED here before a mutable morphology can ship.
    """
    params = getattr(cls, "__dataclass_params__", None)
    assert params is not None and params.frozen, (
        f"{cls.__name__} in the embodiment-config schema is not frozen "
        "(Invariant 7): a mutable morphology spec lets a code path rewrite one "
        "loaded robot's config (capability flags, sensor mounts, spawn pose) at "
        "runtime — config-not-code drift (Invariant 3)."
    )


def test_loaded_nested_specs_reject_mutation_at_runtime() -> None:
    """Live proof the freeze holds on the NESTED specs of a real loaded config.

    The existing suite only mutates ``cfg.id``; here we prove the nested
    ``SpawnSpec`` and ``CapabilityProfile`` instances that come out of a real
    ``robot.yaml`` load are frozen too — catching a freeze that is declared but
    defeated (e.g. a stray ``__setattr__`` override on a nested spec).
    """
    cfg = load_embodiment_config("go2")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.spawn.base_height = 99.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.capabilities.has_gripper = True  # type: ignore[misc]
