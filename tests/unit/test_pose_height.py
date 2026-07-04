# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: deterministic root-height pose oracle (R319/E110).

Companion to pose_upright. E109 proved orientation reads 3/3 of the R316 fault topologies from the
sim root QUAT — but a go2 sunk THROUGH the floor keeps an upright orientation (cosine ~ +1) and only
its root-z betrays the fault. minicpm SPLIT that exact `sunk_floor` frame by framing (STANDING under
neutral framing, FALLEN under fault framing — E108), i.e. no robust VLM read. This oracle asks the
HEIGHT question of ground truth instead — the sim root-z, which the actor cannot author (Invariant 1):
`height_dev` = root_z - stance_z (signed meters), `classify` bands it into SUNK / NOMINAL / AIRBORNE.
Pure math, no sim, no network. Together, orientation(E109) + height(this) read ALL 4 R316 faults.
"""
import importlib.util
import math
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "pose_height", Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "pose_height.py"
)
pose_height = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pose_height)

STANCE_Z = 0.35                       # mujoco_go2.py:397 keyframe qpos z / :1273 standing height
SUNK_FLOOR_Z = max(STANCE_Z - 0.28, -0.05)  # var/evidence/R316/render_poses.py:69 -> 0.07


class TestHeightDev:
    def test_at_stance_is_zero(self):
        assert pose_height.height_dev(STANCE_Z, STANCE_Z) == 0.0

    def test_sunk_floor_is_negative(self):
        # the R316 sunk-through-floor case: ~0.28 m below stance
        assert math.isclose(pose_height.height_dev(SUNK_FLOOR_Z, STANCE_Z), -0.28, abs_tol=1e-9)

    def test_airborne_is_positive(self):
        assert math.isclose(pose_height.height_dev(0.60, STANCE_Z), 0.25, abs_tol=1e-9)

    def test_default_stance_z(self):
        # stance_z defaults to the go2 keyframe height so a lone root_z classifies
        assert math.isclose(pose_height.height_dev(0.35), 0.0, abs_tol=1e-9)

    def test_nan_root_z_raises(self):
        # sensor floor: reject NaN before it becomes a false verdict (never silently pass)
        try:
            pose_height.height_dev(float("nan"), STANCE_Z)
        except ValueError:
            return
        raise AssertionError("a NaN root_z must fail loud, not classify")

    def test_inf_root_z_raises(self):
        try:
            pose_height.height_dev(float("inf"), STANCE_Z)
        except ValueError:
            return
        raise AssertionError("an infinite root_z must fail loud")

    def test_nonpositive_stance_z_raises(self):
        try:
            pose_height.height_dev(0.35, 0.0)
        except ValueError:
            return
        raise AssertionError("a non-positive stance height is nonsense and must fail loud")


class TestClassify:
    def test_stance_is_nominal(self):
        assert pose_height.classify(STANCE_Z, STANCE_Z) == "NOMINAL"

    def test_sunk_floor_is_sunk(self):
        # THE headline: deterministic SUNK where minicpm split STANDING/FALLEN by framing (E108),
        # and where orientation alone reads STANDING (cosine ~ +1) — height is the ONLY witness.
        assert pose_height.classify(SUNK_FLOOR_Z, STANCE_Z) == "SUNK"

    def test_airborne_is_airborne(self):
        assert pose_height.classify(0.70, STANCE_Z) == "AIRBORNE"

    def test_crouch_within_tolerance_is_nominal(self):
        # a standing go2 bobs/crouches; a small dip must NOT read as a fault
        assert pose_height.classify(STANCE_Z - 0.08, STANCE_Z) == "NOMINAL"

    def test_tolerance_is_configurable(self):
        # default tol 0.12 m; a 0.15 m dip is SUNK at the default but NOMINAL at a looser tol
        assert pose_height.classify(STANCE_Z - 0.15, STANCE_Z) == "SUNK"
        assert pose_height.classify(STANCE_Z - 0.15, STANCE_Z, tol=0.20) == "NOMINAL"

    def test_negative_tolerance_raises(self):
        try:
            pose_height.classify(STANCE_Z, STANCE_Z, tol=-0.01)
        except ValueError:
            return
        raise AssertionError("a negative tolerance is nonsense and must fail loud")
