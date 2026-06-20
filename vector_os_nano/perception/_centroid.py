# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Robust 3D centroid + depth-outlier rejection — pure numpy.

Extracted verbatim from ``PerceptionPipeline._remove_depth_outliers`` /
``._robust_centroid`` so the perception-driven grasp point (grasp_point.py)
and the tracking pipeline share ONE implementation. Behaviour is byte-identical
to the originals (the existing pipeline/track tests are the regression gate).
"""
from __future__ import annotations

import numpy as np

from vector_os_nano.core.types import Pose3D


def remove_depth_outliers(points: np.ndarray) -> np.ndarray:
    """Remove depth outliers using IQR on the Z axis.

    Mask edges produce depth bleed — points far behind or in front of the
    actual object surface. IQR filtering removes these. Returns the input
    unchanged when there are too few points or the spread is degenerate.
    """
    if len(points) < 10:
        return points
    z = points[:, 2]
    q1, q3 = np.percentile(z, [25, 75])
    iqr = q3 - q1
    if iqr < 1e-6:
        return points
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (z >= lower) & (z <= upper)
    filtered = points[mask]
    return filtered if len(filtered) >= 4 else points


def robust_centroid(points: np.ndarray) -> Pose3D:
    """Centroid via a 10% trimmed mean per axis (median fallback for < 10 pts).

    More robust than median or mean: mean is outlier-sensitive, median ignores
    density, the trimmed mean removes the 10% extremes and averages the rest.
    """
    if len(points) < 10:
        c = np.median(points, axis=0)
        return Pose3D(x=float(c[0]), y=float(c[1]), z=float(c[2]))

    trim_frac = 0.10
    n = len(points)
    trim_n = max(1, int(n * trim_frac))

    cx, cy, cz = 0.0, 0.0, 0.0
    for axis in range(3):
        sorted_vals = np.sort(points[:, axis])
        trimmed = sorted_vals[trim_n: n - trim_n]
        if len(trimmed) == 0:
            trimmed = sorted_vals
        val = float(np.mean(trimmed))
        if axis == 0:
            cx = val
        elif axis == 1:
            cy = val
        else:
            cz = val

    return Pose3D(x=cx, y=cy, z=cz)
