# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MuJoCoGo2.get_self_mask must HONOR each caller's resolution (E170).

The segmentation renderer behind ``get_self_mask`` is the THIRD sibling of the
go2 head-camera renderer family. E167 fixed the RGB (``_cam_renderer``) and depth
(``_depth_renderer``) renderers to render at each call's dims via ``_ensure_render``;
E168 fixed the g1 mirror. But ``get_self_mask``'s ``_seg_renderer`` was MISSED — it
kept the raw cache-once guard (``if not hasattr(self, "_seg_renderer")``), so the
FIRST caller's (width, height) silently won on every later call.

Live harm path: the sole caller (Go2GraspPerception.get_depth_frame) applies the
self-mask ONLY ``if self_mask.shape == depth.shape``. If a 640x480 mask ever leaks
into a 320x240 grasp (or vice-versa), that shape guard fails SILENTLY and the arm's
own pixels are NOT dropped -> the Piper arm becomes a grasp distractor (the exact
D30 self-occlusion regression the mask exists to prevent), with no error.

This guard pins the contract: get_self_mask(w, h) returns an (h, w) mask, re-creating
the cached segmentation renderer only when the requested dims change. Deterministic:
a fake ``_get_mujoco`` records every Renderer's construction dims — no real GL /
MuJoCo / sim slot is touched.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

import zeno.hardware.sim.mujoco_go2 as mg2
from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2


class _FakeSegRenderer:
    """Records the (height, width) it was built at; renders a matching frame.

    Superset fake: supports the segmentation path (get_self_mask) AND the depth
    path (get_depth_frame via _ensure_render) so the alignment test can render
    both against one fake — a resolution mismatch then surfaces as a real
    array-shape bug rather than being hidden by the fake.
    """

    open_dims: list[tuple[int, int]] = []
    closed: int = 0

    def __init__(self, model: Any, height: int, width: int) -> None:
        self._h = height
        self._w = width
        self._seg = False
        self._depth = False
        self.scene = type("S", (), {"flags": {}})()
        _FakeSegRenderer.open_dims.append((height, width))

    def enable_segmentation_rendering(self) -> None:
        self._seg = True

    def enable_depth_rendering(self) -> None:
        self._depth = True

    def update_scene(self, data: Any, camera: int = 0) -> None:
        pass

    def render(self) -> np.ndarray:
        if self._seg:
            # Real MuJoCo segmentation render is (H, W, 2): [...,0] = geom id.
            return np.full((self._h, self._w, 2), -1, dtype=np.int32)
        if self._depth:
            return np.ones((self._h, self._w), dtype=np.float32)
        return np.zeros((self._h, self._w, 3), dtype=np.uint8)

    def close(self) -> None:
        _FakeSegRenderer.closed += 1


class _FakeObj:
    mjOBJ_BODY = 1


class _FakeRndFlag:
    mjRND_SHADOW = 0
    mjRND_REFLECTION = 1


class _FakeMj:
    Renderer = _FakeSegRenderer
    mjtObj = _FakeObj
    mjtRndFlag = _FakeRndFlag

    @staticmethod
    def mj_name2id(model: Any, obj: int, name: str) -> int:
        return -1  # no piper_base_link -> arm subtree empty

    @staticmethod
    def mj_id2name(model: Any, obj: int, gid: int) -> str:
        return ""


class _FakeCam:
    id = 0


class _FakeModel:
    nbody = 0
    ngeom = 0

    def cam(self, name: str) -> _FakeCam:
        return _FakeCam()


class _FakeMjHandle:
    model = _FakeModel()
    data = object()


@pytest.fixture()
def go2(monkeypatch: pytest.MonkeyPatch) -> MuJoCoGo2:
    """A MuJoCoGo2 with GL/MuJoCo faked out — no sim slot, no GPU."""
    _FakeSegRenderer.open_dims = []
    _FakeSegRenderer.closed = 0
    monkeypatch.setattr(mg2, "_get_mujoco", lambda: _FakeMj)
    robot = object.__new__(MuJoCoGo2)
    robot._connected = True  # type: ignore[attr-defined]
    robot._mj = _FakeMjHandle()  # type: ignore[attr-defined]
    return robot


def test_self_mask_matches_requested_dims(go2: MuJoCoGo2) -> None:
    """get_self_mask returns an (h, w) bool mask at the dims IT was called with."""
    mask = go2.get_self_mask(320, 240)
    assert mask.shape == (240, 320)
    assert mask.dtype == bool


def test_look_res_does_not_lock_self_mask_resolution(go2: MuJoCoGo2) -> None:
    """The regression: a bare 640x480 self-mask must NOT force a later 320x240
    grasp self-mask to come back 640x480 (which fails the caller's shape guard
    -> arm pixels silently NOT dropped -> arm becomes a grasp distractor)."""
    first = go2.get_self_mask(640, 480)
    assert first.shape == (480, 640)
    grasp = go2.get_self_mask(320, 240)
    assert grasp.shape == (240, 320)


def test_self_mask_aligns_with_grasp_depth_dims(go2: MuJoCoGo2) -> None:
    """The grasp contract: after an interleaved 640x480 mask, a 320x240 mask
    matches the 320x240 depth shape so the caller's ``self_mask.shape ==
    depth.shape`` guard passes and the arm pixels are actually zeroed."""
    go2.get_self_mask(640, 480)             # e.g. a describe/look-sized mask
    mask = go2.get_self_mask(320, 240)      # grasp mask
    depth = go2.get_depth_frame(320, 240)   # grasp depth
    assert mask.shape == depth.shape == (240, 320)


def test_same_dims_reuse_the_seg_renderer(go2: MuJoCoGo2) -> None:
    """No wasteful re-create when the dims do not change (one seg renderer)."""
    go2.get_self_mask(320, 240)
    go2.get_self_mask(320, 240)
    seg_builds = [d for d in _FakeSegRenderer.open_dims if d == (240, 320)]
    assert len(seg_builds) == 1


def test_dim_change_closes_the_old_seg_renderer(go2: MuJoCoGo2) -> None:
    """Re-creating on a dim change releases the old GL context (no leak)."""
    go2.get_self_mask(640, 480)
    go2.get_self_mask(320, 240)
    assert _FakeSegRenderer.closed >= 1
