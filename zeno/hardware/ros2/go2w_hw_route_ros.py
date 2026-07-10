# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Route-mode config/status dataclasses + the ROS I/O boundary (split from
go2w_hw_route.py — repo rule: files under 400 lines).

The frozen knobs/snapshot (Inv-7) and the two rclpy-touching helpers live here so
:mod:`~zeno.hardware.ros2.go2w_hw_route` stays lean and its state machine stays
free of message-type imports. Both helpers import ROS message types LAZILY (the
module is safe to import with no ROS env) and NEVER raise into the caller (the
manager treats a failed attach/publish as a clean False / no-op).
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class RouteConfig:
    """Immutable knobs for the route session (additive-only, Inv-7)."""

    nav_sh: str = "~/go2w-nuc/scripts/nav.sh"
    stop_grace_s: float = 10.0           # per-SIGINT wait for ros2 launch
    arrival_tol_m: float = 0.8           # odometry-oracle arrival tolerance
    goto_timeout_s: float = 180.0        # default bound on a blocking route drive
    poll_hz: float = 5.0                 # arrival poll cadence


@dataclasses.dataclass(frozen=True)
class RouteStatus:
    """One immutable snapshot of the route session (tool/status surface)."""

    state: str
    pid: int | None
    reached: bool
    goal: tuple[float, float] | None
    far_reach: bool
    runtime_s: float | None
    reason: str
    oracle_attached: bool


def attach_route_oracle(
    node: Any,
    goal_topic: str,
    odom_topic: str,
    reach_topic: str,
    on_odom: Callable[[Any], None],
    on_reach: Callable[[Any], None],
) -> Any:
    """Create the /goal_point publisher + subscribe odom/reach on *node*.

    Returns the goal publisher on success, or None if rclpy/messages are
    unavailable or the wiring fails (a blind oracle the manager must refuse).
    """
    if node is None:
        return None
    try:
        from geometry_msgs.msg import PointStamped
        from nav_msgs.msg import Odometry
        from rclpy.qos import QoSProfile, ReliabilityPolicy
        from std_msgs.msg import Bool

        reliable = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, depth=5)
        goal_pub = node.create_publisher(PointStamped, goal_topic, reliable)
        sensor = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=10)
        node.create_subscription(Odometry, odom_topic, on_odom, sensor)
        node.create_subscription(Bool, reach_topic, on_reach, 10)
        return goal_pub
    except Exception as exc:  # noqa: BLE001 — attach boundary, fail loud (return None)
        logger.warning("route oracle attach failed: %s", exc)
        return None


def publish_goal_point(
    node: Any, goal_pub: Any, frame: str, x: float, y: float
) -> None:
    """Publish one PointStamped goal to far_planner in *frame* (never raise)."""
    try:
        from geometry_msgs.msg import PointStamped

        msg = PointStamped()
        msg.header.frame_id = frame
        if node is not None:
            try:
                msg.header.stamp = node.get_clock().now().to_msg()
            except Exception:  # noqa: BLE001 — stamp is best-effort
                pass
        msg.point.x = float(x)
        msg.point.y = float(y)
        msg.point.z = 0.0
        goal_pub.publish(msg)
    except Exception as exc:  # noqa: BLE001 — publish boundary, never crash
        logger.warning("route goal publish failed: %s", exc)
