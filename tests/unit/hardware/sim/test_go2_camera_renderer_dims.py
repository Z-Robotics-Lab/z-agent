# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MuJoCoGo2 head-camera renderers must HONOR each caller's resolution (E167).

The go2 head camera is a SHARED resource: the look/explore/describe acceptance
path renders it bare (``base.get_camera_frame()`` -> the 640x480 default, feeding
the VLM), while the grasp path renders it at 320x240 (Go2GraspPerception passes
explicit dims so its RGB *mask* aligns pixel-for-pixel with its 320x240 depth +
intrinsics). Before R378 both methods cached ONE renderer at the FIRST call's
dims (``if not hasattr(self, "_cam_renderer")``) and IGNORED width/height on every
later call. So a "look" (640x480) before a "pick" (320x240) locked the RGB
renderer at 640x480, and the grasp path silently got a 640x480 RGB against a
320x240 depth/intrinsics -> the front-object mask and the depth pointcloud no
longer indexed the same pixels -> wrong 3D grasp point on the bare-cli face.

These guards pin the contract: each RGB/depth call renders at the resolution IT
requested, re-creating the cached renderer only when the requested dims change.
Deterministic: a fake ``_get_mujoco`` records every Renderer's construction dims,
so no real GL / MuJoCo / sim slot is touched.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

import zeno.hardware.sim.mujoco_go2 as mg2
from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2


class _FakeRenderer:
    """Records the (height, width) it was built at; renders a matching frame."""

    open_dims: list[tuple[int, int]] = []
    closed: int = 0

    def __init__(self, model: Any, height: int, width: int) -> None:
        self._h = height
        self._w = width
        self.width = width
        self.height = height
        self.scene = type("S", (), {"flags": {}})()
        self._depth = False
        _FakeRenderer.open_dims.append((height, width))

    def enable_depth_rendering(self) -> None:
        self._depth = True

    def update_scene(self, data: Any, camera: int = 0) -> None:
        pass

    def render(self) -> np.ndarray:
        # Depth renders (H, W) float; RGB renders (H, W, 3) uint8 — matching the
        # real MuJoCo Renderer, so a resolution mismatch surfaces as a real
        # array-shape bug rather than being hidden by the fake.
        if self._depth:
            return np.ones((self._h, self._w), dtype=np.float32)
        return np.zeros((self._h, self._w, 3), dtype=np.uint8)

    def close(self) -> None:
        _FakeRenderer.closed += 1


class _FakeRndFlag:
    mjRND_SHADOW = 0
    mjRND_REFLECTION = 1


class _FakeMj:
    Renderer = _FakeRenderer
    mjtRndFlag = _FakeRndFlag


class _FakeCam:
    id = 0


class _FakeModel:
    def cam(self, name: str) -> _FakeCam:
        return _FakeCam()


class _FakeMjHandle:
    model = _FakeModel()
    data = object()


@pytest.fixture()
def go2(monkeypatch: pytest.MonkeyPatch) -> MuJoCoGo2:
    """A MuJoCoGo2 with GL/MuJoCo faked out — no sim slot, no GPU."""
    _FakeRenderer.open_dims = []
    _FakeRenderer.closed = 0
    monkeypatch.setattr(mg2, "_get_mujoco", lambda: _FakeMj)
    robot = object.__new__(MuJoCoGo2)
    robot._connected = True  # type: ignore[attr-defined]
    robot._mj = _FakeMjHandle()  # type: ignore[attr-defined]
    return robot


def test_rgb_frame_matches_requested_dims(go2: MuJoCoGo2) -> None:
    """get_camera_frame returns a frame at the dims IT was called with."""
    frame = go2.get_camera_frame(320, 240)
    assert frame.shape[:2] == (240, 320)


def test_look_before_grasp_does_not_lock_rgb_resolution(go2: MuJoCoGo2) -> None:
    """The regression: a bare 640x480 'look' must NOT force a later 320x240
    'grasp' RGB to come back 640x480 (which would misalign mask vs depth)."""
    look = go2.get_camera_frame()          # bare default -> 640x480 (VLM path)
    assert look.shape[:2] == (480, 640)
    grasp_rgb = go2.get_camera_frame(320, 240)  # grasp path -> MUST be 320x240
    assert grasp_rgb.shape[:2] == (240, 320)


def test_depth_frame_matches_requested_dims(go2: MuJoCoGo2) -> None:
    """get_depth_frame honors its dims the same way (depth pointcloud path)."""
    depth = go2.get_depth_frame(320, 240)
    assert depth.shape == (240, 320)


def test_grasp_rgb_and_depth_share_one_resolution(go2: MuJoCoGo2) -> None:
    """The grasp contract: RGB mask and depth rendered at the SAME resolution
    even after an interleaved 640x480 look — so front_object_mask indices map
    1:1 onto depth pixels."""
    go2.get_camera_frame()                 # look at 640x480
    rgb = go2.get_camera_frame(320, 240)   # grasp RGB
    depth = go2.get_depth_frame(320, 240)  # grasp depth
    assert rgb.shape[:2] == depth.shape[:2] == (240, 320)


def test_same_dims_reuse_the_renderer(go2: MuJoCoGo2) -> None:
    """No wasteful re-create when the dims do not change (one RGB renderer)."""
    go2.get_camera_frame(320, 240)
    go2.get_camera_frame(320, 240)
    rgb_builds = [d for d in _FakeRenderer.open_dims if d == (240, 320)]
    assert len(rgb_builds) == 1
