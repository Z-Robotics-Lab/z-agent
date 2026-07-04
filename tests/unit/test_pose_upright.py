# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: deterministic quat-upright pose oracle (R318/E109).

E105/E107/E108 exhausted the LOCAL-VLM pose lever: qwen is pose-blind, minicpm-v misses a
side-lying topple single-frame AND multi-view (a topology blind spot, not a view artifact).
This oracle asks the pose question of GROUND TRUTH instead — the sim root quaternion, which the
actor cannot author (Invariant 1). `upright_cosine` = world-up · (R(quat) · body-up) = the m22
entry of the rotation matrix; +1 = standing, 0 = on its side, -1 = on its back. Pure math, no sim,
no network. The SAME 4 R316/R317 world-rotations that fooled every VLM are unambiguous here.
"""
import importlib.util
import math
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "pose_upright", Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "pose_upright.py"
)
pose_upright = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pose_upright)

# The R316/R317 world-frame rotations, applied to an IDENTITY upright stance (w,x,y,z). With a
# real stance quat the composed quat differs but the cosine is ~equal (stance is ~upright); the
# var/evidence/R318 demo confirms it on the REAL wrapper stand() quat.
UPRIGHT = (1.0, 0.0, 0.0, 0.0)
YAW90 = (0.70710678, 0.0, 0.0, 0.70710678)          # 90deg about world-z: still standing
TOPPLED_BACK = (0.0, 1.0, 0.0, 0.0)                 # 180deg about world-x: onto its back
TOPPLED_SIDE_LEFT = (0.70710678, -0.70710678, 0.0, 0.0)  # 90deg about world-x: onto its side


class TestUprightCosine:
    def test_identity_is_fully_upright(self):
        assert pose_upright.upright_cosine(UPRIGHT) == 1.0

    def test_yaw_does_not_tip(self):
        # a heading change must NOT read as a fall (the E108 false-FALLEN failure mode)
        assert math.isclose(pose_upright.upright_cosine(YAW90), 1.0, abs_tol=1e-6)

    def test_back_topple_is_inverted(self):
        assert math.isclose(pose_upright.upright_cosine(TOPPLED_BACK), -1.0, abs_tol=1e-6)

    def test_side_topple_is_horizontal(self):
        # the exact pose minicpm read STANDING 3/3 in ALL 4 azimuths (E108) -> here it is ~0
        assert math.isclose(pose_upright.upright_cosine(TOPPLED_SIDE_LEFT), 0.0, abs_tol=1e-6)

    def test_normalizes_unnormalized_quat(self):
        # a doubled quat is the same rotation
        assert math.isclose(pose_upright.upright_cosine((2.0, 0.0, 0.0, 0.0)), 1.0, abs_tol=1e-6)

    def test_zero_quat_raises(self):
        try:
            pose_upright.upright_cosine((0.0, 0.0, 0.0, 0.0))
        except ValueError:
            return
        raise AssertionError("a zero quaternion must fail loud, not divide-by-zero")


class TestClassify:
    def test_standing(self):
        assert pose_upright.classify(UPRIGHT) == "STANDING"

    def test_yaw_still_standing(self):
        assert pose_upright.classify(YAW90) == "STANDING"

    def test_back_topple_fallen(self):
        assert pose_upright.classify(TOPPLED_BACK) == "FALLEN"

    def test_side_topple_fallen(self):
        # THE headline: deterministic where minicpm single-frame + multi-view both missed it
        assert pose_upright.classify(TOPPLED_SIDE_LEFT) == "FALLEN"

    def test_threshold_is_configurable(self):
        # default 0.5; a 60deg tilt (cos=0.5) sits on the boundary -> STANDING at 0.5, FALLEN above
        tilt60 = (math.cos(math.radians(30)), math.sin(math.radians(30)), 0.0, 0.0)  # 60deg about x
        assert math.isclose(pose_upright.upright_cosine(tilt60), 0.5, abs_tol=1e-6)
        assert pose_upright.classify(tilt60, thresh=0.4) == "STANDING"
        assert pose_upright.classify(tilt60, thresh=0.6) == "FALLEN"
