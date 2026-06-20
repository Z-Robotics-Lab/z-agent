# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Deictic front-object resolver — segment the salient thing in front."""
from __future__ import annotations

import numpy as np

from vector_os_nano.perception.front_object import front_object_mask

_H, _W = 48, 64


def _muted_bg():
    """A muted gray scene (low saturation) — like the table/floor/walls."""
    rgb = np.full((_H, _W, 3), 130, dtype=np.uint8)
    rgb[:, :, 0] += 5  # tiny tint, still low saturation
    return rgb


def _put_blob(rgb, cx, cy, color, r=5):
    for v in range(max(0, cy - r), min(_H, cy + r)):
        for u in range(max(0, cx - r), min(_W, cx + r)):
            rgb[v, u] = color


def test_central_salient_object_found():
    rgb = _muted_bg()
    _put_blob(rgb, _W // 2, _H // 2, (220, 30, 30))  # vivid red, centre
    depth = np.full((_H, _W), 1.0, dtype=np.float32)
    m = front_object_mask(rgb, depth)
    assert m is not None
    ys, xs = np.where(m > 0)
    assert abs(xs.mean() - _W / 2) < 6 and abs(ys.mean() - _H / 2) < 6


def test_picks_most_central_of_two():
    rgb = _muted_bg()
    _put_blob(rgb, _W // 2, _H // 2, (30, 220, 30))   # central green
    _put_blob(rgb, 8, 8, (30, 30, 220))               # off-corner blue
    depth = np.full((_H, _W), 1.0, dtype=np.float32)
    m = front_object_mask(rgb, depth)
    ys, xs = np.where(m > 0)
    assert abs(xs.mean() - _W / 2) < 8  # the central blob, not the corner


def test_muted_scene_returns_none():
    rgb = _muted_bg()
    depth = np.full((_H, _W), 1.0, dtype=np.float32)
    assert front_object_mask(rgb, depth) is None


def test_far_object_rejected_by_depth():
    rgb = _muted_bg()
    _put_blob(rgb, _W // 2, _H // 2, (220, 30, 30))
    depth = np.full((_H, _W), 9.0, dtype=np.float32)  # all far -> beyond max_depth
    assert front_object_mask(rgb, depth, max_depth=4.0) is None


def test_speckle_below_min_blob_rejected():
    rgb = _muted_bg()
    rgb[24, 32] = (250, 0, 0)  # one vivid pixel
    depth = np.full((_H, _W), 1.0, dtype=np.float32)
    assert front_object_mask(rgb, depth, min_blob=50) is None


def test_thin_bridge_keeps_central_object_selectable():
    """Regression (D31): a thin saturated table band must not lose the central object.

    The real go2+piper bug: the brown table's saturation reached the threshold in
    a thin chain that 8-connectivity FUSED the central green cylinder into one
    giant blob with the off-centre cylinders + table, so the central object
    stopped existing as its own component and a brown table sliver won (12.2cm
    error → green@2.3cm after the fix; proven on the live sim, not reproducible
    in a clean synthetic frame because the winning sliver depends on real table
    texture). This guards that opening still yields the central GREEN object as a
    distinct component in a multi-object, table-bridged scene.
    """
    rgb = _muted_bg()
    cy = _H // 2
    # A wide, 1px-THIN saturated table band spanning the scene at the cylinders'
    # base — its saturation just clears the threshold (like the real brown table),
    # so without opening it 8-connects every vivid object into one giant blob and
    # the central object stops existing as its own component (a sliver wins).
    rgb[cy + 4, 6 : _W - 6] = (120, 200, 120)
    _put_blob(rgb, _W // 2, cy, (30, 220, 30), r=4)        # central green (target)
    _put_blob(rgb, _W // 2 - 18, cy, (220, 30, 30), r=4)   # left red
    _put_blob(rgb, _W // 2 + 18, cy, (30, 30, 220), r=4)   # right blue
    depth = np.full((_H, _W), 1.0, dtype=np.float32)
    m = front_object_mask(rgb, depth)
    assert m is not None
    ys, xs = np.where(m > 0)
    # Selection must land on the CENTRAL green blob, not a fused-blob centroid
    # nor an off-centre object/table sliver.
    assert abs(xs.mean() - _W / 2) < 5, (
        f"selected centroid x={xs.mean():.1f} drifted off the central object "
        "— the thin table band fused the blobs (opening failed)"
    )
    sel = rgb[m > 0]
    assert sel[:, 1].mean() > sel[:, 0].mean() + 20, "selected object is not the green one"
