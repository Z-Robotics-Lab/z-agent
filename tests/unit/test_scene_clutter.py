# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the VECTOR_SCENE_CLUTTER scenario knob injects visual distractor geoms
into the go2 room scene at build time — a 2nd SCENE VARIANT off the frozen minimal
tabletop (R226 breadth pivot; answers the R200 'zero scene diversity, no clutter'
ambition critic). Worlds are CONFIG, not code (Invariant 3): the clutter is added via
the existing scene_builder ``extra_geoms`` seam (the same seam g1's percept_target_red
uses), so ZERO kernel/driver edits — one env knob, no new code path.

The clutter geoms are DECORATIVE only: contype/conaffinity 0 (no collision, like the
room rugs/baseboards), no freejoint (not pickable, absent from get_object_positions()).
They render as visible distractors in the head-cam — including a SAME-COLOUR green
competitor — so re-running a confirmed colour-fetch bar on the cluttered scene tests
whether grounding discriminates the real central target, not merely 'the only green thing'.

The honest-verify spine is UNTOUCHED: holding_object(real bottle) reads live sim GT the
actor cannot author, and a decorative box has no weld/freejoint, so grasping toward it
holds nothing — the verdict is unfakeable regardless of what perception selects.

Default (unset) keeps the frozen baseline BYTE-IDENTICAL (extra_geoms default empty),
mirroring VECTOR_SCENE_SWAP / VECTOR_FETCH_FAR.
"""
from __future__ import annotations

import mujoco
import pytest

from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2, _GO2_CLUTTER_GEOMS


def _geom_id(go2: MuJoCoGo2, name: str) -> int:
    m = go2._mj.model
    return mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, name)


def test_default_has_no_clutter(monkeypatch):
    """Default (no env): the frozen minimal scene has none of the clutter geoms."""
    monkeypatch.delenv("VECTOR_SCENE_CLUTTER", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    for g in _GO2_CLUTTER_GEOMS:
        assert _geom_id(go2, str(g["name"])) < 0, (
            f"{g['name']} must be absent without VECTOR_SCENE_CLUTTER"
        )


def test_clutter_injects_all_distractor_geoms(monkeypatch):
    """VECTOR_SCENE_CLUTTER=1: every declared clutter geom is compiled into the scene."""
    monkeypatch.setenv("VECTOR_SCENE_CLUTTER", "1")
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    assert _GO2_CLUTTER_GEOMS, "clutter set must be non-empty"
    for g in _GO2_CLUTTER_GEOMS:
        assert _geom_id(go2, str(g["name"])) >= 0, (
            f"{g['name']} must be present with VECTOR_SCENE_CLUTTER=1"
        )


def test_clutter_is_non_colliding(monkeypatch):
    """Clutter is DECORATIVE — contype/conaffinity 0 (like rugs): it never perturbs
    the robot or pickables physically; it only adds visual distractors."""
    monkeypatch.setenv("VECTOR_SCENE_CLUTTER", "1")
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    m = go2._mj.model
    for g in _GO2_CLUTTER_GEOMS:
        gid = _geom_id(go2, str(g["name"]))
        assert gid >= 0
        assert int(m.geom_contype[gid]) == 0, f"{g['name']} must not collide (contype 0)"
        assert int(m.geom_conaffinity[gid]) == 0, f"{g['name']} must not collide (conaffinity 0)"


def test_clutter_includes_same_colour_green_competitor(monkeypatch):
    """The clutter deliberately includes a green distractor matching the green bottle's
    hue — so a colour-fetch that still grounds the real bottle proves DISCRIMINATION,
    not 'only green thing'. Guards the honest-challenge intent against silent dilution."""
    greens = [g for g in _GO2_CLUTTER_GEOMS if tuple(g["rgba"][:3]) == (0.25, 0.70, 0.35)]
    assert greens, "clutter must contain a same-hue green competitor (rgba 0.25/0.70/0.35)"


def test_clutter_does_not_occlude_green_sightline():
    """No clutter geom may sit on the dog->green-bottle sightline (dog spawn x=10.0,
    green bottle at (10.88, 3.00)): a decorative box between camera and target would
    OCCLUDE (a different, unintended scenario). Keep clutter at x>=10.9 OR |y-3.0|>=0.35."""
    for g in _GO2_CLUTTER_GEOMS:
        x, y, _z = (float(v) for v in g["pos"])
        on_sightline = x < 10.88 and abs(y - 3.00) < 0.35
        assert not on_sightline, (
            f"{g['name']} at {g['pos']} occludes the green-bottle sightline"
        )
