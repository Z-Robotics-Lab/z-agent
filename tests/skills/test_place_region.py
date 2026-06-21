# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for place_region.region_around — TDD RED phase.

Written BEFORE the implementation. All tests should fail with ImportError
until region_around is added to vector_os_nano/skills/utils/place_region.py.
"""
from __future__ import annotations

import math

import pytest

from vector_os_nano.skills.utils.place_region import region_around


# ---------------------------------------------------------------------------
# Test 1 — Correct box for a sample XY, default half=0.15
# ---------------------------------------------------------------------------


def test_region_around_default_half_correct_box() -> None:
    """region_around((10.60, 2.70)) should return (10.45, 2.55, 10.75, 2.85)."""
    box = region_around((10.60, 2.70))
    x_min, y_min, x_max, y_max = box
    assert x_min == pytest.approx(10.45, abs=1e-9)
    assert y_min == pytest.approx(2.55, abs=1e-9)
    assert x_max == pytest.approx(10.75, abs=1e-9)
    assert y_max == pytest.approx(2.85, abs=1e-9)


# ---------------------------------------------------------------------------
# Test 2 — Custom half value
# ---------------------------------------------------------------------------


def test_region_around_custom_half() -> None:
    """region_around((1.0, 2.0), half=0.5) returns (0.5, 1.5, 1.5, 2.5)."""
    box = region_around((1.0, 2.0), half=0.5)
    x_min, y_min, x_max, y_max = box
    assert x_min == pytest.approx(0.5, abs=1e-9)
    assert y_min == pytest.approx(1.5, abs=1e-9)
    assert x_max == pytest.approx(1.5, abs=1e-9)
    assert y_max == pytest.approx(2.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Test 3 — Symmetry: x_max - x_min == 2*half, y_max - y_min == 2*half
# ---------------------------------------------------------------------------


def test_region_around_symmetry() -> None:
    """The box is always exactly 2*half wide in each axis."""
    for half in (0.05, 0.15, 1.0):
        box = region_around((3.14, -2.71), half=half)
        x_min, y_min, x_max, y_max = box
        assert (x_max - x_min) == pytest.approx(2 * half, abs=1e-9)
        assert (y_max - y_min) == pytest.approx(2 * half, abs=1e-9)


# ---------------------------------------------------------------------------
# Test 4 — ValueError on half <= 0
# ---------------------------------------------------------------------------


def test_region_around_raises_on_zero_half() -> None:
    with pytest.raises(ValueError, match="half"):
        region_around((0.0, 0.0), half=0.0)


def test_region_around_raises_on_negative_half() -> None:
    with pytest.raises(ValueError, match="half"):
        region_around((1.0, 1.0), half=-0.1)


# ---------------------------------------------------------------------------
# Test 5 — ValueError on non-finite xy (nan)
# ---------------------------------------------------------------------------


def test_region_around_raises_on_nan_xy() -> None:
    with pytest.raises(ValueError, match="finite"):
        region_around((math.nan, 1.0))


# ---------------------------------------------------------------------------
# Test 6 — ValueError on non-finite xy (inf)
# ---------------------------------------------------------------------------


def test_region_around_raises_on_inf_xy() -> None:
    with pytest.raises(ValueError, match="finite"):
        region_around((1.0, math.inf))
