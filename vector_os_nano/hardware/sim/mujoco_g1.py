# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""MuJoCo-based simulated Unitree G1 humanoid — R1 WIP floor.

R1 scope: STAND + sensors (lidar, head camera) in the go2 apartment room.
Gait / navigation are R2+ (see /tmp/recovered_mujoco_g1.py for prior art).

Architecture:
  build_g1_room_scene_xml() — builds composite scene via MjSpec attach
                              (mirrors mujoco_go2._build_room_scene_xml).
  MuJoCoG1                 — loads scene, holds stand pose, exposes sensors.

The G1 Menagerie model uses position actuators (kp=500, dampratio=1 per
default class).  Setting data.ctrl = key_ctrl[stand_kf] is enough to hold
the stand pose — the actuators' own PD (kp/kd derived from dampratio) handle
the rest.  No additional PD layer is needed for R1.

Spawn: (10, 3, 0.793) facing +x — same as the go2 spawn, directly in front
of the pick_table at (10.95, 3.0).

Camera convention: camera 'g1_head_rgb' (scene name after attach prefix)
  Camera frame X_cam=(0,-1,0), Y_cam=(0,0,1), Z_cam=(-1,0,0).
  Optical axis = -Z_cam = +X_world → looks forward when g1 faces +x.
  Matches go2's d435_rgb xyaxes="0 -1 0 0 0 1" exactly.

Lidar: 2D ring + 3D rings around g1's head height (~1.5m from ground),
  self-filtered using pre-built robot geom set. Mirrors _update_lidar in
  mujoco_go2.py.
