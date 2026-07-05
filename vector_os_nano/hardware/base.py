# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""BaseProtocol — abstract interface for any mobile base.

All mobile base implementations (MuJoCoGo2, UnitreeRealGo2, DiffDriveBase, etc.)
must satisfy this Protocol. Agent and skills depend only on BaseProtocol,
never on concrete implementations.

Dual-mode velocity control:
  - walk(vx, vy, vyaw, duration): blocking, used by skills directly
  - set_velocity(vx, vy, vyaw): non-blocking, used by Nav2 cmd_vel bridge

No hardware imports. No ROS2 imports.
"""
from __future__ import annotations

import math
from typing import Any, Protocol, runtime_checkable


def ensure_finite_base_velocity(
    vx: float,
    vy: float,
    vyaw: float,
    ctx: str = "set_velocity",
) -> None:
    """Reject non-finite (NaN/±inf) base-velocity commands before acting.

    Security floor (rules/common/security.md): reject NaN/inf before acting on an
    actuator. ``set_velocity`` is the streaming command boundary for every mobile
    base — driven by the Nav2 ``/cmd_vel_nav`` bridge, a BYO skill's walk/turn args,
    and NL-parsed velocities. A non-finite component written into a sim command
    array (or published onto ``/cmd_vel_nav``) silently poisons the robot state; a
    NaN also corrupts the ``_cmd_motion`` R2b actor-causation signal the Inv-1 verify
    spine reads (``nan > MOTION_EPS`` is False, so a real motion registers as none)
    while the command still reaches the actuator — a fail-open. Every concrete
    ``set_velocity`` MUST call this at its entry so a bad value fails loud and
    axis-scoped at the boundary rather than being commanded.

    Note ``np.clip`` is NOT sufficient: it clamps ±inf but PROPAGATES NaN
    (``np.clip(nan, lo, hi) == nan``), so a magnitude clamp cannot stand in for this.

    Raises:
        ValueError: if vx, vy or vyaw is NaN, +inf or -inf.
    """
    for name, v in (("vx", vx), ("vy", vy), ("vyaw", vyaw)):
        if not math.isfinite(v):
            raise ValueError(
                f"{ctx}: base velocity {name} is non-finite ({v!r}); "
                "refusing to command NaN/inf to the actuator"
            )


@runtime_checkable
class BaseProtocol(Protocol):
    """Abstract interface for any mobile robot base (quadruped, wheeled, tracked).

    Implementations must be safe to call from Python threads. Real-time safety
    is the responsibility of the concrete implementation (e.g. physics thread).
    """

    @property
    def name(self) -> str:
        """Identifier: 'go2', 'turtlebot', 'sim_diff_drive', etc."""
        ...

    def connect(self) -> None:
        """Open connection to the base hardware or simulator.

        Raises:
            ConnectionError: If the connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Close the connection. Must be idempotent (safe to call if not connected)."""
        ...

    def stop(self) -> None:
        """Emergency stop. Immediately halt all motion.

        Must not raise even under error conditions. Safe to call from any thread.
        """
        ...

    # --- Blocking locomotion (for direct skill use) ---

    def walk(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        vyaw: float = 0.0,
        duration: float = 1.0,
    ) -> bool:
        """Move at body velocity for duration seconds. Blocking.

        Args:
            vx: Forward velocity in m/s (body frame).
            vy: Lateral velocity in m/s (body frame, positive = left).
            vyaw: Yaw rate in rad/s (positive = counter-clockwise).
            duration: Time to hold velocity in seconds.

        Returns:
            True if the motion completed normally, False on error or if the
            base fell / reached a safety limit.
        """
        ...

    # --- Streaming velocity (for Nav2 / nav stack cmd_vel) ---

    def set_velocity(self, vx: float, vy: float, vyaw: float) -> None:
        """Set target velocity. Non-blocking. Physics loop applies it continuously.

        Args:
            vx: Forward velocity in m/s (body frame).
            vy: Lateral velocity in m/s (body frame, positive = left).
            vyaw: Yaw rate in rad/s (positive = counter-clockwise).
        """
        ...

    # --- State queries ---

    def get_position(self) -> list[float]:
        """Current position in world frame.

        Returns:
            [x, y, z] in meters.

        Raises:
            RuntimeError: If not connected.
        """
        ...

    def get_heading(self) -> float:
        """Current yaw angle in world frame.

        Returns:
            Yaw in radians (positive = counter-clockwise from +X axis).

        Raises:
            RuntimeError: If not connected.
        """
        ...

    def get_velocity(self) -> list[float]:
        """Current velocity in world frame.

        Returns:
            [vx, vy, vz] in m/s.

        Raises:
            RuntimeError: If not connected.
        """
        ...

    def get_odometry(self) -> Any:
        """Full odometry snapshot.

        Returns:
            Odometry dataclass (vector_os_nano.core.types.Odometry).

        Raises:
            RuntimeError: If not connected.
        """
        ...

    def get_lidar_scan(self) -> Any:
        """Most recent 2D laser scan.

        Returns:
            LaserScan dataclass if lidar is available, None otherwise.

        Raises:
            RuntimeError: If not connected.
        """
        ...

    # --- Capability flags ---

    @property
    def supports_holonomic(self) -> bool:
        """True if base can strafe (omnidirectional). Go2=True, diff_drive=False."""
        ...

    @property
    def supports_lidar(self) -> bool:
        """True if get_lidar_scan() returns data (not None)."""
        ...
