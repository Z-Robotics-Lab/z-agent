# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MuJoCoG1.get_camera_frame must HONOR each caller's resolution (E168).

The E167 round fixed exactly this defect in the go2 head-camera renderer but left
its DIRECT MIRROR unfixed in the sibling humanoid driver. MuJoCoG1's head camera
is a SHARED resource: the bare look/describe acceptance path renders it via
``base.get_camera_frame()`` (the 640x480 default, feeding the VLM), while the
G1HeadPerception wrapper is explicitly configurable — ``G1HeadPerception(base,
width=W, height=H)`` calls ``base.get_camera_frame(self._w, self._h)`` and the
g1_perception_oracle calls ``base.get_camera_frame(_RENDER_W, _RENDER_H)``. The
method's signature and docstring both ADVERTISE per-call dims.

Before R379 ``get_camera_frame`` cached ONE renderer at the FIRST call's dims
(``if self._cam_renderer is None``) and IGNORED width/height on every later call.
So any non-default G1HeadPerception used AFTER a bare 640x480 look would silently
get a 640x480 frame instead of the resolution it asked for — the same cache-once
API-contract violation E167 removed from go2, latent here only because today's
callers happen to all pass 640x480.

These guards pin the contract: each call renders at the resolution IT requested,
re-creating the cached renderer only when the requested dims change. Deterministic:
a fake ``_get_mujoco`` records every Renderer's construction dims, so no real GL /
MuJoCo / sim slot is touched.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

import vector_os_nano.hardware.sim.mujoco_g1 as mg1
from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1


class _FakeRenderer:
    """Records the (height, width) it was built at; renders a matching frame."""

    open_dims: list[tuple[int, int]] = []
    closed: int = 0

    def __init__(self, model: Any, height: int, width: int) -> None:
        self._h = height
        self._w = width
        self.width = width
        self.height = height
        _FakeRenderer.open_dims.append((height, width))

    def update_scene(self, data: Any, camera: int = 0) -> None:
        pass

    def render(self) -> np.ndarray:
        # (H, W, 3) uint8 like the real MuJoCo Renderer, so a resolution mismatch
        # surfaces as a real array-shape bug rather than being hidden by the fake.
        return np.zeros((self._h, self._w, 3), dtype=np.uint8)

    def close(self) -> None:
        _FakeRenderer.closed += 1


class _FakeCam:
    id = 0


class _FakeModel:
    ncam = 1

    def cam(self, name: str) -> _FakeCam:
        return _FakeCam()


class _FakeMj:
    Renderer = _FakeRenderer


@pytest.fixture()
def g1(monkeypatch: pytest.MonkeyPatch) -> MuJoCoG1:
    """A MuJoCoG1 with GL/MuJoCo faked out — no sim slot, no GPU."""
    _FakeRenderer.open_dims = []
    _FakeRenderer.closed = 0
    monkeypatch.setattr(mg1, "_get_mujoco", lambda: _FakeMj)
    robot = object.__new__(MuJoCoG1)
    robot._connected = True  # type: ignore[attr-defined]
    robot._model = _FakeModel()  # type: ignore[attr-defined]
    robot._data = object()  # type: ignore[attr-defined]
    robot._cam_renderer = None  # type: ignore[attr-defined]
    robot._cam_renderer_dims = None  # type: ignore[attr-defined]
    return robot


def test_rgb_frame_matches_requested_dims(g1: MuJoCoG1) -> None:
    """get_camera_frame returns a frame at the dims IT was called with."""
    frame = g1.get_camera_frame(320, 240)
    assert frame.shape[:2] == (240, 320)


def test_look_before_configured_perception_does_not_lock_resolution(
    g1: MuJoCoG1,
) -> None:
    """The regression: a bare 640x480 'look' must NOT force a later configured
    320x240 perception frame to come back 640x480."""
    look = g1.get_camera_frame()          # bare default -> 640x480 (VLM path)
    assert look.shape[:2] == (480, 640)
    perc = g1.get_camera_frame(320, 240)  # configured perception -> MUST be 320x240
    assert perc.shape[:2] == (240, 320)


def test_same_dims_reuse_the_renderer(g1: MuJoCoG1) -> None:
    """No wasteful re-create when the dims do not change (one RGB renderer)."""
    g1.get_camera_frame(320, 240)
    g1.get_camera_frame(320, 240)
    builds = [d for d in _FakeRenderer.open_dims if d == (240, 320)]
    assert len(builds) == 1


def test_dim_change_closes_the_old_renderer(g1: MuJoCoG1) -> None:
    """Switching resolution releases the old GL context before replacing it."""
    g1.get_camera_frame(640, 480)
    g1.get_camera_frame(320, 240)
    assert _FakeRenderer.closed == 1
