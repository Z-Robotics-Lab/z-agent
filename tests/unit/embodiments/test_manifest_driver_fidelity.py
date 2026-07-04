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

import ast
from pathlib import Path

import pytest

from vector_os_nano.embodiments import load_embodiment_config

# Repo root, four parents up from tests/unit/embodiments/<this file>.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _read_module_float_const(path: Path, name: str) -> float:
    """Return the float value of a top-level ``name = <number>`` assignment.

    Reads the value by parsing the source with :mod:`ast` — the module is NEVER
    imported, so a module that pulls ROS2 / a sim binding at import time (e.g. the
    vnav bridge) can still have its plain literal constants asserted in a
    ROS2-free, sim-free unit test. Fails loudly if the constant is missing or is
    not a numeric literal, so a rename can never silently disable the guard.
    """
    if not path.exists():
        raise AssertionError(f"expected source file not found: {path}")
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, ast.Assign):
            targets = list(node.targets)
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
                return float(value.value)
            raise AssertionError(f"{name} in {path.name} is not a numeric literal")
    raise AssertionError(f"{name} not found as a top-level constant in {path.name}")

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


def test_go2_lidar_offset_matches_driver() -> None:
    """Manifest lidar mount offset mirrors _LIDAR_OFFSET_X / _LIDAR_OFFSET_Z.

    The go2 manifest ``pos: [0.3, 0.0, 0.2]`` header names
    ``_LIDAR_OFFSET_X / _LIDAR_OFFSET_Z`` as its source, and the vnav bridge's
    ``_SENSOR_X/_SENSOR_Z`` claim the same numbers ("Must match mujoco_go2.py
    _LIDAR_OFFSET"). Yet the E148 g1 lidar-offset guard had NO go2 counterpart —
    the go2 consts were METHOD-LOCAL to ``_update_lidar`` and unimportable, so a
    drift would silently make both the manifest and the bridge advertise a beam
    origin the driver no longer casts from. Hoisting them to module scope makes
    this mirror guardable, symmetric with g1.
    """
    lidar = next(s for s in load_embodiment_config("go2").sensors if s.role == "lidar")
    assert lidar.pos[0] == pytest.approx(go2._LIDAR_OFFSET_X)
    assert lidar.pos[2] == pytest.approx(go2._LIDAR_OFFSET_Z)


def test_go2_vnav_bridge_sensor_offset_matches_driver() -> None:
    """The vnav bridge's _SENSOR_X/_SENSOR_Z mirror the driver's lidar offset.

    ``scripts/go2_vnav_bridge.py`` publishes the lidar point-cloud at
    ``_SENSOR_X/_SENSOR_Y/_SENSOR_Z`` with a comment "Must match mujoco_go2.py
    _LIDAR_OFFSET". This is a THIRD downstream mirror of the driver const (after
    the manifest, guarded above) and the last one E149 left comment-pinned only:
    a drifted driver ``_LIDAR_OFFSET`` would make the bridge advertise the SLAM
    point-cloud from an origin the driver no longer casts from, silently, with no
    red test. The bridge imports rclpy + MuJoCoGo2 at module load, so we read its
    literals with ast (no import), keeping the guard ROS2-free and sim-free.
    """
    bridge = _REPO_ROOT / "scripts" / "go2_vnav_bridge.py"
    assert _read_module_float_const(bridge, "_SENSOR_X") == pytest.approx(
        go2._LIDAR_OFFSET_X
    )
    assert _read_module_float_const(bridge, "_SENSOR_Z") == pytest.approx(
        go2._LIDAR_OFFSET_Z
    )


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


def test_g1_spawn_matches_driver_constants() -> None:
    """Manifest spawn pose mirrors the driver's authoritative spawn/height consts.

    The g1 manifest ``spawn`` header names _G1_SPAWN_X/_G1_SPAWN_Y/_G1_PELVIS_Z as
    its source; drift either driver const and connect() would place the humanoid
    somewhere the manifest no longer describes, with no test to catch it.
    """
    spawn = load_embodiment_config("g1").spawn
    assert spawn.xy[0] == pytest.approx(g1._G1_SPAWN_X)
    assert spawn.xy[1] == pytest.approx(g1._G1_SPAWN_Y)
    assert spawn.base_height == pytest.approx(g1._G1_PELVIS_Z)


def test_g1_lidar_offset_matches_driver() -> None:
    """Manifest lidar mount offset mirrors _LIDAR_OFFSET_X / _LIDAR_OFFSET_Z.

    The offset (pelvis-relative) sets where the beams originate; a silent drift
    would make the manifest advertise a head-height sensor the driver no longer
    mounts there.
    """
    lidar = next(s for s in load_embodiment_config("g1").sensors if s.role == "lidar")
    assert lidar.pos[0] == pytest.approx(g1._LIDAR_OFFSET_X)
    assert lidar.pos[2] == pytest.approx(g1._LIDAR_OFFSET_Z)


def test_g1_policy_action_scale_and_nav_speed_match_driver() -> None:
    """Manifest policy scalars E147 left uncovered — action_scale and nav_speed.

    Both name a driver const in the manifest (``_ACTION_SCALE`` / ``_NAV_SPEED``)
    yet the E147 policy-scalar guard checked neither, so a drifted RL action gain
    or nav command speed would pass every existing test while the manifest lies.
    """
    spec = load_embodiment_config("g1").policy.spec
    assert spec["action_scale"] == pytest.approx(g1._ACTION_SCALE)
    assert spec["nav_speed"] == pytest.approx(g1._NAV_SPEED)
