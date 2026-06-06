# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""SCENARIOS — the playground's preset-scene catalog.

A small id -> Scenario registry. The kernel never imports this; the playground
world resolves a scenario by id and grounds its verify predicates against the
scenario's known ``object_names``. The scene XML path is derived from the
installed ``hardware/sim`` package (never a machine-specific absolute path).
"""

from __future__ import annotations

from pathlib import Path

from vector_os_nano.playground.scenario import Scenario

# Resolve bundled scene XMLs from the installed package, not a hardcoded path.
_SIM_DIR = Path(__file__).resolve().parent.parent / "hardware" / "sim"

# The bundled tabletop scene ships a table + six graspable free bodies. These
# names MUST match the MJCF body names in so101_mujoco.xml — they are the
# contract the sim-oracle predicates read ground truth against.
_TABLETOP_OBJECTS: tuple[str, ...] = (
    "banana",
    "mug",
    "bottle",
    "screwdriver",
    "duck",
    "lego",
)

TABLETOP = Scenario(
    id="tabletop",
    embodiment="arm",
    scene_xml=str(_SIM_DIR / "so101_mujoco.xml"),
    task_hint="Pick and place objects on a tabletop with the SO-101 arm.",
    object_names=_TABLETOP_OBJECTS,
)

# A named drop-zone over the same so101 scene: the tabletop spans x in
# [-0.10, 0.50], y in [-0.25, 0.25] (table centred at (0.20, 0) with half-sizes
# (0.30, 0.25)). The tray is the right-front quadrant, so placed_count() with no
# argument verifies "object resting INSIDE the tray" — a scene-defined region the
# sub-goal references by scenario instead of hand-passing raw coordinates.
_TRAY_REGION: tuple[float, float, float, float] = (0.20, 0.0, 0.50, 0.25)

TABLETOP_TRAY = Scenario(
    id="tabletop_tray",
    embodiment="arm",
    scene_xml=str(_SIM_DIR / "so101_mujoco.xml"),
    task_hint="Sort objects into the tray (right-front drop-zone) with the SO-101 arm.",
    object_names=_TABLETOP_OBJECTS,
    place_region=_TRAY_REGION,
)

# id -> Scenario. Additive: new preset scenes append here.
SCENARIOS: dict[str, Scenario] = {
    TABLETOP.id: TABLETOP,
    TABLETOP_TRAY.id: TABLETOP_TRAY,
}


def get_scenario(scenario_id: str) -> Scenario:
    """Return the scenario registered under *scenario_id*.

    Fails loud with the valid set when unknown — never a silent fallback.
    """
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        valid = ", ".join(sorted(SCENARIOS)) or "<none>"
        raise KeyError(
            f"unknown playground scenario {scenario_id!r}; valid: {valid}"
        ) from None
