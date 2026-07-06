# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""ArmProtocol — abstract interface for any robot arm.

All arm implementations (SO101Arm, SimulatedArm, etc.) must satisfy
this Protocol. The agent engine and skills depend only on ArmProtocol,
never on concrete implementations.

No hardware imports. No ROS2 imports.
"""
from __future__ import annotations

import math
from typing import Iterable, Protocol, runtime_checkable


def ensure_finite_joint_targets(
    positions: Iterable[float],
    ctx: str = "move_joints",
) -> None:
    """Reject non-finite (NaN/±inf) actuator targets before commanding.

    Security floor (rules/common/security.md): reject NaN/inf before acting on
    an actuator. A non-finite joint target written into a sim ``ctrl`` array or
    a real servo command silently poisons the robot state and every downstream
    verify while the move reports success — a fail-open. Every concrete
    ``move_joints`` MUST call this at its entry so a bad value from config
    (``skills.<name>.joint_values``), IK output, or the ROS2 bridge fails loud
    and index-scoped at the boundary rather than being commanded.

    Length (dof mismatch) stays a separate, pre-existing contract — this gate
    checks only finiteness and is a no-op on an empty sequence.

    Raises:
        ValueError: if any target is NaN, +inf or -inf.
    """
    for i, v in enumerate(positions):
        if not math.isfinite(v):
            raise ValueError(
                f"{ctx}: joint target[{i}] is non-finite ({v!r}); "
                "refusing to command NaN/inf to the actuator"
            )


@runtime_checkable
class ArmProtocol(Protocol):
    """Abstract interface for any robot arm.

    Implementations must be safe to call from Python threads but are NOT
    required to be real-time safe — trajectory interpolation runs at
    servo-rate (50-100 Hz) which is soft-RT.
    """

    @property
    def name(self) -> str:
        """Human-readable identifier for this arm (e.g., "so101", "sim")."""
        ...

    @property
    def joint_names(self) -> list[str]:
        """Ordered list of joint names (length == dof)."""
        ...

    @property
    def dof(self) -> int:
        """Degrees of freedom (number of actuated joints, excluding gripper)."""
        ...

    def connect(self) -> None:
        """Open the connection to the arm hardware.

        Raises:
            ConnectionError: If the connection cannot be established.
            OSError: For serial/USB errors.
        """
        ...

    def disconnect(self) -> None:
        """Close the connection. Must be idempotent (safe to call if not connected)."""
        ...

    def get_joint_positions(self) -> list[float]:
        """Read current joint positions in radians.

        Returns:
            List of floats, length == dof, in joint_names order.

        Raises:
            RuntimeError: If not connected.
        """
        ...

    def move_joints(self, positions: list[float], duration: float = 3.0) -> bool:
        """Move to target joint positions over duration seconds.

        Args:
            positions: Target joint positions in radians, length == dof.
            duration: Time to complete the motion (seconds).

        Returns:
            True if motion completed successfully, False on timeout or error.

        Raises:
            ValueError: If len(positions) != dof, or any target is non-finite
                (NaN/±inf) — see ``ensure_finite_joint_targets``.
            RuntimeError: If not connected.
        """
        ...

    def move_cartesian(
        self,
        target_xyz: tuple[float, float, float],
        duration: float = 3.0,
    ) -> bool:
        """Move end-effector to target Cartesian position (IK solved internally).

        Args:
            target_xyz: Target (x, y, z) in meters, robot base frame.
            duration: Motion duration in seconds.

        Returns:
            True if motion completed, False if IK failed or motion error.

        Raises:
            RuntimeError: If not connected.
        """
        ...

    def fk(
        self,
        joint_positions: list[float],
    ) -> tuple[list[float], list[list[float]]]:
        """Forward kinematics: joint positions → end-effector pose.

        Args:
            joint_positions: Joint positions in radians, length == dof.

        Returns:
            (position_xyz, rotation_3x3) where:
            - position_xyz: [x, y, z] in meters
            - rotation_3x3: 3x3 rotation matrix as list-of-lists
        """
        ...

    def ik(
        self,
        target_xyz: tuple[float, float, float],
        current_joints: list[float] | None = None,
    ) -> list[float] | None:
        """Inverse kinematics: Cartesian target → joint positions.

        Args:
            target_xyz: Target (x, y, z) in meters, robot base frame.
            current_joints: Seed configuration (uses current if None).

        Returns:
            Joint positions in radians if reachable, None if no IK solution.
        """
        ...

    def stop(self) -> None:
        """Emergency stop. Immediately halt all motion.

        Must not raise even under error conditions. Should be safe to call
        from any thread.

        Raises:
            RuntimeError: If not connected.
        """
        ...
