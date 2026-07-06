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

import numpy as np
import pytest

from zeno.embodiments import load_embodiment_config

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
    "zeno.hardware.sim.mujoco_go2",
    reason="mujoco binding required to read the go2 driver's authoritative constants",
)
g1 = pytest.importorskip(
    "zeno.hardware.sim.mujoco_g1",
    reason="mujoco binding required to read the g1 driver's authoritative constants",
)
piper = pytest.importorskip(
    "zeno.hardware.sim.mujoco_piper",
    reason="mujoco binding required to read the piper driver's authoritative constants",
)
piper_gripper = pytest.importorskip(
    "zeno.hardware.sim.mujoco_piper_gripper",
    reason="mujoco binding required to read the piper gripper driver's constant",
)
# The ROS2 proxy imports only numpy + stdlib at module load (rclpy is lazy), so it
# imports cleanly with or without the mujoco binding.
from zeno.hardware.sim import piper_ros2_proxy as piper_proxy  # noqa: E402


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


def test_piper_proxy_sensor_offset_matches_driver() -> None:
    """The piper ROS2 proxy's _BODY_SENSOR_DX/_DZ mirror the same lidar offset.

    ``piper_ros2_proxy.py`` reconstructs the body pose from ``/state_estimation``
    (published by the vnav bridge in sensor frame) inside ``_sync_ik_base`` by
    SUBTRACTING ``_BODY_SENSOR_DX/_BODY_SENSOR_DZ`` — a copy pinned by comment to
    "must match go2_vnav_bridge.py _SENSOR_X/_SENSOR_Z (0.3 m forward, 0.2 m up)".
    That makes it a FOURTH downstream mirror of the driver's authoritative
    ``_LIDAR_OFFSET`` (after the manifest and the bridge, both guarded above),
    and the one E149/E151 left comment-pinned only: a drifted offset would make
    the piper IK base land at the wrong body position and the arm reach the wrong
    place, silently, with no red test. The proxy has no ROS2 import at module
    load, but we read its literals with ast anyway — symmetric with the bridge
    guard and immune to any future import-time dependency.
    """
    proxy = _REPO_ROOT / "zeno" / "hardware" / "sim" / "piper_ros2_proxy.py"
    assert _read_module_float_const(proxy, "_BODY_SENSOR_DX") == pytest.approx(
        go2._LIDAR_OFFSET_X
    )
    assert _read_module_float_const(proxy, "_BODY_SENSOR_DZ") == pytest.approx(
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


# ---------------------------------------------------------------------------
# piper arm — the ROS2 proxy's constant block mirrors the in-process driver
# ---------------------------------------------------------------------------

# ``piper_ros2_proxy.py`` opens its constants with the standing promise
# "Constants (duplicate of MuJoCoPiper's — kept in sync)": the ROS2 proxy
# hardcodes its OWN copy of the driver's IK/joint/site constants so its
# blocking-IK path behaves identically to the in-process ``MuJoCoPiper``. The
# E158 guard covered only ``_BODY_SENSOR_DX/_DZ`` (a mirror of the go2 *lidar*
# offset, a different vein); the rest of the "kept in sync" block — joint names,
# EE site, every IK convergence scalar, the top-down rotation + seeds, the home
# pose, and the move rate — was pinned by comment ALONE. Drift any one (e.g.
# tighten the driver's ``_IK_POS_TOL`` for better grasps, or rename a joint in
# the MJCF and update only the driver) and the proxy would solve a DIFFERENT arm
# pose than the in-process sim it claims to mirror, silently, with no red test.
# Each tuple is (proxy attribute, authority module, authority attribute).
_PIPER_PROXY_MIRRORS: tuple[tuple[str, object, str], ...] = (
    ("_ARM_JOINT_NAMES", piper, "_ARM_JOINT_NAMES"),
    ("_EE_SITE_NAME", piper, "_EE_SITE_NAME"),
    ("_GRIPPER_JOINT_NAME", piper_gripper, "_JOINT_NAME"),
    ("_IK_MAX_ITER", piper, "_IK_MAX_ITER"),
    ("_IK_POS_TOL", piper, "_IK_POS_TOL"),
    ("_IK_ROT_TOL", piper, "_IK_ROT_TOL"),
    ("_IK_STEP_SIZE", piper, "_IK_STEP_SIZE"),
    ("_IK_DAMPING", piper, "_IK_DAMPING"),
    ("_R_TOP_DOWN", piper, "_R_TOP_DOWN"),
    ("_IK_TOP_DOWN_SEEDS", piper, "_IK_TOP_DOWN_SEEDS"),
    ("_HOME_JOINTS", piper, "_HOME_JOINTS"),
    ("_MOVE_UPDATE_HZ", piper, "_MOVE_UPDATE_HZ"),
)


def test_piper_proxy_constants_mirror_driver() -> None:
    """Every "kept in sync" proxy constant must equal its driver authority.

    Reads both live module attributes (both import ROS2-free / sim-free) and
    asserts equality, so a drift the E158 sensor-offset guard cannot see becomes
    a red unit test. Missing constants fail loudly, so a rename on either side
    can never silently disable the guard.
    """
    for proxy_name, authority_mod, authority_name in _PIPER_PROXY_MIRRORS:
        assert hasattr(piper_proxy, proxy_name), f"proxy lost {proxy_name}"
        assert hasattr(authority_mod, authority_name), (
            f"authority {authority_mod.__name__} lost {authority_name}"
        )
        got = getattr(piper_proxy, proxy_name)
        want = getattr(authority_mod, authority_name)
        if isinstance(want, np.ndarray) or isinstance(got, np.ndarray):
            assert np.array_equal(np.asarray(got), np.asarray(want)), proxy_name
        else:
            assert got == want, proxy_name


# ---------------------------------------------------------------------------
# SO-101 home-pose value chain (Inv-1 verify moat).
#
# The home pose is the SO-101 rest configuration, copied into several
# module-level literals: the config default (the RUNTIME AUTHORITY the home
# skill actually commands via context.config["skills"]["home"]["joint_values"],
# falling back to the skill literal only when a user omits the key), the verify
# oracle ``arm_sim_oracle._HOME_JOINTS`` (what ``arm_at_home()`` grades against —
# the moat), and four skill fallbacks (``_DEFAULT_HOME_JOINTS`` in
# home/pick/place/handover).
#
# test_playground_predicates.py already pins oracle == home-fallback, but
# NOTHING pinned either to the config AUTHORITY: edit config's joint_values (the
# pose the arm truly goes to) without touching the fallback and the arm reaches a
# DIFFERENT pose than the oracle grades — a silent Inv-1 breach with no red test.
# test_config.py::test_default_home_joint_values checks only len/type, not the
# value. This guard pins every copy to the config authority.
#
# scan._DEFAULT_SCAN_JOINTS shares the value TODAY but is a DISTINCT semantic
# pose (scan != home) that may legitimately diverge, so it is deliberately
# EXCLUDED — pinning it would encode a false invariant.
# ---------------------------------------------------------------------------
_HOME_POSE_FALLBACK_MODULES: tuple[tuple[str, str], ...] = (
    ("zeno.skills.home", "_DEFAULT_HOME_JOINTS"),
    ("zeno.skills.pick", "_DEFAULT_HOME_JOINTS"),
    ("zeno.skills.place", "_DEFAULT_HOME_JOINTS"),
    ("zeno.skills.handover", "_DEFAULT_HOME_JOINTS"),
    # wave is the FIFTH skill that returns the arm home; E161 missed it because it
    # inlined the pose literal into its ``.get(..., [...])`` fallback instead of a
    # ``_DEFAULT_HOME_JOINTS`` constant like the other four. Made symmetric here so
    # the same guard pins it to the config authority (else a drifted default.yaml
    # leaves wave sending the arm to a pose the oracle no longer grades).
    ("zeno.skills.wave", "_DEFAULT_HOME_JOINTS"),
)


def test_so101_home_pose_chain_mirrors_config_authority() -> None:
    """Every SO-101 home-pose copy must equal the config runtime authority.

    The verify oracle grades ``arm_at_home()`` against ``_HOME_JOINTS``; the arm
    is actually commanded to ``config["skills"]["home"]["joint_values"]``. If the
    two drift the moat silently grades the wrong pose, so this pins the oracle AND
    the four skill fallbacks to the config authority. Missing attributes fail
    loudly, so a rename cannot silently disable the guard.
    """
    import importlib

    from zeno.core.config import load_config
    from zeno.vcli.worlds.arm_sim_oracle import _HOME_JOINTS as oracle_home

    authority = load_config()["skills"]["home"]["joint_values"]
    assert isinstance(authority, list) and authority, (
        "config lost the home joint_values authority"
    )

    # The moat: the oracle must grade against the pose the arm is truly commanded to.
    assert list(oracle_home) == list(authority), (
        "arm_sim_oracle._HOME_JOINTS drifted from the config home authority"
    )

    for mod_name, attr in _HOME_POSE_FALLBACK_MODULES:
        mod = importlib.import_module(mod_name)
        assert hasattr(mod, attr), f"{mod_name} lost {attr}"
        assert list(getattr(mod, attr)) == list(authority), (
            f"{mod_name}.{attr} drifted from the config home authority"
        )


def test_config_missing_file_fallback_home_pose_matches_default_yaml(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """load_config's hardcoded missing-file fallback must carry default.yaml's home pose.

    ``core.config.load_config`` deep-merges on top of default.yaml, but when that
    file is absent it falls back to a WHOLE inline defaults dict (``except
    FileNotFoundError``). That inline dict hardcodes its OWN copy of the SO-101
    home ``joint_values`` — the one copy E161 left unpinned. If default.yaml's home
    pose is edited but this fallback is not, a user who loses default.yaml gets an
    arm commanded to a stale pose the verify oracle (``arm_at_home()``) no longer
    grades: a silent Inv-1 breach with no red test. Pin the fallback to the YAML
    authority by driving the REAL missing-file branch and comparing.
    """
    import yaml

    from zeno.core import config as config_mod

    # The runtime authority, read straight from the YAML — never via the fallback.
    default_yaml = config_mod._DEFAULT_YAML
    assert default_yaml.exists(), f"default.yaml missing: {default_yaml}"
    authority = yaml.safe_load(default_yaml.read_text())["skills"]["home"]["joint_values"]

    # Force the missing-file branch: point _DEFAULT_YAML at a path that does not exist.
    monkeypatch.setattr(config_mod, "_DEFAULT_YAML", tmp_path / "nonexistent.yaml")
    fallback_home = config_mod.load_config()["skills"]["home"]["joint_values"]

    assert list(fallback_home) == list(authority), (
        "config.py missing-file fallback home pose drifted from default.yaml authority"
    )
