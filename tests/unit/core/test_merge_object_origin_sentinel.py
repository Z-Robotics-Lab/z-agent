# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Regression: merge_object must not treat a genuine 0.0 coordinate as "no update".

Backlog #3 — the x=0/y=0 sentinel trap. The old code did
``x=x if x != 0.0 else existing.x`` so a real object localized at the world
origin (or anywhere on the x=0 / y=0 axis) was silently kept at its stale
position. The fix switches the sentinel to ``None``: ``None`` means "no new
localization, keep existing"; a real float (including 0.0) is always applied.

This is the same bug class that hid the (0,0) catastrophe (D97) — a real
coordinate that happens to be zero must round-trip through a merge.
"""
from __future__ import annotations

from vector_os_nano.core.scene_graph import SceneGraph


def _fresh_graph() -> SceneGraph:
    # merge_object keys on category+room_id; it does not require a RoomNode.
    return SceneGraph()


def test_merge_updates_to_genuine_origin_x() -> None:
    """An object first seen at (5.0, 3.0), re-localized to x=0.0, must move to 0.0."""
    sg = _fresh_graph()
    sg.merge_object(category="cup", room_id="kitchen", viewpoint_id="vp_1", x=5.0, y=3.0)
    merged = sg.merge_object(
        category="cup", room_id="kitchen", viewpoint_id="vp_2", x=0.0, y=3.0,
    )
    assert merged.x == 0.0, f"genuine x=0.0 was discarded as sentinel, got {merged.x}"
    assert merged.y == 3.0


def test_merge_updates_to_genuine_origin_y() -> None:
    """Symmetric: a genuine y=0.0 must be applied, not discarded."""
    sg = _fresh_graph()
    sg.merge_object(category="cup", room_id="kitchen", viewpoint_id="vp_1", x=5.0, y=3.0)
    merged = sg.merge_object(
        category="cup", room_id="kitchen", viewpoint_id="vp_2", x=5.0, y=0.0,
    )
    assert merged.x == 5.0
    assert merged.y == 0.0, f"genuine y=0.0 was discarded as sentinel, got {merged.y}"


def test_merge_updates_to_full_origin() -> None:
    """An object re-localized to exactly (0.0, 0.0) must land there, not stay stale."""
    sg = _fresh_graph()
    sg.merge_object(category="cup", room_id="kitchen", viewpoint_id="vp_1", x=5.0, y=3.0)
    merged = sg.merge_object(
        category="cup", room_id="kitchen", viewpoint_id="vp_2", x=0.0, y=0.0,
    )
    assert (merged.x, merged.y) == (0.0, 0.0)


def test_coordinateless_merge_keeps_existing_position() -> None:
    """Regression: a coordinate-less re-observation (None) must NOT clobber a real pose."""
    sg = _fresh_graph()
    sg.merge_object(category="cup", room_id="kitchen", viewpoint_id="vp_1", x=5.0, y=3.0)
    # No x/y supplied — "seen in the room again, but not localized this time".
    merged = sg.merge_object(category="cup", room_id="kitchen", viewpoint_id="vp_2")
    assert (merged.x, merged.y) == (5.0, 3.0), "un-localized merge must keep the real pose"


def test_new_object_without_coords_defaults_to_origin() -> None:
    """A brand-new object with no coords keeps the historical (0.0, 0.0) default."""
    sg = _fresh_graph()
    obj = sg.merge_object(category="cup", room_id="kitchen", viewpoint_id="vp_1")
    assert (obj.x, obj.y) == (0.0, 0.0)


def test_new_object_with_explicit_origin_coords() -> None:
    """A brand-new object explicitly localized at the origin is stored at the origin."""
    sg = _fresh_graph()
    obj = sg.merge_object(
        category="cup", room_id="kitchen", viewpoint_id="vp_1", x=0.0, y=0.0,
    )
    assert (obj.x, obj.y) == (0.0, 0.0)
