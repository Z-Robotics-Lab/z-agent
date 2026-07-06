# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Region helper for place-step verification.

Builds a placed_count region box around a place target XY.  The box is used
as the argument to placed_count(region) so the orchestrator can verify the
PLACE step with a grounded predicate:

    placed_count((x_min, y_min, x_max, y_max)) >= 1

Usage example::

    from zeno.skills.utils.place_region import region_around
    region = region_around((10.60, 2.70))
    # -> (10.45, 2.55, 10.75, 2.85)

The ``half`` parameter is the half-width/half-height of the box in metres.
The default (0.15 m) is calibrated for the observed landing scatter of
PlaceTopDownSkill at the floor-level corridor target (empirically: drop lands
within ~0.05 m of the commanded XY; 0.15 m gives a comfortable margin).
"""
from __future__ import annotations

import math


def region_around(
    xy: tuple[float, float],
    half: float = 0.15,
) -> tuple[float, float, float, float]:
    """Return a placed_count region box centred on *xy*.

    The box is axis-aligned in the XY plane:
        (x - half, y - half, x + half, y + half)

    Args:
        xy:   Centre of the region (x, y) in world metres.  Both coordinates
              must be finite (not NaN or inf).
        half: Half-width and half-height of the box in metres.  Must be > 0.

    Returns:
        (x_min, y_min, x_max, y_max) as a 4-tuple of floats.

    Raises:
        ValueError: If *half* <= 0 or either coordinate of *xy* is non-finite.
    """
    if half <= 0.0:
        raise ValueError(f"half must be > 0; got {half!r}")
    x, y = float(xy[0]), float(xy[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError(
            f"xy coordinates must be finite (not NaN or inf); got ({x!r}, {y!r})"
        )
    return (x - half, y - half, x + half, y + half)
