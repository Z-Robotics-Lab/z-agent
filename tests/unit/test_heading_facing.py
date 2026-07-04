# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: deterministic heading/facing oracle (R322/E113).

The FOURTH deterministic hard channel, after pose_upright (own orientation, E109),
pose_height (own height, E110) and place_near (object-to-object proximity, E112). Those
grade WHERE bodies are and how a single body is oriented; none grades whether a robot is
turned TOWARD a target — the "go to / face the red thing" (VLN) acceptance question that E14
left to no deterministic channel and a local VLM cannot read reliably (foreshortening hides
heading). Invariant 1: the robot's world yaw and the target's world position are ground truth
the actor cannot author, so "is the heading pointed at the target" is a hard channel.

`yaw_from_quat` extracts world-z yaw from a MuJoCo (w,x,y,z) root quaternion; `bearing_to`
is the world angle from robot to target; `heading_error` is the signed smallest angle between
the two (wrapped to [-pi, pi]); `facing_margin` = tol - |error| (signed, +inside like
pose_height's dev); `classify` bands it FACING / AWAY. Orthogonal to distance: a robot can be
FACING a far target or AWAY from a near one — this composes with place_near, never duplicates
it. Pure math, no sim, no network.
"""
import importlib.util
import math
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "heading_facing",
    Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "heading_facing.py",
)
heading_facing = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(heading_facing)


class TestYawFromQuat:
    def test_identity_is_zero_yaw(self):
        assert math.isclose(heading_facing.yaw_from_quat((1.0, 0.0, 0.0, 0.0)), 0.0, abs_tol=1e-9)

    def test_ninety_deg_about_z(self):
        # a +90deg rotation about world-z: quat = (cos45, 0, 0, sin45)
        c = math.cos(math.pi / 4)
        yaw = heading_facing.yaw_from_quat((c, 0.0, 0.0, c))
        assert math.isclose(yaw, math.pi / 2, abs_tol=1e-9)

    def test_one_eighty_about_z(self):
        yaw = heading_facing.yaw_from_quat((0.0, 0.0, 0.0, 1.0))
        assert math.isclose(abs(yaw), math.pi, abs_tol=1e-9)

    def test_unnormalized_quat_still_works(self):
        # a scaled 90deg-about-z quaternion must yield the same yaw (yaw is scale-invariant)
        c = math.cos(math.pi / 4)
        yaw = heading_facing.yaw_from_quat((5.0 * c, 0.0, 0.0, 5.0 * c))
        assert math.isclose(yaw, math.pi / 2, abs_tol=1e-9)

    def test_roll_pitch_do_not_leak_into_yaw(self):
        # a pure 90deg roll about x (quat = (cos45, sin45, 0, 0)) has zero yaw
        c = math.cos(math.pi / 4)
        assert math.isclose(heading_facing.yaw_from_quat((c, c, 0.0, 0.0)), 0.0, abs_tol=1e-9)

    def test_zero_quat_raises(self):
        try:
            heading_facing.yaw_from_quat((0.0, 0.0, 0.0, 0.0))
        except ValueError:
            return
        raise AssertionError("a degenerate zero quaternion must fail loud")


class TestBearingTo:
    def test_target_due_plus_x_is_zero(self):
        assert math.isclose(heading_facing.bearing_to((0.0, 0.0), (1.0, 0.0)), 0.0, abs_tol=1e-9)

    def test_target_due_plus_y_is_half_pi(self):
        assert math.isclose(heading_facing.bearing_to((0.0, 0.0), (0.0, 1.0)), math.pi / 2, abs_tol=1e-9)

    def test_target_due_minus_x_is_pi(self):
        assert math.isclose(abs(heading_facing.bearing_to((0.0, 0.0), (-1.0, 0.0))), math.pi, abs_tol=1e-9)

    def test_bearing_ignores_z(self):
        # bearing is a ground-plane angle; a z difference must not change it
        b = heading_facing.bearing_to((0.0, 0.0, 0.3), (1.0, 0.0, 5.0))
        assert math.isclose(b, 0.0, abs_tol=1e-9)

    def test_coincident_xy_raises(self):
        # robot exactly on the target: the bearing is undefined -> fail loud, never a false verdict
        try:
            heading_facing.bearing_to((2.0, 3.0), (2.0, 3.0))
        except ValueError:
            return
        raise AssertionError("a coincident robot/target must fail loud (undefined bearing)")

    def test_nan_coord_raises(self):
        try:
            heading_facing.bearing_to((0.0, float("nan")), (1.0, 1.0))
        except ValueError:
            return
        raise AssertionError("a NaN coordinate must fail loud")


class TestHeadingError:
    def test_facing_target_is_zero_error(self):
        # robot yaw 0 (pointing +x), target due +x -> exactly aligned
        e = heading_facing.heading_error(0.0, (0.0, 0.0), (1.0, 0.0))
        assert math.isclose(e, 0.0, abs_tol=1e-9)

    def test_ninety_off_to_the_left(self):
        # robot pointing +x, target due +y -> +90deg to correct
        e = heading_facing.heading_error(0.0, (0.0, 0.0), (0.0, 1.0))
        assert math.isclose(e, math.pi / 2, abs_tol=1e-9)

    def test_error_wraps_to_shortest_arc(self):
        # robot yaw ~+pi, target bearing ~-pi: the naive diff is ~-2pi but the true error is small
        e = heading_facing.heading_error(3.0, (0.0, 0.0), (math.cos(-3.0), math.sin(-3.0)))
        assert abs(e) < 0.6  # ~0.283 rad, NOT ~2pi
        assert math.isclose(abs(e), 2 * math.pi - 6.0, abs_tol=1e-9)

    def test_error_is_signed(self):
        # target to the right (bearing -90deg) with yaw 0 -> negative error
        e = heading_facing.heading_error(0.0, (0.0, 0.0), (0.0, -1.0))
        assert math.isclose(e, -math.pi / 2, abs_tol=1e-9)


class TestClassify:
    def test_aligned_is_facing(self):
        assert heading_facing.classify(0.0, (0.0, 0.0), (1.0, 0.0)) == "FACING"

    def test_ninety_off_is_away_with_default_tol(self):
        # 90deg off, default tol 45deg -> AWAY
        assert heading_facing.classify(0.0, (0.0, 0.0), (0.0, 1.0)) == "AWAY"

    def test_exactly_at_tol_is_facing(self):
        # boundary inclusive: an error of exactly tol still counts FACING
        v = heading_facing.classify(0.0, (0.0, 0.0), (math.cos(math.pi / 4), math.sin(math.pi / 4)),
                                    tol_deg=45.0)
        assert v == "FACING"

    def test_facing_is_distance_orthogonal(self):
        # THE composition headline: facing depends ONLY on orientation, not distance. The SAME
        # heading reads FACING to a target 100m away and to one 0.1m away -> this channel is
        # orthogonal to place_near (which is translation-only), so the two compose to grade
        # "approached AND oriented toward" without either duplicating the other.
        assert heading_facing.classify(0.0, (0.0, 0.0), (100.0, 0.0)) == "FACING"
        assert heading_facing.classify(0.0, (0.0, 0.0), (0.1, 0.0)) == "FACING"
        # ...and being NEAR a target you are turned AWAY from is honestly AWAY
        assert heading_facing.classify(0.0, (0.0, 0.0), (-0.1, 0.0)) == "AWAY"

    def test_default_tol(self):
        assert heading_facing.DEFAULT_TOL_DEG == 45.0

    def test_nonpositive_tol_raises(self):
        for bad in (0.0, -10.0):
            try:
                heading_facing.classify(0.0, (0.0, 0.0), (1.0, 0.0), tol_deg=bad)
            except ValueError:
                continue
            raise AssertionError(f"tol_deg={bad} must fail loud")

    def test_over_180_tol_raises(self):
        # a tolerance above 180deg would make EVERY heading FACING (vacuous) -> fail loud
        try:
            heading_facing.classify(0.0, (0.0, 0.0), (1.0, 0.0), tol_deg=181.0)
        except ValueError:
            return
        raise AssertionError("tol_deg>180 must fail loud (vacuous FACING)")

    def test_nonfinite_tol_raises(self):
        for bad in (float("nan"), float("inf")):
            try:
                heading_facing.classify(0.0, (0.0, 0.0), (1.0, 0.0), tol_deg=bad)
            except ValueError:
                continue
            raise AssertionError(f"tol_deg={bad} must fail loud")


class TestFacingMargin:
    def test_positive_inside_tol(self):
        # 0deg error, 45deg tol -> +45deg of slack
        m = heading_facing.facing_margin(0.0, (0.0, 0.0), (1.0, 0.0), tol_deg=45.0)
        assert math.isclose(m, 45.0, abs_tol=1e-9)

    def test_negative_outside_tol(self):
        # 90deg error, 45deg tol -> -45deg (AWAY by that much)
        m = heading_facing.facing_margin(0.0, (0.0, 0.0), (0.0, 1.0), tol_deg=45.0)
        assert math.isclose(m, -45.0, abs_tol=1e-9)

    def test_zero_at_boundary(self):
        m = heading_facing.facing_margin(0.0, (0.0, 0.0), (math.cos(math.pi / 4), math.sin(math.pi / 4)),
                                         tol_deg=45.0)
        assert math.isclose(m, 0.0, abs_tol=1e-7)


class TestClassifyFromQuat:
    def test_quat_heading_faces_target(self):
        # robot at origin with identity quat (facing +x), target due +x -> FACING
        assert heading_facing.classify_quat((1.0, 0.0, 0.0, 0.0), (0.0, 0.0), (1.0, 0.0)) == "FACING"

    def test_quat_turned_away_is_away(self):
        # same identity heading (+x) but target is behind (-x) -> AWAY
        assert heading_facing.classify_quat((1.0, 0.0, 0.0, 0.0), (0.0, 0.0), (-1.0, 0.0)) == "AWAY"

    def test_quat_turned_toward_target_is_facing(self):
        # robot rotated +90deg about z now faces +y; a +y target -> FACING
        c = math.cos(math.pi / 4)
        assert heading_facing.classify_quat((c, 0.0, 0.0, c), (0.0, 0.0), (0.0, 5.0)) == "FACING"
