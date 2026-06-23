# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R7 — the HONEST GROUNDED for g1: GT-backed perception match (NOT a self-read).

These tests lock in the honesty CONTRACT of ``detection_matches_gt`` at unit level
(no real model / no sim) with a fake base + a stubbed detector:

  - CORRECT localization (box center on the GT projection)        -> True  (GROUNDED-eligible)
  - WRONG box (box on a wall, far from the GT projection)         -> False (RAN)   [REFUTATION]
  - object OUT OF VIEW (GT behind the camera / off-frame)         -> False (RAN)   [REFUTATION]
  - the detector input is RGB ONLY — the GT is never handed to it (the firewall)

and that the spine grades ``detection_matches_gt('red') == True`` GROUNDED while a
bare call / a short-circuit stays RAN (the spine is byte-unchanged; this just pins it).
"""

from __future__ import annotations

import numpy as np
import pytest

from vector_os_nano.perception.depth_projection import mujoco_intrinsics, world_to_pixel
from vector_os_nano.vcli.worlds.g1_perception_oracle import (
    _RENDER_H,
    _RENDER_W,
    make_detection_matches_gt,
)


# Camera at origin looking +X (the g1 head orientation): xmat columns are
# (right=-Y, up=+Z, -forward=-X). A world point at +X projects to the image center.
_CAM_XPOS = np.array([0.0, 0.0, 0.0])
_CAM_XMAT = np.array([0, 0, -1, -1, 0, 0, 0, 1, 0], dtype=float)  # cols right/up/-fwd

# GT red object 1 m straight ahead (+X) at the camera's own height (z=0 here) —
# projects to the image center ~(320, 240). (In the real sim the camera sits at
# head height and the object at z≈0.32, so the real projection lands lower in-frame;
# the unit fixture keeps it dead-center for a clean contract assertion.)
_GT_RED = [1.0, 0.0, 0.0]


class _Box:
    def __init__(self, x1, y1, x2, y2):
        self.bbox = (x1, y1, x2, y2)
        self.label = "red"
        self.confidence = 0.5


class _StubDetector:
    """A detector whose boxes the test chooses; RECORDS what RGB it was handed and
    asserts it is ONLY an array (never a GT pose) — the firewall proof."""

    def __init__(self, boxes):
        self._boxes = boxes
        self.seen_rgb_shapes: list = []
        self.seen_extra_args: list = []

    def detect(self, rgb, query, *extra):
        assert isinstance(rgb, np.ndarray), "detector must receive an RGB array"
        self.seen_rgb_shapes.append(rgb.shape)
        self.seen_extra_args.append(extra)  # must always be empty (no GT leaked)
        return list(self._boxes)


class _FakeBase:
    """Minimal g1-shape base: GT object positions + the exact camera pose."""

    def __init__(self, gt, cam_xpos=_CAM_XPOS, cam_xmat=_CAM_XMAT):
        self._gt = gt
        self._cam_xpos = cam_xpos
        self._cam_xmat = cam_xmat

    def get_object_positions(self):
        return dict(self._gt)

    def get_camera_pose(self):
        return self._cam_xpos.copy(), self._cam_xmat.copy()

    def get_camera_frame(self, w=_RENDER_W, h=_RENDER_H):
        return np.zeros((h, w, 3), dtype=np.uint8)


class _FakeAgent:
    """g1 shape: a base with GT + camera, NO arm, NO bound perception adapter."""

    def __init__(self, base):
        self._base = base
        self._arm = None
        self._perception = None


@pytest.fixture
def gt_projection():
    intr = mujoco_intrinsics(_RENDER_W, _RENDER_H, vfov_deg=45.0)
    proj = world_to_pixel(*_GT_RED, intr, _CAM_XPOS, _CAM_XMAT)
    assert proj is not None
    return proj  # (u, v, depth)


def _run(monkeypatch, boxes, gt=None):
    """Wire a stub detector + fake g1 agent, return (oracle_result, stub)."""
    gt = gt or {"pickable_can_red": _GT_RED, "pickable_bottle_green": [1.0, -0.5, 0.0]}
    stub = _StubDetector(boxes)
    monkeypatch.setattr(
        "vector_os_nano.perception.grounding_dino.get_shared_detector",
        lambda: stub,
    )
    agent = _FakeAgent(_FakeBase(gt))
    oracle = make_detection_matches_gt(agent)
    return oracle, stub


def test_correct_box_on_gt_projection_matches(monkeypatch, gt_projection):
    """A box centered on the GT projection -> True (the EARNED GROUNDED)."""
    gu, gv, _ = gt_projection
    boxes = [_Box(gu - 20, gv - 20, gu + 20, gv + 20)]  # center == (gu, gv)
    oracle, stub = _run(monkeypatch, boxes)
    assert oracle("red", tol=60.0) is True
    # FIREWALL: the detector only ever saw an RGB array, never a GT pose.
    assert all(extra == () for extra in stub.seen_extra_args)
    assert all(len(shape) == 3 for shape in stub.seen_rgb_shapes)


def test_wrong_box_far_from_gt_is_refuted(monkeypatch, gt_projection):
    """REFUTATION: a box on a wall (far from the GT projection) -> False -> RAN."""
    boxes = [_Box(5.0, 5.0, 25.0, 25.0)]  # center (15,15), hundreds of px from GT
    oracle, _ = _run(monkeypatch, boxes)
    assert oracle("red", tol=60.0) is False


def test_object_out_of_view_is_refuted(monkeypatch):
    """REFUTATION: GT object BEHIND the camera (g1 faces away) -> not imageable -> False."""
    gt = {"pickable_can_red": [-1.0, 0.0, 0.0]}  # behind a +X-looking camera
    boxes = [_Box(300, 220, 340, 260)]  # even a centered box can't match an unimageable GT
    oracle, _ = _run(monkeypatch, boxes, gt=gt)
    assert oracle("red", tol=60.0) is False


def test_no_detection_is_refuted(monkeypatch):
    """No box at all -> False (detector found nothing to match)."""
    oracle, _ = _run(monkeypatch, boxes=[])
    assert oracle("red", tol=60.0) is False


def test_missing_base_fails_safe(monkeypatch):
    """No base -> False (never raises into the verifier sandbox)."""
    class _Bare:
        _base = None
        _arm = None
    oracle = make_detection_matches_gt(_Bare())
    assert oracle("red") is False


def test_spine_grades_match_grounded_bare_ran():
    """The frozen spine grades '== True' GROUNDED and a bare call RAN (unchanged)."""
    from vector_os_nano.vcli.cognitive.evidence_classifier import classify_verify_expr

    names = frozenset({"detection_matches_gt"})
    assert classify_verify_expr("detection_matches_gt('red') == True", names) == "GROUNDED"
    assert classify_verify_expr("detection_matches_gt('red')", names) == "RAN"
    assert classify_verify_expr("detection_matches_gt('red') or True", names) == "RAN"
