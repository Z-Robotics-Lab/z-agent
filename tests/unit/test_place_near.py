# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: deterministic relational proximity oracle (R321/E112).

The placement geometry that is ALREADY deterministic is ABSOLUTE-region containment
(make_placed_count / make_resting_on_receptacle, D106): "is the object inside this box".
The one placement flavor with NO deterministic channel is RELATIONAL — "put A NEAR B",
"the bottle next to the box" — which today only the VLM judge grades. But the GEOMETRY of
"near" is exactly the wrong job for a VLM (Invariant 1): the two objects' world positions
are ground truth the actor cannot author, so distance-to-a-radius is a hard channel. This
oracle grades that half; the VLM shrinks to the IDENTITY half (which object is "the box").

`separation` = Euclidean distance between two positions (planar=xy for ground-plane
"next to", full=xyz); `proximity_margin` = radius - separation (signed meters, +inside like
pose_height's dev); `classify` bands it NEAR / FAR. Pure math, no sim, no network.
"""
import importlib.util
import math
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "place_near", Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "place_near.py"
)
place_near = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(place_near)


class TestSeparation:
    def test_identical_positions_is_zero(self):
        assert place_near.separation((1.0, 2.0, 0.3), (1.0, 2.0, 0.3)) == 0.0

    def test_planar_ignores_z(self):
        # a 3-4-5 triangle in xy; a large z gap must NOT change the planar distance
        d = place_near.separation((0.0, 0.0, 0.0), (3.0, 4.0, 99.0), planar=True)
        assert math.isclose(d, 5.0, abs_tol=1e-9)

    def test_full_includes_z(self):
        # full xyz: legs 3,4 (=5 in-plane) then 12 in z -> 13 (a 5-12-13 triangle)
        d = place_near.separation((0.0, 0.0, 0.0), (3.0, 4.0, 12.0), planar=False)
        assert math.isclose(d, 13.0, abs_tol=1e-9)

    def test_two_component_positions_allowed(self):
        # a caller may pass bare (x, y); planar distance must still work
        assert math.isclose(place_near.separation((0.0, 0.0), (0.6, 0.8)), 1.0, abs_tol=1e-9)

    def test_nan_coord_raises(self):
        # sensor floor: a NaN position must fail loud, never become a false NEAR/FAR
        try:
            place_near.separation((0.0, 0.0, float("nan")), (1.0, 1.0, 1.0), planar=False)
        except ValueError:
            return
        raise AssertionError("a NaN coordinate must fail loud, not classify")

    def test_inf_coord_raises(self):
        try:
            place_near.separation((float("inf"), 0.0), (1.0, 1.0))
        except ValueError:
            return
        raise AssertionError("an infinite coordinate must fail loud")

    def test_too_few_components_raises(self):
        # a degenerate 1-D position is malformed; never silently pad it
        try:
            place_near.separation((1.0,), (2.0,))
        except ValueError:
            return
        raise AssertionError("a <2-component position must fail loud")

    def test_full_needs_z_component(self):
        # full=xyz but a 2-component position has no z -> malformed, fail loud
        try:
            place_near.separation((0.0, 0.0), (1.0, 1.0), planar=False)
        except ValueError:
            return
        raise AssertionError("planar=False on a 2-component position must fail loud")


class TestProximityMargin:
    def test_positive_inside_radius(self):
        # 0.6 m apart, 1.0 m radius -> +0.4 m of slack (positive = comfortably NEAR)
        m = place_near.proximity_margin((0.0, 0.0), (0.6, 0.0), 1.0)
        assert math.isclose(m, 0.4, abs_tol=1e-9)

    def test_negative_outside_radius(self):
        # 1.5 m apart, 1.0 m radius -> -0.5 m (negative = FAR by that much)
        m = place_near.proximity_margin((0.0, 0.0), (1.5, 0.0), 1.0)
        assert math.isclose(m, -0.5, abs_tol=1e-9)

    def test_zero_at_boundary(self):
        m = place_near.proximity_margin((0.0, 0.0), (1.0, 0.0), 1.0)
        assert math.isclose(m, 0.0, abs_tol=1e-9)


class TestClassify:
    def test_within_radius_is_near(self):
        assert place_near.classify((0.0, 0.0), (0.3, 0.0), radius=0.5) == "NEAR"

    def test_beyond_radius_is_far(self):
        assert place_near.classify((0.0, 0.0), (2.0, 0.0), radius=0.5) == "FAR"

    def test_exactly_at_radius_is_near(self):
        # boundary is inclusive (<=): a placement resting exactly at the edge still counts NEAR
        assert place_near.classify((0.0, 0.0), (0.5, 0.0), radius=0.5) == "NEAR"

    def test_planar_near_but_full_far_when_stacked(self):
        # THE relational headline: B directly ABOVE A reads NEAR in-plane ("next to" on the
        # ground) yet FAR in full xyz — the two questions are genuinely different, and the
        # caller chooses which "near" the task means. A VLM cannot disambiguate this reliably.
        a, b = (1.0, 1.0, 0.05), (1.0, 1.0, 2.0)
        assert place_near.classify(a, b, radius=0.5, planar=True) == "NEAR"
        assert place_near.classify(a, b, radius=0.5, planar=False) == "FAR"

    def test_default_radius(self):
        # a documented default exists for CLI ergonomics; the rubric/caller owns the real value
        assert place_near.DEFAULT_RADIUS == 0.5

    def test_nonpositive_radius_raises(self):
        # a zero/negative proximity radius is nonsense and must fail loud (never a vacuous FAR)
        for bad in (0.0, -0.3):
            try:
                place_near.classify((0.0, 0.0), (0.1, 0.0), radius=bad)
            except ValueError:
                continue
            raise AssertionError(f"radius={bad} must fail loud")

    def test_nonfinite_radius_raises(self):
        for bad in (float("nan"), float("inf")):
            try:
                place_near.classify((0.0, 0.0), (0.1, 0.0), radius=bad)
            except ValueError:
                continue
            raise AssertionError(f"radius={bad} must fail loud")
