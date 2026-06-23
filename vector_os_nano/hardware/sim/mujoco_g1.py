# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MuJoCo-based simulated Unitree G1 humanoid — R2 floor.

R2 scope: WALK via the 12-DOF RL policy (motion.pt) in the go2 apartment room,
plus sensors (lidar, head camera). The robot is the matched pair:
  g1_12dof.xml + motion.pt  — proven to walk by the lead's spike (forward-0.5
  cmd → 2.70 m in 6 s, base z 0.765-0.791, no fall).

Architecture:
  _build_g1_room_scene_xml() — MjSpec attach of g1_12dof model into the go2
                               room scene (mirrors R1 approach, swaps robot).
  MuJoCoG1                  — loads scene, runs policy gait, exposes:
                                walk(), navigate_to(), set_velocity(), stop(),
                                get_base_height(), get_heading(),
                                get_lidar_scan(), get_camera_frame(),
                                get_camera_pose()

Policy control loop (50 Hz, single-threaded / synchronous):
  - _step_batch() advances 10 physics steps (0.002 s each = 0.02 s) and runs
    one policy inference.  The probe drives it step-by-step — no daemon/threads.
  - Obs layout (47): [3 ang_vel, 3 gravity, 3 cmd, 12 q, 12 dq, 12 prev_act, 2 gait_phase].
    Exact match to spike_12dof_walk.py (proven correct).

CRITICAL offset note (combined room scene):
  The g1 freejoint is NOT at qpos[0] in the combined scene (room has 3 static
  bodies before g1 is attached).  Empirically verified:
    pelvis_qpos_adr = 21   (qpos[21:28] = root pos x,y,z + quat w,x,y,z)
    pelvis_dof_adr  = 18   (qvel[18:24] = root lin_vel + ang_vel)
    leg qpos        = qpos[28:40]  (12 joints)
    leg qvel        = qvel[24:36]  (12 joints)
    ctrl indices    = ctrl[0:12]   (all 12 g1 actuators, only robot in scene)
    ang_vel obs     = qvel[21:24]  (pelvis_dof_adr + 3)
    gravity quat    = qpos[24:28]  (pelvis_qpos_adr + 3)

Camera: 'g1_head_rgb' on the pelvis body at pos=(0.04, 0, 0.42),
  xyaxes="0 -1 0 0 0 1" — forward-facing, matches go2 d435_rgb convention.
