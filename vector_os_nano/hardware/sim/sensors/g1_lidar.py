# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""G1 lidar ray-casting helper (extracted from mujoco_g1.get_lidar_scan).

Public surface:

* :func:`g1_lidar_scan` — cast lidar rays from a given world position in a
  MuJoCo model+data pair and return a :class:`~vector_os_nano.core.types.LaserScan`
  with attached 3-D point-cloud diagnostics.  Behaviour is byte-for-byte identical
  to the inline code that previously lived inside ``MuJoCoG1.get_lidar_scan``.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    pass

__all__ = ["g1_lidar_scan"]


def g1_lidar_scan(
    model: Any,
    data: Any,
    *,
    pelvis_bid: int,
    robot_geom_ids: set[int],
    pos_lidar: np.ndarray,
    heading: float,
) -> Any:
    """Cast multi-elevation lidar rays from *pos_lidar* in a MuJoCo scene.

    Mirrors the ray-casting body of ``MuJoCoG1.get_lidar_scan`` exactly —
    all numeric constants, the tilt, elevation rings, azimuth resolution,
    ``mj_ray`` ``bodyexclude`` and self-filter logic are preserved unchanged.

    Args:
        model: ``mujoco.MjModel`` for the compiled scene.
        data: ``mujoco.MjData`` for the current sim state.
        pelvis_bid: Body id passed to ``mj_ray`` as *bodyexclude* (avoids
            spurious self-hits through the pelvis capsule).
        robot_geom_ids: Set of geom ids belonging to g1_* bodies; hits against
            these are treated as self-hits and filtered from the 3-D point cloud
            and the mid-ring range list.
        pos_lidar: ``(3,)`` float64 world position of the virtual lidar origin.
        heading: Robot yaw (radians), used to orient the azimuth sweep so that
            index 0 is behind the robot (``heading - 180 deg``).

    Returns:
        A :class:`~vector_os_nano.core.types.LaserScan`-like object with all
        standard ``LaserScan`` fields PLUS the diagnostic attributes
        ``n_returns``, ``min_range``, ``median_range``, ``points_3d``, and
        ``near_zero_self_hits``.
    """
    from vector_os_nano.core.types import LaserScan  # noqa: PLC0415

    import mujoco as _mj  # noqa: PLC0415

    # ------------------------------------------------------------------
    # Constants (mirrors the inline code exactly)
    # ------------------------------------------------------------------
    tilt_rad = math.radians(-10.0)
    cos_tilt = math.cos(tilt_rad)
    sin_tilt = math.sin(tilt_rad)

    n_azimuth = 360
    elevations = sorted(set([0] + list(range(-8, 30, 3))))

    cos_h = math.cos(heading)
    sin_h = math.sin(heading)

    mid_ring_ranges: list[float] = []
    points_3d: list[tuple[float, float, float, float]] = []
    near_zero_hits: int = 0

    # ------------------------------------------------------------------
    # Ray-casting loop (byte-for-byte copy of the inline body)
    # ------------------------------------------------------------------
    for elev_deg in elevations:
        elev_rad = math.radians(elev_deg)
        cos_elev = math.cos(elev_rad)
        sin_elev = math.sin(elev_rad)
        azimuth_step = 360.0 / n_azimuth

        for i in range(n_azimuth):
            azimuth = heading + math.radians(i * azimuth_step - 180.0)

            dx_w = cos_elev * math.cos(azimuth)
            dy_w = cos_elev * math.sin(azimuth)
            dz_w = sin_elev

            dx_b = dx_w * cos_h + dy_w * sin_h
            dy_b = -dx_w * sin_h + dy_w * cos_h
            dz_b = dz_w

            dx_bt = dx_b * cos_tilt - dz_b * sin_tilt
            dz_bt = dx_b * sin_tilt + dz_b * cos_tilt

            direction = np.array(
                [
                    dx_bt * cos_h - dy_b * sin_h,
                    dx_bt * sin_h + dy_b * cos_h,
                    dz_bt,
                ],
                dtype=np.float64,
            )

            geom_id = np.zeros(1, dtype=np.int32)
            dist = _mj.mj_ray(
                model,
                data,
                pos_lidar,
                direction,
                None,
                1,
                pelvis_bid,
                geom_id,
            )

            is_self = int(geom_id[0]) in robot_geom_ids
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

    # ------------------------------------------------------------------
    # Build LaserScan + diagnostics wrapper (mirrors inline exactly)
    # ------------------------------------------------------------------
    valid_ranges = [r for r in mid_ring_ranges if r < 15.0]
    scan = LaserScan(
        timestamp=float(data.time),
        angle_min=-math.pi,
        angle_max=math.pi,
        angle_increment=math.radians(360.0 / n_azimuth),
        range_min=0.05,
        range_max=15.0,
        ranges=tuple(mid_ring_ranges),
    )
    diagnostics = {
        "n_returns": len(valid_ranges),
        "min_range": min(valid_ranges) if valid_ranges else float("inf"),
        "median_range": (
            float(np.median(valid_ranges)) if valid_ranges else float("inf")
        ),
        "points_3d": points_3d,
        "near_zero_self_hits": near_zero_hits,
    }

    class _ScanWithDiag:  # noqa: N801
        def __init__(self, s: LaserScan, diag: dict) -> None:
            self._scan = s
            self.__dict__.update(diag)
            self.timestamp = s.timestamp
            self.angle_min = s.angle_min
            self.angle_max = s.angle_max
            self.angle_increment = s.angle_increment
            self.range_min = s.range_min
            self.range_max = s.range_max
            self.ranges = s.ranges

    return _ScanWithDiag(scan, diagnostics)
