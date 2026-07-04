# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Drift guards: each embodiment manifest value MUST equal the driver constant
it claims to mirror.

Both ``robot.yaml`` manifests carry a standing promise in their header —
"Values must stay ACCURATE to today's driver" (Stage 1 mirrors constants the
per-robot driver still hardcodes; Stage 2 will make the driver READ them). Until
Stage 2 lands, the manifest and the driver hold the SAME number in two places,
and the only thing keeping them in sync is a comment.

``test_embodiment_config.py`` asserts each manifest value against a literal
copied INTO that test — so it catches a bad edit to the YAML, but NOT a driver
constant that drifts away from the manifest (change ``_MPC_Z_DES`` and every
test there still passes while the manifest silently lies).

This module closes that gap: it imports the driver's AUTHORITATIVE module-level
constant and asserts the manifest mirrors it. When Stage 2 wires the driver to
read the manifest, a silently-drifted value would have made the robot behave
wrong on the sim face; these guards make that drift a red unit test instead.

Offline + memory-safe: importing the driver modules loads the ``mujoco`` binding
but launches NO sim (no ``MjModel`` is built, no process spawned). If ``mujoco``
is absent the driver import is skipped, never a false red.
"""
from __future__ import annotations

import pytest

from vector_os_nano.embodiments import load_embodiment_config

# The drivers import the ``mujoco`` python binding at module load. That is a
# cheap, sim-free import; skip cleanly if the binding is unavailable so the guard
# never turns into an environment false-positive.
go2 = pytest.importorskip(
    "vector_os_nano.hardware.sim.mujoco_go2",
    reason="mujoco binding required to read the go2 driver's authoritative constants",
)
g1 = pytest.importorskip(
    "vector_os_nano.hardware.sim.mujoco_g1",
    reason="mujoco binding required to read the g1 driver's authoritative constants",
)


# ---------------------------------------------------------------------------
# go2 quadruped — manifest mirrors mujoco_go2 module constants
# ---------------------------------------------------------------------------


def test_go2_policy_scalars_match_driver() -> None:
    """policy.spec numbers must equal the driver's authoritative constants."""
    spec = load_embodiment_config("go2").policy.spec
    assert spec["mpc_z_des"] == pytest.approx(go2._MPC_Z_DES)
    assert spec["mpc_gait_hz"] == go2._MPC_GAIT_HZ
    assert spec["mpc_gait_duty"] == pytest.approx(go2._MPC_GAIT_DUTY)
    assert spec["vx_max"] == pytest.approx(go2._VX_MAX)
    assert spec["vy_max"] == pytest.approx(go2._VY_MAX)
    assert spec["vyaw_max"] == pytest.approx(go2._VYAW_MAX)
    assert spec["sim_hz"] == go2._SIM_HZ
    assert spec["ctrl_hz"] == go2._CTRL_HZ


def test_go2_stance_matches_stand_joints_constant() -> None:
    """Every leg's (hip, thigh, calf) must equal the driver's _STAND_JOINTS triple."""
    stance = load_embodiment_config("go2").stance
    hip, thigh, calf = go2._STAND_JOINTS[0], go2._STAND_JOINTS[1], go2._STAND_JOINTS[2]
    for leg in ("FL", "FR", "RL", "RR"):
        assert stance[f"{leg}_hip"] == pytest.approx(hip), leg
        assert stance[f"{leg}_thigh"] == pytest.approx(thigh), leg
        assert stance[f"{leg}_calf"] == pytest.approx(calf), leg


def test_go2_lidar_update_interval_matches_driver() -> None:
    lidar = next(s for s in load_embodiment_config("go2").sensors if s.role == "lidar")
    assert lidar.params["update_interval_steps"] == go2._LIDAR_UPDATE_INTERVAL


# ---------------------------------------------------------------------------
# g1 humanoid — manifest mirrors mujoco_g1 module constants
# ---------------------------------------------------------------------------


def test_g1_policy_scalars_match_driver() -> None:
    spec = load_embodiment_config("g1").policy.spec
    assert spec["sim_dt"] == pytest.approx(g1._SIM_DT)
    assert spec["decimation"] == g1._DECIMATION
    assert spec["num_obs"] == g1._NUM_OBS
    assert spec["num_actions"] == g1._NUM_ACTIONS
    assert spec["gait_period"] == pytest.approx(g1._GAIT_PERIOD)
    assert spec["body_radius"] == pytest.approx(g1._G1_BODY_RADIUS)


# Manifest joint order, documented in g1/robot.yaml, mapping 1:1 onto the
# driver's _DEFAULT_ANGLES vector (left leg then right leg, 6 DoF each).
_G1_STANCE_ORDER: tuple[str, ...] = (
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
)


def test_g1_stance_matches_default_angles_constant() -> None:
    """Manifest stance, in the documented joint order, must equal _DEFAULT_ANGLES."""
    stance = load_embodiment_config("g1").stance
    default_angles = g1._DEFAULT_ANGLES
    assert len(_G1_STANCE_ORDER) == len(default_angles)
    for i, joint in enumerate(_G1_STANCE_ORDER):
        assert stance[joint] == pytest.approx(float(default_angles[i])), joint