"""
from __future__ import annotations

import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from vector_os_nano.hardware.sim.sensors.g1_lidar import g1_lidar_scan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ROOM_XML = _HERE / "go2_room.xml"
_GO2_ASSETS_DIR = _HERE / "mjcf" / "go2" / "assets"

# 12-DOF model + policy from assets/g1_gait/
_ASSET_DIR = _REPO_ROOT / "assets" / "g1_gait"
_G1_12DOF_XML = _ASSET_DIR / "g1_12dof.xml"
_G1_MESHES_DIR = _ASSET_DIR / "meshes"

# Output scene (new 12dof scene — replaces the R1 29dof scene)
_G1_SCENE_XML = _HERE / "mjcf" / "g1" / "scene_g1_12dof_room.xml"

# G1 spawn position in the room
_G1_SPAWN_X: float = 10.0
_G1_SPAWN_Y: float = 3.0
_G1_PELVIS_Z: float = 0.793  # from g1_12dof default stance height

# Camera name in the compiled scene (attach prefix "g1_" + camera name "head_rgb")
_SCENE_CAM_NAME: str = "g1_head_rgb"

# Lidar mount offsets from pelvis (z-offset brings sensor to ~head height)
_LIDAR_OFFSET_X: float = 0.0
_LIDAR_OFFSET_Z: float = 0.72  # pelvis z ~0.793 + 0.72 = ~1.51 m from floor

# ---------------------------------------------------------------------------
# Policy / gait constants (from spike_12dof_walk.py — proven correct)
# ---------------------------------------------------------------------------

_SIM_DT: float = 0.002          # MuJoCo physics timestep (s)
_DECIMATION: int = 10            # physics steps per policy step → 50 Hz policy
_KPS = np.array([100, 100, 100, 150, 40, 40] * 2, dtype=np.float32)
_KDS = np.array([2, 2, 2, 4, 2, 2] * 2, dtype=np.float32)
_DEFAULT_ANGLES = np.array(
    [-0.1, 0.0, 0.0, 0.3, -0.2, 0.0, -0.1, 0.0, 0.0, 0.3, -0.2, 0.0],
    dtype=np.float32,
)
_ANG_VEL_SCALE: float = 0.25
_DOF_POS_SCALE: float = 1.0
_DOF_VEL_SCALE: float = 0.05
_ACTION_SCALE: float = 0.25
_CMD_SCALE = np.array([2.0, 2.0, 0.25], dtype=np.float32)
_NUM_ACTIONS: int = 12
_NUM_OBS: int = 47
_GAIT_PERIOD: float = 0.8

# ---------------------------------------------------------------------------
# Navigation constants (tuned from the recovered gait's navigate_to)
# ---------------------------------------------------------------------------

_NAV_TOL_FLOOR: float = 0.30      # gait COM oscillation floor
_NAV_VYAW_MAX: float = 0.6        # max yaw rate command
_NAV_K_YAW: float = 2.0           # proportional heading gain
_NAV_FACE_TOL: float = 0.35       # rad: pivot until aligned within this
_NAV_YAW_DEADBAND: float = 0.12   # rad: stop correcting when aligned
_NAV_SPEED: float = 0.5           # default forward command speed
_NAV_CAPTURE_R: float = 0.5       # m: inside → freeze steering
_NAV_FALL_Z: float = 0.4          # m: pelvis below this = fallen
_NAV_TIMEOUT_S: float = 30.0      # max seconds before timeout

# ---------------------------------------------------------------------------
# Lazy mujoco / torch imports
# ---------------------------------------------------------------------------

_mujoco: Any = None
_torch: Any = None


def _get_mujoco() -> Any:
    global _mujoco
    if _mujoco is None:
        import mujoco  # noqa: PLC0415
        _mujoco = mujoco
    return _mujoco


def _get_torch() -> Any:
    global _torch
    if _torch is None:
        import torch  # noqa: PLC0415
        _torch = torch
    return _torch


# ---------------------------------------------------------------------------
# Gravity orientation (matches spike & recovered code exactly)
# ---------------------------------------------------------------------------


def _gravity_orientation(quat: np.ndarray) -> np.ndarray:
    """Project gravity vector into body frame from quaternion (qw, qx, qy, qz)."""
    qw, qx, qy, qz = float(quat[0]), float(quat[1]), float(quat[2]), float(quat[3])
    return np.array(
        [
            2.0 * (-qz * qx + qw * qy),
            -2.0 * (qz * qy + qw * qx),
            1.0 - 2.0 * (qw * qw + qz * qz),
        ],
        dtype=np.float32,
    )


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------


def _build_g1_room_scene_xml() -> Path:
    """Build composite G1-12dof-in-go2-room scene XML via MjSpec attach.

    Strategy:
    1. Load go2_room.xml with the go2 robot include removed (room geometry only).
    2. Load g1_12dof.xml via MjSpec, set meshdir to absolute path, add head camera.
    3. Attach g1 at spawn frame (10, 3, 0) with prefix "g1_".
    4. Compile and write to scene_g1_12dof_room.xml.

    Returns the path to the written scene XML.
    """
    mj = _get_mujoco()

    if not _ROOM_XML.exists():
        raise FileNotFoundError(f"go2_room.xml not found at {_ROOM_XML}")
    if not _G1_12DOF_XML.exists():
        raise FileNotFoundError(
            f"g1_12dof.xml not found at {_G1_12DOF_XML}; "
            "run scripts/setup_g1_gait.sh first."
        )

    # Step 1: resolve room template → room-only XML (no robot)
    xml = _ROOM_XML.read_text()
    xml = xml.replace('<include file="GO2_MODEL_PATH"/>', "<!-- no robot (g1 scene) -->")
    xml = xml.replace("GO2_ASSETS_DIR", str(_GO2_ASSETS_DIR))
    xml = xml.replace("GRASP_WELDS", "")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, dir="/tmp", prefix="g1_room_12dof_tmp_"
    ) as fh:
        fh.write(xml)
        room_tmp = fh.name

    try:
        # Step 2: load MjSpec for room and 12dof g1
        room_spec = mj.MjSpec.from_file(room_tmp)

        g1_spec = mj.MjSpec.from_file(str(_G1_12DOF_XML))
        # Absolute mesh paths survive to_xml() round-trip (room meshdir overrides relative).
        for mesh in g1_spec.meshes:
            if not os.path.isabs(mesh.file):
                mesh.file = str(_G1_MESHES_DIR / mesh.file)
        g1_spec.meshdir = ""

        # Add head camera: pos=(0.04,0,0.42) → ~head height; xyaxes → forward-facing.
        pelvis_body = None
        for b in g1_spec.bodies:
            if b.name == "pelvis":
                pelvis_body = b
                break
        if pelvis_body is None:
            raise RuntimeError("pelvis body not found in g1_12dof.xml")

        pelvis_body.add_camera(
            name="head_rgb",
            pos=[0.04, 0.0, 0.42],
            xyaxes=[0, -1, 0, 0, 0, 1],
        )

        # Step 3: attach g1 at spawn frame; connect() sets standing z=0.793.
        frame = room_spec.worldbody.add_frame(pos=[_G1_SPAWN_X, _G1_SPAWN_Y, 0.0])
        room_spec.attach(g1_spec, prefix="g1_", frame=frame)
        room_spec.compile()

        # Step 4: write compiled scene
        _G1_SCENE_XML.parent.mkdir(parents=True, exist_ok=True)
        _G1_SCENE_XML.write_text(room_spec.to_xml())
        logger.info("G1-12dof room scene written to %s", _G1_SCENE_XML)

    finally:
        try:
            os.unlink(room_tmp)
        except OSError:
            pass

    return _G1_SCENE_XML


# ---------------------------------------------------------------------------
# Robot geom set for lidar self-filtering
# ---------------------------------------------------------------------------


def _build_robot_geom_set(model: Any) -> set[int]:
    """Return set of geom ids belonging to any g1_* body (lidar self-filter)."""
    mj = _get_mujoco()
    robot_geom_ids: set[int] = set()
    for gid in range(model.ngeom):
        bid = model.geom_bodyid[gid]
        body_name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, bid) or ""
        if body_name.startswith("g1_"):
            robot_geom_ids.add(gid)
    return robot_geom_ids


# ---------------------------------------------------------------------------
# Internal offset container
# ---------------------------------------------------------------------------


class _G1Offsets:
    """Pre-computed qpos/qvel/ctrl offsets for the g1 in the combined scene."""

    def __init__(self, model: Any) -> None:
        mj = _get_mujoco()
        # Pelvis (root) freejoint
        pelvis_bid = model.body("g1_pelvis").id
        jnt_adr = model.body_jntadr[pelvis_bid]
        self.pelvis_qpos_adr: int = int(model.jnt_qposadr[jnt_adr])
        self.pelvis_dof_adr: int = int(model.jnt_dofadr[jnt_adr])
        # Derived: leg joints start right after the 7-float root (pos+quat)
        self.leg_qpos_start: int = self.pelvis_qpos_adr + 7
        self.leg_dof_start: int = self.pelvis_dof_adr + 6
        # Angular velocity slice (dof_adr + 3 → 3 floats)
        self.angvel_start: int = self.pelvis_dof_adr + 3
        # Gravity orientation quaternion slice (qpos_adr + 3 → 4 floats)
        self.quat_start: int = self.pelvis_qpos_adr + 3
        # Ctrl: all 12 actuators are the ONLY actuators in the room scene
        # (verified: nu=12 and all are g1_ leg actuators)
        self.ctrl_start: int = 0
        self.ctrl_end: int = _NUM_ACTIONS
        # Pelvis body id (for mj_ray bodyexclude)
        self.pelvis_bid: int = pelvis_bid
        # Pre-build robot geom set
        self.robot_geom_ids: set[int] = _build_robot_geom_set(model)

        logger.debug(
            "G1 offsets: qpos=%d dof=%d leg_qpos=%d:%d ctrl=%d:%d nu=%d",
            self.pelvis_qpos_adr, self.pelvis_dof_adr,
            self.leg_qpos_start, self.leg_qpos_start + _NUM_ACTIONS,
            self.ctrl_start, self.ctrl_end, model.nu,
        )


# ---------------------------------------------------------------------------
# Nav result type — honors the base navigate_to contract
# ---------------------------------------------------------------------------


class _G1NavResult(dict):
    """Dict carrying nav telemetry whose truthiness reflects arrival.

    Subclasses ``dict`` so existing ``.get("moved_m")`` / ``.get("reached")``
    callers keep working unchanged.  Overrides ``__bool__`` so that
    ``bool(result)`` is ``True`` only on arrival — honoring the go2 base-navigate
    contract (plain ``bool``).  Without this, ``bool(non_empty_dict)`` is always
    ``True``, mis-reporting falls and timeouts as successful arrivals.
    """

    __slots__ = ()

    def __bool__(self) -> bool:  # noqa: D401
        """True only when ``reached`` is truthy."""
        return bool(self.get("reached", False))


# ---------------------------------------------------------------------------
# MuJoCoG1
# ---------------------------------------------------------------------------


class MuJoCoG1:
    """Simulated Unitree G1 humanoid in the go2 apartment room — R2 walking.

    Driven by a 12-DOF RL policy (motion.pt, 50 Hz) in a single-threaded
    synchronous loop.  Exposes walk(), navigate_to(), set_velocity(), stop(),
    get_base_height(), get_heading(), get_lidar_scan(), get_camera_frame(),
    get_camera_pose(), build_scene().
    """

    def __init__(self, gui: bool = False, room: bool = True) -> None:
        self._gui = gui
        self._room = room
        self._model: Any = None
        self._data: Any = None
        self._policy: Any = None
        self._offsets: _G1Offsets | None = None
        self._viewer: Any = None
        self._cam_renderer: Any = None
        # Policy per-batch state
        self._action = np.zeros(_NUM_ACTIONS, dtype=np.float32)
        self._target = _DEFAULT_ANGLES.copy()
        self._obs = np.zeros(_NUM_OBS, dtype=np.float32)
        self._counter: int = 0
        # Velocity command [vx, vy, vyaw]
        self._cmd = np.zeros(3, dtype=np.float32)
        # Sensor cache
        self._last_scan: Any = None
        self._last_pointcloud: list[tuple[float, float, float, float]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Build scene (if missing), load model + policy, reset to stance."""
        mj = _get_mujoco()
        torch = _get_torch()

        if not _G1_SCENE_XML.exists():
            _build_g1_room_scene_xml()

        self._model = mj.MjModel.from_xml_path(str(_G1_SCENE_XML))
        self._model.opt.timestep = _SIM_DT
        self._data = mj.MjData(self._model)
        self._offsets = _G1Offsets(self._model)

        # Load policy
        policy_path = _ASSET_DIR / "motion.pt"
        if not policy_path.exists():
            raise FileNotFoundError(
                f"motion.pt not found at {policy_path}; "
                "run scripts/setup_g1_gait.sh first."
            )
        self._policy = torch.jit.load(str(policy_path))

        # Reset control state
        self._action = np.zeros(_NUM_ACTIONS, dtype=np.float32)
        self._target = _DEFAULT_ANGLES.copy()
        self._obs = np.zeros(_NUM_OBS, dtype=np.float32)
        self._counter = 0
        self._cmd = np.zeros(3, dtype=np.float32)

        self._reset_to_stance()

        if self._gui:
            try:
                self._viewer = mj.viewer.launch_passive(self._model, self._data)
            except Exception as exc:
                logger.warning("Viewer unavailable (gui=True ignored): %s", exc)
                self._viewer = None

        off = self._offsets
        logger.info(
            "MuJoCoG1 R2 connected: nbody=%d nu=%d nq=%d qpos=%d ctrl=%d:%d",
            self._model.nbody, self._model.nu, self._model.nq,
            off.pelvis_qpos_adr, off.ctrl_start, off.ctrl_end,
        )

    def _reset_to_stance(self) -> None:
        """Reset physics to default 12-DOF stance at room spawn coordinates."""
        mj = _get_mujoco()
        d = self._data
        m = self._model
        off = self._offsets
        assert d is not None and m is not None and off is not None

        mj.mj_resetData(m, d)

        # Set leg joints to default stance angles
        lq = off.leg_qpos_start
        d.qpos[lq : lq + _NUM_ACTIONS] = _DEFAULT_ANGLES

        # Place pelvis freejoint at world spawn
        qa = off.pelvis_qpos_adr
        d.qpos[qa + 0] = _G1_SPAWN_X
        d.qpos[qa + 1] = _G1_SPAWN_Y
        d.qpos[qa + 2] = _G1_PELVIS_Z
        d.qpos[qa + 3] = 1.0  # qw
        d.qpos[qa + 4] = 0.0  # qx
        d.qpos[qa + 5] = 0.0  # qy
        d.qpos[qa + 6] = 0.0  # qz

        mj.mj_forward(m, d)

    def close(self) -> None:
        """Release renderer and MuJoCo resources."""
        if self._cam_renderer is not None:
            try:
                self._cam_renderer.close()
            except Exception:
                pass
            self._cam_renderer = None
        if self._viewer is not None:
            try:
                self._viewer.close()
            except Exception:
                pass
            self._viewer = None
        self._model = None
        self._data = None
        self._policy = None
        self._offsets = None

    def _require_connection(self) -> None:
        if self._model is None or self._data is None:
            raise RuntimeError("Not connected. Call connect() first.")

    # ------------------------------------------------------------------
    # Policy step (core control loop — single-threaded)
    # ------------------------------------------------------------------

    def _step_batch(self) -> None:
        """Advance one policy batch: _DECIMATION physics steps + one policy inference."""
        mj = _get_mujoco()
        torch = _get_torch()
        d = self._data
        m = self._model
        off = self._offsets
        assert d is not None and m is not None and off is not None and self._policy is not None

        lq = off.leg_qpos_start
        ld = off.leg_dof_start
        cmd = self._cmd.copy()

        # PD torque + physics advance
        for _ in range(_DECIMATION):
            tau = (self._target - d.qpos[lq : lq + _NUM_ACTIONS]) * _KPS - (
                d.qvel[ld : ld + _NUM_ACTIONS] * _KDS
            )
            d.ctrl[off.ctrl_start : off.ctrl_end] = tau
            mj.mj_step(m, d)
            self._counter += 1

        # Build observation vector (47 elements)
        obs = self._obs
        av = off.angvel_start
        obs[:3] = d.qvel[av : av + 3] * _ANG_VEL_SCALE
        obs[3:6] = _gravity_orientation(d.qpos[off.quat_start : off.quat_start + 4])
        obs[6:9] = cmd * _CMD_SCALE
        obs[9 : 9 + _NUM_ACTIONS] = (
            d.qpos[lq : lq + _NUM_ACTIONS] - _DEFAULT_ANGLES
        ) * _DOF_POS_SCALE
        obs[9 + _NUM_ACTIONS : 9 + 2 * _NUM_ACTIONS] = (
            d.qvel[ld : ld + _NUM_ACTIONS] * _DOF_VEL_SCALE
        )
        obs[9 + 2 * _NUM_ACTIONS : 9 + 3 * _NUM_ACTIONS] = self._action
        phase = (self._counter * _SIM_DT) % _GAIT_PERIOD / _GAIT_PERIOD
        obs[9 + 3 * _NUM_ACTIONS] = math.sin(2.0 * math.pi * phase)
        obs[9 + 3 * _NUM_ACTIONS + 1] = math.cos(2.0 * math.pi * phase)

        with torch.no_grad():
            self._action = (
                self._policy(torch.from_numpy(obs).unsqueeze(0)).numpy().squeeze()
            )
        self._target = self._action * _ACTION_SCALE + _DEFAULT_ANGLES

        if self._viewer is not None:
            try:
                if self._viewer.is_running():
                    self._viewer.sync()
                else:
                    self._viewer = None
            except Exception:
                self._viewer = None

    def step(self, n: int = 1) -> None:
        """Step the policy n times (n policy batches = n * DECIMATION physics steps)."""
        self._require_connection()
        for _ in range(n):
            self._step_batch()

    # ------------------------------------------------------------------
    # Velocity / gait commands
    # ------------------------------------------------------------------

    def set_velocity(self, vx: float, vy: float = 0.0, vyaw: float = 0.0) -> None:
        """Set the current velocity command [vx, vy, vyaw]."""
        self._cmd[0] = float(vx)
        self._cmd[1] = float(vy)
        self._cmd[2] = float(vyaw)

    def stop(self) -> None:
        """Zero the velocity command."""
        self._cmd[:] = 0.0

    def walk(
        self, vx: float, vy: float = 0.0, vyaw: float = 0.0, duration: float = 1.0
    ) -> None:
        """Walk with given velocity command for `duration` seconds, then stop."""
        self._require_connection()
        self.set_velocity(vx, vy, vyaw)
        n_batches = max(1, int(duration / (_SIM_DT * _DECIMATION)))
        for _ in range(n_batches):
            self._step_batch()
        self.stop()

    def navigate_to(
        self,
        x: float,
        y: float,
        tol: float = 0.3,
        speed: float = _NAV_SPEED,
        timeout: float | None = None,
        **_ignored: Any,
    ) -> "_G1NavResult":
        """Walk to world position (x, y); honors the base navigate_to contract.

        ``bool(result)`` is ``True`` only on arrival.  ``timeout=None`` uses
        ``_NAV_TIMEOUT_S``.  Extra kwargs (e.g. ``on_progress``) are ignored for
        call-shape compatibility with go2.  Returns :class:`_G1NavResult` (dict
        subclass) with keys: reached, moved_m, net_m, pos, reason.
        """
        self._require_connection()
        tol = max(tol, _NAV_TOL_FLOOR)

        # Track odometry
        off = self._offsets
        assert off is not None
        qa = off.pelvis_qpos_adr
        start_x = float(self._data.qpos[qa])
        start_y = float(self._data.qpos[qa + 1])
        prev_x, prev_y = start_x, start_y
        path_len: float = 0.0

        # Each tick = 5 policy batches ≈ 0.1 s
        _TICK_BATCHES = 5
        tick_s = _TICK_BATCHES * _SIM_DT * _DECIMATION
        eff_timeout = float(timeout) if timeout is not None else _NAV_TIMEOUT_S
        max_ticks = int(eff_timeout / tick_s) + 1

        for _tick in range(max_ticks):
            # Read current state
            cx = float(self._data.qpos[qa])
            cy = float(self._data.qpos[qa + 1])
            cz = float(self._data.qpos[qa + 2])

            # Accumulate path length
            step_m = math.hypot(cx - prev_x, cy - prev_y)
            path_len += step_m
            prev_x, prev_y = cx, cy

            # Fall detection
            if cz < _NAV_FALL_Z:
                self.stop()
                net_m = math.hypot(cx - start_x, cy - start_y)
                return _G1NavResult({
                    "reached": False,
                    "moved_m": float(path_len),
                    "net_m": float(net_m),
                    "pos": [cx, cy, cz],
                    "reason": "fell",
                })

            # Check arrival
            dx = x - cx
            dy = y - cy
            dist = math.hypot(dx, dy)
            if dist < tol:
                self.stop()
                net_m = math.hypot(cx - start_x, cy - start_y)
                return _G1NavResult({
                    "reached": True,
                    "moved_m": float(path_len),
                    "net_m": float(net_m),
                    "pos": [cx, cy, cz],
                    "reason": "arrived",
                })

            # Compute heading error
            desired_heading = math.atan2(dy, dx)
            current_heading = self.get_heading()
            yaw_err = desired_heading - current_heading
            # Wrap to [-π, π]
            while yaw_err > math.pi:
                yaw_err -= 2.0 * math.pi
            while yaw_err < -math.pi:
                yaw_err += 2.0 * math.pi

            # Choose control mode
            if abs(yaw_err) > _NAV_FACE_TOL and dist > _NAV_CAPTURE_R:
                # Pivot in place to face the goal
                vyaw = float(
                    max(-_NAV_VYAW_MAX, min(_NAV_VYAW_MAX, _NAV_K_YAW * yaw_err))
                )
                self.set_velocity(0.0, 0.0, vyaw)
            else:
                # Walk forward with optional small heading correction
                if abs(yaw_err) < _NAV_YAW_DEADBAND or dist < _NAV_CAPTURE_R:
                    vyaw = 0.0
                else:
                    vyaw = float(
                        max(-_NAV_VYAW_MAX, min(_NAV_VYAW_MAX, _NAV_K_YAW * yaw_err))
                    )
                self.set_velocity(float(speed), 0.0, vyaw)

            # Advance ~0.1 s
            for _ in range(_TICK_BATCHES):
                self._step_batch()

        # Timeout
        self.stop()
        cx = float(self._data.qpos[qa])
        cy = float(self._data.qpos[qa + 1])
        cz = float(self._data.qpos[qa + 2])
        net_m = math.hypot(cx - start_x, cy - start_y)
        return _G1NavResult({
            "reached": False,
            "moved_m": float(path_len),
            "net_m": float(net_m),
            "pos": [cx, cy, cz],
            "reason": "timeout",
        })

    # ------------------------------------------------------------------
    # Pose queries
    # ------------------------------------------------------------------

    def get_base_height(self) -> float:
        """Return pelvis z coordinate in world frame."""
        self._require_connection()
        qa = self._offsets.pelvis_qpos_adr  # type: ignore[union-attr]
        return float(self._data.qpos[qa + 2])

    def get_position(self) -> list[float]:
        """Return pelvis [x, y, z] in world frame (BaseProtocol accessor)."""
        self._require_connection()
        qa = self._offsets.pelvis_qpos_adr  # type: ignore[union-attr]
        q = self._data.qpos
        return [float(q[qa]), float(q[qa + 1]), float(q[qa + 2])]

    def get_heading(self) -> float:
        """Return yaw (radians) from pelvis quaternion (qw, qx, qy, qz)."""
        self._require_connection()
        off = self._offsets
        assert off is not None
        q = self._data.qpos[off.quat_start : off.quat_start + 4]
        qw, qx, qy, qz = float(q[0]), float(q[1]), float(q[2]), float(q[3])
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
        return math.atan2(siny_cosp, cosy_cosp)

    # ------------------------------------------------------------------
    # Lidar
    # ------------------------------------------------------------------

    def get_lidar_scan(self) -> Any:
        """Cast lidar rays from head height, return LaserScan + 3D points.

        Thin wrapper around :func:`~vector_os_nano.hardware.sim.sensors.g1_lidar.g1_lidar_scan`.
        Lidar mounted at ~1.51 m (pelvis_z + LIDAR_OFFSET_Z) — above all g1 leg
        geoms.  Uses the live pelvis pose so the scan is valid while walking.
        """
        self._require_connection()
        d = self._data
        m = self._model
        off = self._offsets
        assert d is not None and m is not None and off is not None

        qa = off.pelvis_qpos_adr
        pos_base = d.qpos[qa : qa + 3].copy().astype(np.float64)
        heading = self.get_heading()
        cos_h = math.cos(heading)
        sin_h = math.sin(heading)

        pos_lidar = np.array(
            [
                float(pos_base[0]) + cos_h * _LIDAR_OFFSET_X,
                float(pos_base[1]) + sin_h * _LIDAR_OFFSET_X,
                float(pos_base[2]) + _LIDAR_OFFSET_Z,
            ],
            dtype=np.float64,
        )

        result = g1_lidar_scan(
            m,
            d,
            pelvis_bid=off.pelvis_bid,
            robot_geom_ids=off.robot_geom_ids,
            pos_lidar=pos_lidar,
            heading=heading,
        )
        self._last_scan = result
        self._last_pointcloud = result.points_3d
        return result

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    def get_camera_frame(self, width: int = 640, height: int = 480) -> "np.ndarray":
        """Render RGB from the g1_head_rgb camera.

        Returns (H, W, 3) uint8 numpy array in RGB order.
        """
        self._require_connection()
        mj = _get_mujoco()
        m = self._model
        d = self._data
        assert m is not None and d is not None

        if self._cam_renderer is None:
            self._cam_renderer = mj.Renderer(m, height, width)

        try:
            cam_id = m.cam(_SCENE_CAM_NAME).id
        except Exception:
            cam_id = -1
            for ci in range(m.ncam):
                nm = mj.mj_id2name(m, mj.mjtObj.mjOBJ_CAMERA, ci) or ""
                if "head_rgb" in nm:
                    cam_id = ci
                    break
            if cam_id < 0:
                available = [
                    mj.mj_id2name(m, mj.mjtObj.mjOBJ_CAMERA, i)
                    for i in range(m.ncam)
                ]
                raise RuntimeError(
                    f"Camera '{_SCENE_CAM_NAME}' not found. Available: {available}"
                )

        self._cam_renderer.update_scene(d, camera=cam_id)
        return self._cam_renderer.render().copy()

    def get_camera_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (cam_xpos, cam_xmat) for the g1_head_rgb camera.

        cam_xpos: (3,) world position.
        cam_xmat: (9,) row-major rotation matrix; -Z column is optical axis.
        """
        self._require_connection()
        mj = _get_mujoco()
        m = self._model
        d = self._data
        assert m is not None and d is not None
        try:
            cam_id = m.cam(_SCENE_CAM_NAME).id
        except Exception:
            cam_id = 0
        return (
            d.cam_xpos[cam_id].copy(),
            d.cam_xmat[cam_id].copy(),
        )

    # ------------------------------------------------------------------
    # Ground truth (SIM-side; INVISIBLE to the detector)
    # ------------------------------------------------------------------

    def get_object_positions(self) -> dict[str, list[float]]:
        """Free-body object world positions ``{body_name: [x, y, z]}`` from the live
        g1 scene. Mirrors :meth:`MuJoCoPiper.get_object_positions` /
        :meth:`MuJoCoArm.get_object_positions` so the SAME duck-typed GT surface is
        available on the g1 path.

        MOAT ROLE (R7): this is INDEPENDENT SIM GROUND TRUTH — the physics body xpos
        of the room's pickables (e.g. ``pickable_can_red``). It is read ONLY by the
        verify oracle (``detection_matches_gt``), NEVER passed to the detector: the
        detector's whole input stays the rendered RGB (the firewall in
        :class:`G1HeadPerception`, which exposes only ``get_color_frame`` /
        ``get_camera_pose`` — never this). So the oracle judges the detector's box
        (the CLAIM) against a truth the detector cannot author — a real, non-tautological
        anchor, not a self-read (D61/D62 lesson).

        Scans for free-joint bodies exactly as the arm/piper accessors do, so the
        room's freejoint cylinders (can/bottles) are reported and the static furniture
        (no freejoint) is skipped. Fail-safe: requires a live connection.
        """
        self._require_connection()
        mj = _get_mujoco()
        model = self._model
        data = self._data
        assert model is not None and data is not None
        result: dict[str, list[float]] = {}
        for i in range(model.nbody):
            name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, i)
            if name is None:
                continue
            jadr = int(model.body_jntadr[i])
            if jadr < 0:
                continue
            if model.jnt_type[jadr] == mj.mjtJoint.mjJNT_FREE:
                result[name] = [float(c) for c in data.body(name).xpos]
        return result

    # ------------------------------------------------------------------
    # Scene builder (external callers / tests)
    # ------------------------------------------------------------------

    @staticmethod
    def build_scene() -> Path:
        """(Re)build the g1-12dof-in-room scene XML and return its path."""
        return _build_g1_room_scene_xml()
