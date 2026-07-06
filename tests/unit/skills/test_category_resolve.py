# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""D168 — colourless CATEGORY reference resolution against the scene object catalog.

A colourless category ("罐子"/"can") cannot be singled out perceptually when the scene's
pickables are near-identical cylinders (grounding-dino scores them within noise, so the
grasp picks a random one — observed: 罐子 grabbed the blue bottle). But the scene's object
CATALOG often makes a category UNIQUE: exactly one "can" among {bottle, bottle, can}. This
resolver maps such a reference to (colour, scene_name) so the grasp can drive the PROVEN
colour-selection path. Ambiguous / absent categories resolve to None (unchanged behaviour).

Pure function — no sim, no model. The verify oracle is untouched; this only chooses WHICH
object to grasp.
"""
from __future__ import annotations

from zeno.skills.perception_grasp import _resolve_unique_category

_SCENE = ("pickable_bottle_blue", "pickable_bottle_green", "pickable_can_red")


def test_unique_zh_category_resolves_to_object_and_colour():
    # 罐子 = "can" is unique in the scene → resolve to the red can + its colour.
    assert _resolve_unique_category("把罐子拿过来", _SCENE) == ("red", "pickable_can_red")


def test_unique_en_category_resolves():
    assert _resolve_unique_category("grab the can", _SCENE) == ("red", "pickable_can_red")


def test_ambiguous_category_resolves_to_none():
    # 瓶子 = "bottle" matches TWO objects → cannot single one out → None (unchanged).
    assert _resolve_unique_category("把瓶子拿过来", _SCENE) is None
    assert _resolve_unique_category("bottle", _SCENE) is None


def test_absent_category_resolves_to_none():
    assert _resolve_unique_category("拿起那个杯子", _SCENE) is None  # no cup in scene


def test_no_object_noun_resolves_to_none():
    assert _resolve_unique_category("前面的东西", _SCENE) is None
    assert _resolve_unique_category("", _SCENE) is None


def test_category_without_known_colour_returns_none_colour():
    # A unique category whose catalog name encodes no known colour → (None, name):
    # resolvable object but no colour attribute to drive the colour path.
    scene = ("pickable_can_plain", "pickable_bottle_blue")
    assert _resolve_unique_category("罐子", scene) == (None, "pickable_can_plain")
