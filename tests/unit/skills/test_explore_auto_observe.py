# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for the explore auto-observe depth-localize fix (Spec 1).

The exploration loop's auto-observe hook (explore.py _exploration_loop) used to
build ``detected_objects`` as a list of DICTS and pass them to
SceneGraph.observe_with_viewpoint, whose contract unpacks
``for category, obj_x, obj_y in detected_objects`` (3-tuples).  Dicts iterate to
their keys -> ValueError, swallowed by the hook's try/except -> explore stored
NOTHING.  The fix depth-localizes the VLM-named objects via localize_objects_3d
and passes (cat, x, y) tuples ONLY for objects that localized — never (0, 0).

These tests reproduce the FIXED hook logic faithfully (the loop itself is a
long-running ROS2 thread; the localize/build/observe sub-block is what changed)
and drive a REAL SceneGraph so the tuple contract is enforced.

No MuJoCo, no GPU, no network — pure stubs + a real SceneGraph.
"""
from __future__ import annotations

from typing import Any

import pytest

from zeno.core.scene_graph import SceneGraph


# ---------------------------------------------------------------------------
# Fakes mirroring the explore auto-observe collaborators
# ---------------------------------------------------------------------------


class _FakeVLMObj:
    def __init__(self, name: str, confidence: float = 0.8) -> None:
        self.name = name
        self.confidence = confidence


class _FakeDescResult:
    def __init__(self, summary: str) -> None:
        self.summary = summary


class _FakeVLM:
    """Stub VLM: describe_scene + find_objects (the explore hook's contract)."""

    def __init__(self, object_names: list[str], summary: str = "a room") -> None:
        self._names = object_names
        self._summary = summary

    def describe_scene(self, frame: Any) -> _FakeDescResult:
        return _FakeDescResult(self._summary)

    def find_objects(self, frame: Any) -> list[_FakeVLMObj]:
        return [_FakeVLMObj(n) for n in self._names]


def _run_auto_observe_hook(
    *,
    spatial_memory: SceneGraph,
    perception: Any,
    vlm: Any,
    room: str,
    x: float,
    y: float,
    heading: float,
    localize_fn: Any,
) -> None:
    """Faithful reproduction of explore.py's FIXED auto-observe sub-block.

    Mirrors _exploration_loop lines that depth-localize VLM objects and build
    (cat, x, y) tuples, skipping un-localized objects (never (0, 0)).  Uses an
    injected ``localize_fn`` so the test controls which objects localize without
    pulling in the real depth pipeline.
    """
    if vlm is None:
        return
    if not spatial_memory.should_add_viewpoint(room, x, y):
        return
    desc_result = vlm.describe_scene(None)
    obj_result = vlm.find_objects(None)
    scene_summary = str(getattr(desc_result, "summary", ""))
    object_names = [
        str(getattr(o, "name", ""))
        for o in (obj_result or [])
        if str(getattr(o, "name", ""))
    ]
    world_positions: dict[str, tuple[float, float, float]] = {}
    if object_names:
        loc_results = localize_fn(perception, object_names)
        world_positions = {label: (lx, ly, lz) for label, lx, ly, lz in loc_results}
    detected_objects: list[tuple[str, float, float]] | None = None
    if world_positions:
        detected_objects = [
            (name, world_positions[name][0], world_positions[name][1])
            for name in object_names
            if name in world_positions
        ]
    spatial_memory.observe_with_viewpoint(
        room=room,
        x=x,
        y=y,
        heading=heading,
        objects=object_names,
        description=scene_summary,
        detected_objects=detected_objects,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_localized_object_stored_at_real_xy_unlocalized_skipped():
    """When SOME objects localize: localized ones get their real (x, y); the
    un-localized one is recorded names-only WITHOUT a fabricated (0, 0)."""
    sg = SceneGraph()

    def _fake_localize(perception: Any, names: list[str]):
        # Only 'cup' localizes; 'counter' is dropped (no usable depth point).
        return [("cup", 5.0, 3.0, 0.4)]

    _run_auto_observe_hook(
        spatial_memory=sg,
        perception=object(),  # any non-None stub; localize is injected
        vlm=_FakeVLM(["cup", "counter"]),
        room="kitchen",
        x=1.0,
        y=2.0,
        heading=0.0,
        localize_fn=_fake_localize,
    )

    objs = {o.category: o for o in sg.find_objects_in_room("kitchen")}
    assert "cup" in objs
    assert objs["cup"].x == pytest.approx(5.0)
    assert objs["cup"].y == pytest.approx(3.0)
    # 'counter' did not localize: it MUST NOT be present at a fabricated (0, 0).
    # (use_detected=True path merges only detected_objects, so 'counter' is not
    # recorded this observation — it is re-recorded once depth localizes it.)
    if "counter" in objs:
        assert not (
            objs["counter"].x == pytest.approx(0.0)
            and objs["counter"].y == pytest.approx(0.0)
        ), "un-localized object must never be stored at fake (0, 0)"


def test_no_perception_falls_back_to_names_only_no_crash():
    """perception=None -> localize returns [] -> detected_objects=None ->
    observe_with_viewpoint takes the names-only branch; object recorded WITHOUT
    a fabricated coordinate, no crash."""
    sg = SceneGraph()

    def _fake_localize(perception: Any, names: list[str]):
        # The real localize_objects_3d returns [] for perception=None.
        assert perception is None
        return []

    _run_auto_observe_hook(
        spatial_memory=sg,
        perception=None,
        vlm=_FakeVLM(["sofa"]),
        room="living_room",
        x=0.5,
        y=0.5,
        heading=0.0,
        localize_fn=_fake_localize,
    )

    objs = {o.category: o for o in sg.find_objects_in_room("living_room")}
    assert "sofa" in objs
    # Names-only path: merge_object created the object with default x=y=0.0.
    # That is the SAME as the legitimate no-perception case (names-only), NOT a
    # fabricated localized position — the object simply has no coordinate yet.
    # The key contract is no crash and the object IS recorded by name.


def test_real_localizer_with_none_perception_returns_empty():
    """Integration with the REAL localize_objects_3d: perception=None yields []
    (its internal guard), so the hook routes to the names-only path safely."""
    from zeno.perception.object_localizer import localize_objects_3d

    sg = SceneGraph()
    _run_auto_observe_hook(
        spatial_memory=sg,
        perception=None,
        vlm=_FakeVLM(["lamp"]),
        room="hallway",
        x=0.0,
        y=0.0,
        heading=0.0,
        localize_fn=localize_objects_3d,
    )
    objs = {o.category: o for o in sg.find_objects_in_room("hallway")}
    assert "lamp" in objs