"""
from __future__ import annotations

import logging
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_ROOM_XML = _HERE / "go2_room.xml"
_GO2_ASSETS_DIR = _HERE / "mjcf" / "go2" / "assets"
_G1_XML = _HERE / "mjcf" / "g1" / "g1.xml"
_G1_SCENE_XML = _HERE / "mjcf" / "g1" / "scene_g1_room.xml"

# G1 spawn position in the room (same as go2 spawn — facing pick_table)
_G1_SPAWN_X: float = 10.0
_G1_SPAWN_Y: float = 3.0
_G1_PELVIS_Z: float = 0.793  # from menagerie stand keyframe

# Camera name in the COMPILED scene (attach prefix "g1_" + camera name "head_rgb")
_SCENE_CAM_NAME: str = "g1_head_rgb"

# Lidar mount offsets from pelvis (world-frame z component is additive to pelvis z)
# Mount at ~head height to clear legs; pelvis z ≈ 0.793, so offset_z=0.72 → ~1.51m
_LIDAR_OFFSET_X: float = 0.0
_LIDAR_OFFSET_Z: float = 0.72  # ~1.51m from floor when standing

# ---------------------------------------------------------------------------
# Lazy mujoco import
# ---------------------------------------------------------------------------

_mujoco: Any = None


def _get_mujoco() -> Any:
    global _mujoco
    if _mujoco is None:
        import mujoco  # noqa: PLC0415
        _mujoco = mujoco
    return _mujoco


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------

def _build_g1_room_scene_xml() -> Path:
    """Build composite G1-in-go2-room scene XML via MjSpec attach.

    Strategy:
    1. Load go2_room.xml, replacing <include GO2_MODEL_PATH> with a comment
       so the room geometry (walls/furniture/pick_table/cans) compiles without
       the go2 robot.
    2. Load the pre-built g1.xml (absolute mesh paths, head camera).
    3. Attach g1 at a frame at (10, 3, 0) in the room worldbody (facing +x).
    4. Compile and write to scene_g1_room.xml.

    Textures in go2_room.xml use builtin types (gradient/checker/flat) and
    furniture PNG textures loaded via texturedir=GO2_ASSETS_DIR.  We rewrite
    texturedir to the absolute go2 assets path in the resolved XML so textures
    survive the temp-file round-trip.  (If the PNG files are missing, MuJoCo
    falls back to flat colors — the room geometry still loads.)

    Returns the path to the written scene XML.
    """
    mj = _get_mujoco()

    if not _ROOM_XML.exists():
        raise FileNotFoundError(f"go2_room.xml not found at {_ROOM_XML}")
    if not _G1_XML.exists():
        raise FileNotFoundError(
            f"g1.xml not found at {_G1_XML}; run build_g1.py first."
        )

    # ------------------------------------------------------------------
    # Step 1: resolve room template → room-only XML (no go2 robot)
    # ------------------------------------------------------------------
    xml = _ROOM_XML.read_text()
    # Remove go2 include — room geometry stays, no robot bodies
    xml = xml.replace('<include file="GO2_MODEL_PATH"/>', "<!-- no robot (g1 scene) -->")
    # Substitute asset dirs (meshdir and texturedir for furniture)
    xml = xml.replace("GO2_ASSETS_DIR", str(_GO2_ASSETS_DIR))
    # Remove grasp welds (piper-specific; g1 has no arm in R1)
    xml = xml.replace("GRASP_WELDS", "")

    # Write to a temp file so MjSpec can resolve relative refs
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".xml", delete=False, dir="/tmp", prefix="g1_room_tmp_"
    ) as fh:
        fh.write(xml)
        room_tmp = fh.name

    try:
        # ------------------------------------------------------------------
        # Step 2: load MjSpec for room and g1
        # ------------------------------------------------------------------
        room_spec = mj.MjSpec.from_file(room_tmp)
        g1_spec = mj.MjSpec.from_file(str(_G1_XML))

        # ------------------------------------------------------------------
        # Step 3: attach g1 at spawn frame
        # G1's pelvis free joint starts at (0,0,0) relative to the attach
        # frame; the stand keyframe sets pelvis z=0.793 within qpos, so
        # physically it floats at frame_z + 0.793.  We place the frame at
        # z=0 so connect() can set qpos[pelvis_z]=0.793 directly.
        # ------------------------------------------------------------------
        frame = room_spec.worldbody.add_frame(
            pos=[_G1_SPAWN_X, _G1_SPAWN_Y, 0.0]
        )
        room_spec.attach(g1_spec, prefix="g1_", frame=frame)
        room_spec.compile()

        # ------------------------------------------------------------------
        # Step 4: write scene
        # ------------------------------------------------------------------
        _G1_SCENE_XML.parent.mkdir(parents=True, exist_ok=True)
        _G1_SCENE_XML.write_text(room_spec.to_xml())
        logger.info("G1 room scene written to %s", _G1_SCENE_XML)

    finally:
        try:
            os.unlink(room_tmp)
        except OSError:
            pass

    return _G1_SCENE_XML


# ---------------------------------------------------------------------------
# Internal sim state container
# ---------------------------------------------------------------------------

class _G1SimState:
    """Lightweight container for the loaded MuJoCo model + data."""

    def __init__(self, model: Any, data: Any) -> None:
        self.model = model
        self.data = data
        # g1 pelvis freejoint qpos address in the combined scene
        pelvis_bid = model.body("g1_pelvis").id
        jnt_adr = model.body_jntadr[pelvis_bid]
        self.pelvis_qpos_adr: int = int(model.jnt_qposadr[jnt_adr])
        # Stand keyframe index (named "g1_stand" in combined scene)
        self.stand_kf_id: int = -1
        for ki in range(model.nkey):
            nm = _get_mujoco().mj_id2name(model, _get_mujoco().mjtObj.mjOBJ_KEY, ki)
            if nm == "g1_stand":
                self.stand_kf_id = ki
                break
        # Pre-build robot geom id set (all geoms whose body is in g1 subtree)
        self._robot_geom_ids: set[int] = _build_robot_geom_set(model)
        # Pelvis body id for mj_ray bodyexclude
        self.base_bid: int = pelvis_bid


def _build_robot_geom_set(model: Any) -> set[int]:
    """Return set of geom ids that belong to any g1_* body (self-filter for lidar)."""
    mj = _get_mujoco()
    robot_geom_ids: set[int] = set()
    for gid in range(model.ngeom):
        bid = model.geom_bodyid[gid]
        body_name = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, bid) or ""
        if body_name.startswith("g1_"):
            robot_geom_ids.add(gid)
    return robot_geom_ids


# ---------------------------------------------------------------------------
# MuJoCoG1
# ---------------------------------------------------------------------------

class MuJoCoG1:
    """Simulated Unitree G1 humanoid in the go2 apartment room.

    R1: stand, sensors (lidar + head camera), basic pose queries.

    Usage:
        g1 = MuJoCoG1(gui=False)
        g1.connect()
        g1.settle(seconds=0.5)
        height = g1.get_base_height()
        scan = g1.get_lidar_scan()
        frame = g1.get_camera_frame()
        g1.close()
    """

    def __init__(self, gui: bool = False, room: bool = True) -> None:
        self._gui = gui
        self._room = room
        self._mj: _G1SimState | None = None
        self._viewer: Any = None
        self._cam_renderer: Any = None
        self._last_scan: Any = None
        self._last_pointcloud: list[tuple[float, float, float, float]] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Build scene (if needed), load model, reset to stand keyframe."""
        mj = _get_mujoco()

        # Build scene if not present or if forced
        if not _G1_SCENE_XML.exists():
            _build_g1_room_scene_xml()

        model = mj.MjModel.from_xml_path(str(_G1_SCENE_XML))
        data = mj.MjData(model)
        self._mj = _G1SimState(model, data)

        # Reset to stand keyframe
        self._reset_to_stand()

        if self._gui:
            try:
                self._viewer = mj.viewer.launch_passive(model, data)
            except Exception as exc:
                logger.warning("Viewer unavailable (gui=True ignored): %s", exc)
                self._viewer = None

        logger.info(
            "MuJoCoG1 connected: nbody=%d, njnt=%d, nu=%d, pelvis_qpos_adr=%d",
            model.nbody, model.njnt, model.nu, self._mj.pelvis_qpos_adr,
        )

    def _reset_to_stand(self) -> None:
        """Reset to stand keyframe and place pelvis at room spawn coordinates."""
        mj = _get_mujoco()
        state = self._mj
        assert state is not None

        if state.stand_kf_id >= 0:
            mj.mj_resetDataKeyframe(state.model, state.data, state.stand_kf_id)
        else:
            mj.mj_resetData(state.model, state.data)
            # Manually set stand joint angles from keyframe ctrl
            state.data.ctrl[:] = state.model.key_ctrl[0]
            state.data.qpos[state.pelvis_qpos_adr + 3] = 1.0  # qw=1 (identity)

        # Override freejoint translation to world spawn position
        # (keyframe has pelvis at (0,0,0.793) relative to attach frame —
        # the attach frame is at (10,3,0) so we set the qpos to world coords)
        qa = state.pelvis_qpos_adr
        state.data.qpos[qa + 0] = _G1_SPAWN_X
        state.data.qpos[qa + 1] = _G1_SPAWN_Y
        state.data.qpos[qa + 2] = _G1_PELVIS_Z
        state.data.qpos[qa + 3] = 1.0  # qw
        state.data.qpos[qa + 4] = 0.0  # qx
        state.data.qpos[qa + 5] = 0.0  # qy
        state.data.qpos[qa + 6] = 0.0  # qz

        # Set ctrl to stand values so position actuators hold the pose
        if state.stand_kf_id >= 0:
            state.data.ctrl[:] = state.model.key_ctrl[state.stand_kf_id]

        mj.mj_forward(state.model, state.data)

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
        self._mj = None

    def _require_connection(self) -> None:
        if self._mj is None:
            raise RuntimeError("Not connected. Call connect() first.")

    # ------------------------------------------------------------------
    # Physics stepping
    # ------------------------------------------------------------------

    def step(self, n: int = 1) -> None:
        """Step physics n times, holding stand pose via ctrl each step."""
        self._require_connection()
        mj = _get_mujoco()
        state = self._mj
        assert state is not None
        for _ in range(n):
            # Position actuators: keep ctrl at stand values
            if state.stand_kf_id >= 0:
                state.data.ctrl[:] = state.model.key_ctrl[state.stand_kf_id]
            mj.mj_step(state.model, state.data)

        if self._viewer is not None:
            try:
                self._viewer.sync()
            except Exception:
                pass

    def settle(self, seconds: float) -> None:
        """Step physics for a given wall time equivalent (100 Hz control loop)."""
        self._require_connection()
        mj = _get_mujoco()
        dt = float(self._mj.model.opt.timestep)  # type: ignore[union-attr]
        n_steps = max(1, int(seconds / dt))
        self.step(n_steps)

    # ------------------------------------------------------------------
    # Pose queries
    # ------------------------------------------------------------------

    def get_base_height(self) -> float:
        """Return pelvis z coordinate in world frame."""
        self._require_connection()
        qa = self._mj.pelvis_qpos_adr  # type: ignore[union-attr]
        return float(self._mj.data.qpos[qa + 2])  # type: ignore[union-attr]

    def get_heading(self) -> float:
        """Return yaw angle (radians) from pelvis quaternion (qw,qx,qy,qz)."""
        self._require_connection()
        qa = self._mj.pelvis_qpos_adr  # type: ignore[union-attr]
        q = self._mj.data.qpos[qa + 3: qa + 7]  # type: ignore[union-attr]
        # q = [qw, qx, qy, qz]
        qw, qx, qy, qz = float(q[0]), float(q[1]), float(q[2]), float(q[3])
        siny_cosp = 2.0 * (qw * qz + qx * qy)
        cosy_cosp = 1.0 - 2.0 * (qy * qy + qz * qz)
        return math.atan2(siny_cosp, cosy_cosp)

    # ------------------------------------------------------------------
    # Lidar
    # ------------------------------------------------------------------

    def get_lidar_scan(self) -> Any:
        """Cast lidar rays from head height, return LaserScan + 3D points.

        Mirrors mujoco_go2._update_lidar.  Lidar mounted at ~1.5m
        (pelvis_z + LIDAR_OFFSET_Z) — above all g1 leg geoms.

        Returns:
            LaserScan dataclass with: ranges, n_returns, min_range,
            median_range, and near_zero_self_hits count.
        """
        self._require_connection()
        from vector_os_nano.core.types import LaserScan  # noqa: PLC0415
        mj = _get_mujoco()
        state = self._mj
        assert state is not None

        qa = state.pelvis_qpos_adr
        pos_base = state.data.qpos[qa: qa + 3].copy().astype(np.float64)
        heading = self.get_heading()
        cos_h = math.cos(heading)
        sin_h = math.sin(heading)

        # Lidar position in world frame
        pos_lidar = np.array([
            float(pos_base[0]) + cos_h * _LIDAR_OFFSET_X,
            float(pos_base[1]) + sin_h * _LIDAR_OFFSET_X,
            float(pos_base[2]) + _LIDAR_OFFSET_Z,
        ], dtype=np.float64)

        # Scan beam tilt: 10° downward (shallow — at 1.5m height sees walls fine)
        tilt_rad = math.radians(-10.0)
        cos_tilt = math.cos(tilt_rad)
        sin_tilt = math.sin(tilt_rad)

        n_azimuth = 360
        elevations = sorted(set([0] + list(range(-8, 30, 3))))  # include 0° for 2D ring
        mid_ring_ranges: list[float] = []
        points_3d: list[tuple[float, float, float, float]] = []
        near_zero_hits: int = 0

        for elev_deg in elevations:
            elev_rad = math.radians(elev_deg)
            cos_elev = math.cos(elev_rad)
            sin_elev = math.sin(elev_rad)
            azimuth_step = 360.0 / n_azimuth

            for i in range(n_azimuth):
                azimuth = heading + math.radians(i * azimuth_step - 180.0)

                # Ray direction in world frame (no tilt yet)
                dx_w = cos_elev * math.cos(azimuth)
                dy_w = cos_elev * math.sin(azimuth)
                dz_w = sin_elev

                # World → body frame
                dx_b = dx_w * cos_h + dy_w * sin_h
                dy_b = -dx_w * sin_h + dy_w * cos_h
                dz_b = dz_w

                # Apply pitch tilt in body frame
                dx_bt = dx_b * cos_tilt - dz_b * sin_tilt
                dz_bt = dx_b * sin_tilt + dz_b * cos_tilt

                # Body → world frame
                direction = np.array([
                    dx_bt * cos_h - dy_b * sin_h,
                    dx_bt * sin_h + dy_b * cos_h,
                    dz_bt,
                ], dtype=np.float64)

                geom_id = np.zeros(1, dtype=np.int32)
                dist = mj.mj_ray(
                    state.model,
                    state.data,
                    pos_lidar,
                    direction,
                    None,
                    1,
                    state.base_bid,
                    geom_id,
                )

                is_self = int(geom_id[0]) in state._robot_geom_ids
                hit_valid = dist > 0 and dist < 15.0 and not is_self

                if hit_valid:
                    px = pos_lidar[0] + dist * direction[0]
                    py = pos_lidar[1] + dist * direction[1]
                    pz = pos_lidar[2] + dist * direction[2]
                    points_3d.append((float(px), float(py), float(pz), 0.0))

                if elev_deg == 0:
                    if is_self and dist > 0 and dist < 0.1:
                        near_zero_hits += 1
                    if hit_valid:
                        mid_ring_ranges.append(float(dist))
                    else:
                        mid_ring_ranges.append(float("inf"))

        valid_ranges = [r for r in mid_ring_ranges if r < 15.0]
        scan = LaserScan(
            timestamp=float(state.data.time),
            angle_min=-math.pi,
            angle_max=math.pi,
            angle_increment=math.radians(360.0 / n_azimuth),
            range_min=0.05,
            range_max=15.0,
            ranges=tuple(mid_ring_ranges),
        )
        # Diagnostics returned as a companion dict (LaserScan is frozen)
        diagnostics = {
            "n_returns": len(valid_ranges),
            "min_range": min(valid_ranges) if valid_ranges else float("inf"),
            "median_range": float(np.median(valid_ranges)) if valid_ranges else float("inf"),
            "points_3d": points_3d,
            "near_zero_self_hits": near_zero_hits,
        }

        # Expose diagnostics as a plain struct so callers can use scan.n_returns etc
        class _ScanWithDiag:  # noqa: N801
            def __init__(self, s: LaserScan, d: dict) -> None:
                self._scan = s
                self.__dict__.update(d)
                # Forward LaserScan fields
                self.timestamp = s.timestamp
                self.angle_min = s.angle_min
                self.angle_max = s.angle_max
                self.angle_increment = s.angle_increment
                self.range_min = s.range_min
                self.range_max = s.range_max
                self.ranges = s.ranges

        result = _ScanWithDiag(scan, diagnostics)
        self._last_scan = result
        self._last_pointcloud = points_3d
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
        state = self._mj
        assert state is not None

        if self._cam_renderer is None:
            self._cam_renderer = mj.Renderer(state.model, height, width)

        # Resolve camera name: "g1_head_rgb" in the compiled scene
        try:
            cam_id = state.model.cam(_SCENE_CAM_NAME).id
        except Exception:
            # Fallback: iterate to find the first camera containing "head_rgb"
            cam_id = -1
            for ci in range(state.model.ncam):
                nm = mj.mj_id2name(state.model, mj.mjtObj.mjOBJ_CAMERA, ci) or ""
                if "head_rgb" in nm:
                    cam_id = ci
                    break
            if cam_id < 0:
                raise RuntimeError(
                    f"Camera '{_SCENE_CAM_NAME}' not found in model. "
                    f"Available cameras: {[mj.mj_id2name(state.model, mj.mjtObj.mjOBJ_CAMERA, i) for i in range(state.model.ncam)]}"
                )

        self._cam_renderer.update_scene(state.data, camera=cam_id)
        return self._cam_renderer.render().copy()

    def get_camera_pose(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (cam_xpos, cam_xmat) for the g1_head_rgb camera.

        cam_xpos: (3,) world position of camera
        cam_xmat: (9,) rotation matrix (row-major, reshape to 3x3)

        The cam_xmat -Z column is the optical axis direction.
        """
        self._require_connection()
        mj = _get_mujoco()
        state = self._mj
        assert state is not None
        try:
            cam_id = state.model.cam(_SCENE_CAM_NAME).id
        except Exception:
            cam_id = 0
        return (
            state.data.cam_xpos[cam_id].copy(),
            state.data.cam_xmat[cam_id].copy(),
        )

    # ------------------------------------------------------------------
    # Convenience scene builder (for external callers)
    # ------------------------------------------------------------------

    @staticmethod
    def build_scene() -> Path:
        """(Re)build the g1-in-room scene XML and return its path."""
        return _build_g1_room_scene_xml()
