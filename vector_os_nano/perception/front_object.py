# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Deictic "front object" resolver — segment the thing in front, from sensors.

The acceptance phrase "抓前面的东西" (grasp the thing in front) is DEICTIC: it
names no object, so it needs no VLM naming. The right tool for a deictic spatial
query is a salient-object + depth resolver, not a language model. This finds the
most central salient blob in the camera's forward FOV (objects are visually
distinct from the muted table/floor/walls) and returns its pixel mask, from which
grasp_point.py derives the 3D grasp point from REAL depth — honest perception,
never a ground-truth pose lookup.

Pluggable: a VLM (named objects) or EdgeTAM (precise instance masks) can replace
this resolver when available; the 3D-point math downstream is identical. Pure
except for an optional cv2 fast path (graceful numpy fallback).
"""
from __future__ import annotations

import numpy as np

_SAT_MIN = 140      # HSV saturation: vivid objects (cylinders p95~169) vs the
                    # muted table/floor (p80~83). Tuned to the current sim render
                    # fidelity; a VLM/EdgeTAM front-end would be lighting-robust.
_VAL_MIN = 40       # reject near-black
_MIN_BLOB = 50      # px; reject speckle
_MAX_DEPTH = 2.0    # m; the front WORKSPACE only — excludes the far room/doorway
_FRONT_BAND = 0.4   # m; blobs within this of the nearest count as "the front shelf"


def _saturation(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (saturation, value) in 0..255, cv2 if present else numpy."""
    try:
        import cv2
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        return hsv[:, :, 1], hsv[:, :, 2]
    except Exception:  # noqa: BLE001 — numpy HSV S=(max-min)/max, V=max
        a = rgb.astype(np.float32)
        mx = a.max(axis=2)
        mn = a.min(axis=2)
        with np.errstate(divide="ignore", invalid="ignore"):
            sat = np.where(mx > 0, (mx - mn) / mx, 0.0) * 255.0
        return sat.astype(np.uint8), mx.astype(np.uint8)


def _components(binary: np.ndarray):
    """Connected components -> (n, labels, centroids, areas). cv2 or numpy BFS-free fallback."""
    try:
        import cv2
        n, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)
        areas = stats[:, cv2.CC_STAT_AREA]
        return n, labels, centroids, areas
    except Exception:  # noqa: BLE001 — degenerate single-component fallback
        labels = binary.astype(np.int32)
        ys, xs = np.where(binary > 0)
        if len(xs) == 0:
            return 1, labels, np.array([[0.0, 0.0]]), np.array([0])
        centroids = np.array([[0.0, 0.0], [xs.mean(), ys.mean()]])
        areas = np.array([0, len(xs)])
        return 2, labels, centroids, areas


def front_object_mask(
    rgb: np.ndarray,
    depth: np.ndarray | None = None,
    *,
    sat_min: int = _SAT_MIN,
    val_min: int = _VAL_MIN,
    min_blob: int = _MIN_BLOB,
    central_frac: float = 0.8,
    max_depth: float = _MAX_DEPTH,
) -> np.ndarray | None:
    """Binary mask (H, W) uint8 of the salient object most in front, or None.

    Salient = high HSV saturation (objects are vivid vs the muted scene),
    gated to the central forward FOV and to near, valid depth. Among qualifying
    connected blobs, the one whose centroid is CLOSEST to the image centre wins
    ("前面" = directly ahead). Returns None when nothing salient is in front
    (FAIL LOUD — never fabricate a target).
    """
    if rgb is None or rgb.ndim != 3:
        return None
    h, w = rgb.shape[:2]
    sat, val = _saturation(rgb)
    salient = ((sat >= sat_min) & (val >= val_min)).astype(np.uint8)

    # Central forward FOV gate.
    cx0, cx1 = int(w * (1 - central_frac) / 2), int(w - w * (1 - central_frac) / 2)
    cy0, cy1 = int(h * (1 - central_frac) / 2), int(h - h * (1 - central_frac) / 2)
    gate = np.zeros((h, w), dtype=np.uint8)
    gate[cy0:cy1, cx0:cx1] = 1
    salient &= gate

    # Near, valid depth only (the front workspace, not the far room/wall).
    if depth is not None:
        salient &= ((depth > 0) & (depth <= max_depth)).astype(np.uint8)

    if int(salient.sum()) < min_blob:
        return None

    n, labels, centroids, areas = _components(salient)
    img_c = np.array([w / 2.0, h / 2.0])

    # Per-blob: centrality + median depth. "前面" = NEAREST (a foreground object
    # at ~1 m beats a same-colored background object at ~3 m, which 'most central'
    # would wrongly pick when the background sits dead-centre in a doorway).
    cands = []
    for i in range(1, n):
        if areas[i] < min_blob:
            continue
        comp = labels == i
        cen = float(np.linalg.norm(centroids[i] - img_c))
        if depth is not None:
            dv = depth[comp & (depth > 0)]
            zmed = float(np.median(dv)) if dv.size else float("inf")
        else:
            zmed = 0.0
        cands.append((i, cen, zmed))
    if not cands:
        return None

    if depth is not None:
        z_near = min(c[2] for c in cands)
        front_shelf = [c for c in cands if c[2] <= z_near + _FRONT_BAND]
        best = min(front_shelf, key=lambda c: c[1])  # most central of the nearest shelf
    else:
        best = min(cands, key=lambda c: c[1])         # no depth -> most central
    return (labels == best[0]).astype(np.uint8)
