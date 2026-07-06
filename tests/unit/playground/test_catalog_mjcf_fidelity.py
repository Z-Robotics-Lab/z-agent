# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Drift guard: every playground scenario's ``object_names`` MUST exist as a
``<body name=...>`` in the MJCF scene it points at.

``catalog.py`` declares (catalog.py:22) that ``_TABLETOP_OBJECTS`` "MUST match
the MJCF body names in so101_mujoco.xml — they are the contract the sim-oracle
predicates read ground truth against". The world resolves a scenario by id and
grounds its verify predicates against that scenario's ``object_names``; if a name
drifts from the scene (a body renamed in the XML, or a bad edit to the tuple),
``get_object_positions()`` silently omits it and the oracle grades against a name
the scene no longer has — a false verdict on the acceptance face.

Until this file, the ONLY thing asserting that contract was
``tests/vcli/test_playground_real_arm.py::TestRealArmOracleContract``, which is
``@pytest.mark.integration`` (deselected under ``-m 'not integration'``) AND
instantiates a REAL headless ``MuJoCoArm`` (a sim run — Inv-5 sim-gated, the one
global slot). So in the deterministic always-run gate there was NO guard: rename
``mug`` -> ``cup`` in so101_mujoco.xml, or append a bogus name to the tuple, and
CI stays GREEN while the sim-oracle contract silently breaks.

This module closes that gap the E147 (manifest<->driver) way — read the artifact
OFFLINE and assert the mirror. It parses the scene XML with the stdlib
:mod:`xml.etree.ElementTree` (no ``mujoco`` binding, no ``MjModel``, no sim
process, no GL) and asserts every declared object body is present. It INTROSPECTS
``SCENARIOS`` rather than hardcoding a list, so a scenario added later is covered
automatically (E154/E156 pattern: guard the shape, not a frozen enumeration).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from zeno.playground.catalog import SCENARIOS


def _body_names(scene_xml: str) -> frozenset[str]:
    """Return every ``<body name=...>`` in *scene_xml*, at any nesting depth.

    Pure stdlib XML parse — never loads mujoco or builds a model. MuJoCo scenes
    nest bodies under ``worldbody`` and under one another; ``iter('body')``
    walks the whole tree. (The bundled so101 scene has no ``<include>``; if a
    future scene splits bodies into an included file this guard would need to
    follow includes — asserted non-vacuously below so that regression is loud.)
    """
    root = ET.parse(scene_xml).getroot()
    return frozenset(
        b.attrib["name"] for b in root.iter("body") if "name" in b.attrib
    )


# Every registered scenario that declares graspable objects — introspected, not
# hardcoded, so a new preset scene is guarded the moment it lands in SCENARIOS.
_OBJECT_SCENARIOS = [s for s in SCENARIOS.values() if s.object_names]


def test_at_least_one_object_scenario_is_guarded() -> None:
    """Anti-vacuous: SCENARIOS must contain >=1 scenario with object_names.

    Without this, an empty registry (or every scenario losing its object_names)
    would make the parametrized guard below pass by collecting zero cases.
    """
    assert _OBJECT_SCENARIOS, "no playground scenario declares object_names to guard"


@pytest.mark.parametrize("scenario", _OBJECT_SCENARIOS, ids=lambda s: s.id)
def test_scenario_object_names_are_real_mjcf_bodies(scenario) -> None:
    """Each declared object name resolves to a body in the scenario's scene."""
    scene = Path(scenario.scene_xml)
    assert scene.is_file(), f"{scenario.id}: scene_xml missing on disk: {scene}"

    bodies = _body_names(scenario.scene_xml)
    # Anti-vacuous: a scene that parsed to zero bodies would let any object_names
    # set pass by subset-of-empty logic only if object_names were also empty; but
    # a real scene always has bodies, so an empty parse is itself the bug.
    assert bodies, f"{scenario.id}: parsed no <body> elements from {scene}"

    missing = set(scenario.object_names) - bodies
    assert not missing, (
        f"{scenario.id}: object_names not present as MJCF bodies in {scene.name}: "
        f"{sorted(missing)}. The sim-oracle grades against these names; a body "
        f"renamed in the scene (or a bad edit to the catalog tuple) silently "
        f"breaks the verify contract. Fix the tuple or the <body name> to match."
    )


def test_tabletop_declares_the_six_known_objects() -> None:
    """Sanity pin on the canonical arm scene (mirrors the integration contract).

    Not vacuous coverage — it fixes the expected count so a silent shrink of the
    tuple (e.g. down to 1 name that happens to exist) is caught even though the
    subset check above would still pass.
    """
    tabletop = SCENARIOS["tabletop"]
    assert len(tabletop.object_names) == 6
    assert set(tabletop.object_names) <= _body_names(tabletop.scene_xml)
