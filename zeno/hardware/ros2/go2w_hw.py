# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware — real Unitree Go2W driver over the RUNNING nav stack (P5.4).

CEO ruling 2026-07-10: real-hardware nav integration runs on THIS NUC through
the already-running nav stack (``~/Z-Navigation-Stack`` via ``nav.sh``). There
is NO ``unitree_sdk2`` dependency and NO new ROS interface — this driver only
CONSUMES the robot's existing topics/services:

Publishes
    /way_point        geometry_msgs/PointStamped (frame 'map')
        A latched pursuit goal: publish ONCE and the local planner drives the
        robot until arrival or cancel. navigate_to sends it once, then polls
        odometry (never a re-publish loop — that is the sim FAR-probe pattern).
    /teleop_cmd_vel   geometry_msgs/Twist
        Direct body velocity. The robot-side cmd_vel guard clamps to 0.6 m/s and
        enforces a 0.4 s deadman, so walk() refreshes at >=4 Hz; "stop" is simply
        to stop publishing (the deadman halts the robot), with one final zero.

Subscribes
    /state_estimation nav_msgs/Odometry (map frame, 10-50 Hz)
        Pose truth — the REAL verify oracle (Inv-1: no /gt on hardware).

Calls (std_srvs/Trigger)
    /standup /liedown /estop /estop_release /manual /nav_cancel
        estop  = latched zero; manual = guard silent (hardware-remote takeover);
        estop_release (== resume) resumes both; nav_cancel clears the latched
        waypoint. Semantics mirror ``nav.sh`` so the two control faces agree.

This driver implements the ``BaseProtocol`` surface skills/worlds actually use
(walk / set_velocity / navigate_to / get_position / get_heading / get_odometry /
stop) and reuses the ``ensure_finite_*`` guards. rclpy and all ROS message/
service imports are LAZY (module import must not require a sourced ROS env — same
contract as ``nav_client.py``); the shared process ``Ros2Runtime`` owns the
executor + spin thread so this node never calls ``rclpy.spin`` itself.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Callable

from zeno.hardware.base import (
    ensure_finite_base_velocity,
    ensure_finite_nav_goal,
)
from zeno.hardware.ros2.go2w_hw_camera import CameraMixin
from zeno.hardware.ros2.go2w_hw_services import TriggerServiceMixin
from zeno.hardware.ros2.runtime import get_ros2_runtime

logger = logging.getLogger(__name__)


class Go2WHardware(CameraMixin, TriggerServiceMixin):
    """Real Go2W base driver — everything through the running nav stack.

    Safe to construct with no ROS env (lazy imports). ``connect()`` wires the
    node, publishers, odometry subscriber and Trigger clients onto the shared
    runtime; until then every ROS-touching call degrades to a no-op / False and
    never raises (so an offline REPL or a unit test stays quiet).

    The std_srvs/Trigger stance & safety helpers (standup/liedown/estop/
    estop_release/resume/manual/nav_cancel) come from ``TriggerServiceMixin``.
    """

    _NODE_NAME: str = "zeno_go2w_hw"

    # --- Robot-side cmd_vel guard mirror (topic contract, not re-implemented
    #     safety: the AUTHORITATIVE clamp + deadman live in the robot bridge per
    #     AGENTS Invariant 6; these keep us from ever exceeding them from here). ---
    MAX_LINEAR_MPS: float = 0.6        # guard clamps linear speed to 0.6 m/s
    MAX_YAW_RPS: float = 1.5           # conservative yaw-rate ceiling
    DEADMAN_S: float = 0.4             # guard stops the robot 0.4 s after last cmd
    TELEOP_PERIOD_S: float = 0.2       # 5 Hz refresh — strictly < deadman, >= 4 Hz

    # --- navigate_to poll defaults ---
    ARRIVAL_RADIUS_M: float = 0.8      # real-oracle arrival tolerance
    STALL_TIMEOUT_S: float = 10.0      # no-progress window before aborting
    STALL_EPS_M: float = 0.1           # min distance decrease counted as progress

    # Topics / services (the robot's EXISTING interface — we add none).
    WAYPOINT_TOPIC: str = "/way_point"
    TELEOP_TOPIC: str = "/teleop_cmd_vel"
    ODOM_TOPIC: str = "/state_estimation"
    _TRIGGER_SERVICES: tuple[str, ...] = (
        "/standup", "/liedown", "/estop", "/estop_release", "/manual", "/nav_cancel",
    )

    def __init__(self) -> None:
        from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

        self._node: Any = None
        self._waypoint_pub: Any = None
        self._teleop_pub: Any = None
        self._clients: dict[str, Any] = {}
        self._connected: bool = False
        self._shared_runtime_used: bool = False
        # Cached pose truth from /state_estimation (GIL-protected scalar writes).
        self._position: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._heading: float = 0.0
        self._last_odom: Any = None
        self._odom_arrival_mono: float | None = None
        # Operator-interrupt seam: set by cancel_navigation() (Ctrl+C handler,
        # stop skill); navigate_to's poll loop exits promptly when set.
        self._nav_abort = __import__("threading").Event()
        self._moved_origin: tuple[float, float] | None = None
        # turned() oracle anchor: odometry heading sampled by rotate() at
        # command start (None until the first rotation is commanded). The
        # actor can trigger a rotation but cannot author this value (Inv-1).
        self.rotate_anchor_yaw: float | None = None
        # Eyes: the D435i RGB source (offline-safe; its Image subscription rides
        # this node + the shared runtime on connect, like _on_odom — no new node).
        self._camera = Go2WCamera()

    # ------------------------------------------------------------------
    # Identity / capabilities
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "go2w_hw"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def supports_holonomic(self) -> bool:
        return True  # Go2W can strafe

    @property
    def supports_lidar(self) -> bool:
        return False  # lidar is consumed by the nav stack, not exposed here

    # ------------------------------------------------------------------
    # Lifecycle  (camera accessors: CameraMixin / go2w_hw_camera.py)
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Wire node + pub/sub + Trigger clients onto the shared ROS2 runtime.

        Best-effort: if rclpy or the ROS env is unavailable the driver stays
        disconnected (a debug line, not an error — a bridge-absent host must not
        bleed ERROR into the REPL), exactly like Go2ROS2Proxy.connect.
        """
        try:
            import rclpy
            from rclpy.node import Node
            from rclpy.qos import QoSProfile, ReliabilityPolicy
            from geometry_msgs.msg import PointStamped, Twist
            from nav_msgs.msg import Odometry
            from std_srvs.srv import Trigger

            if not rclpy.ok():
                rclpy.init()
            node = Node(self._NODE_NAME)

            reliable = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, depth=5)
            sensor = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=10)

            self._waypoint_pub = node.create_publisher(
                PointStamped, self.WAYPOINT_TOPIC, reliable
            )
            self._teleop_pub = node.create_publisher(Twist, self.TELEOP_TOPIC, reliable)
            node.create_subscription(Odometry, self.ODOM_TOPIC, self._on_odom, sensor)
            for svc in self._TRIGGER_SERVICES:
                self._clients[svc] = node.create_client(Trigger, svc)

            self._node = node
            # Attach the D435i RGB sub onto this node (best-effort — a down camera
            # leaves has_camera() False, never fails connect).
            self._camera.attach(node)
            get_ros2_runtime().add_node(node)
            self._shared_runtime_used = True
            self._connected = True
            logger.info("Go2WHardware connected (domain from sourced ROS env)")
        except ImportError as exc:
            logger.debug("Go2WHardware: ROS2 unavailable, running offline: %s", exc)
            self._connected = False
        except Exception as exc:  # noqa: BLE001 — connection boundary
            logger.error("Go2WHardware connect failed: %s", exc)
            self._connected = False

    def disconnect(self) -> None:
        """Detach from the shared runtime and destroy the node (idempotent)."""
        if self._shared_runtime_used and self._node is not None:
            try:
                get_ros2_runtime().remove_node(self._node)
            except Exception:  # noqa: BLE001 — best-effort teardown
                pass
        self._shared_runtime_used = False
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception:  # noqa: BLE001
                pass
            self._node = None
        self._connected = False

    def _install_node_for_test(self, node: Any) -> None:
        """Test seam: attach a mock node + its publishers/clients without ROS.

        Mirrors what connect() wires, but drives the (mocked) node's factories
        directly so seam tests never construct a real rclpy Node. Not used in
        production — connect() is the real path.
        """
        self._node = node
        self._waypoint_pub = node.create_publisher(None, self.WAYPOINT_TOPIC, 10)
        self._teleop_pub = node.create_publisher(None, self.TELEOP_TOPIC, 10)
        node.create_subscription(None, self.ODOM_TOPIC, self._on_odom, 10)
        for svc in self._TRIGGER_SERVICES:
            self._clients[svc] = node.create_client(None, svc)
        self._camera.attach_node_for_test(node)
        self._connected = True

    # ------------------------------------------------------------------
    # Odometry callback + state readback (the real verify oracle)
    # ------------------------------------------------------------------

    def _on_odom(self, msg: Any) -> None:
        """Cache pose + heading from a /state_estimation Odometry message."""
        import time as _t
        self._last_odom = msg
        self._odom_arrival_mono = _t.monotonic()
        p = msg.pose.pose.position
        self._position = (float(p.x), float(p.y), float(p.z))
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self._heading = math.atan2(siny_cosp, cosy_cosp)

    def cancel_navigation(self) -> None:
        """Unblock a running navigate_to NOW and clear the latched goal.

        Field trace 2026-07-10: the REPL sat inside the poll loop for a 5 m
        walk with no way to interject; Ctrl+C killed the whole CLI. This is
        the safe unwind: flag the loop, then /nav_cancel so the local planner
        stops pursuing the abandoned waypoint.
        """
        self._nav_abort.set()
        try:
            self.nav_cancel()
        except Exception:  # noqa: BLE001 — cancel must never raise
            pass

    def odom_age_s(self) -> float | None:
        """Seconds since the last odometry ARRIVED — None if never received.

        THE liveness oracle. Field bug 2026-07-10: liveness checks that fell
        back to get_position() were永真 (it returns default zeros before any
        odometry), so a DOWN stack graded stack_ready()==True and misled the
        planner away from bringup.
        """
        if self._odom_arrival_mono is None:
            return None
        import time as _t
        return _t.monotonic() - self._odom_arrival_mono

    def get_position(self) -> list[float]:
        """Return [x, y, z] in the map frame from the latest odometry."""
        return list(self._position)

    def get_heading(self) -> float:
        """Return the latest yaw (radians) from odometry."""
        return self._heading

    def get_velocity(self) -> list[float]:
        """Return [vx, vy, vz] from the latest odometry twist (world frame)."""
        if self._last_odom is None:
            return [0.0, 0.0, 0.0]
        t = self._last_odom.twist.twist.linear
        return [float(t.x), float(t.y), float(t.z)]

    def get_odometry(self) -> Any:
        """Return a zeno.core.types.Odometry snapshot from the cache."""
        from zeno.core.types import Odometry

        x, y, z = self._position
        if self._last_odom is None:
            return Odometry(timestamp=time.time(), x=x, y=y, z=z)
        o = self._last_odom.pose.pose.orientation
        t = self._last_odom.twist.twist
        return Odometry(
            timestamp=time.time(), x=x, y=y, z=z,
            qx=float(o.x), qy=float(o.y), qz=float(o.z), qw=float(o.w),
            vx=float(t.linear.x), vy=float(t.linear.y), vz=float(t.linear.z),
            vyaw=float(t.angular.z),
        )

    # ------------------------------------------------------------------
    # Navigation — latched /way_point + odometry poll (nav_client template)
    # ------------------------------------------------------------------

    def navigate_to(
        self,
        x: float,
        y: float,
        timeout: float = 120.0,
        poll_hz: float = 5.0,
        stall_timeout: float | None = None,
        on_progress: Callable[[float, float], None] | None = None,
    ) -> bool:
        """Drive to map-frame (x, y): publish /way_point ONCE, poll odometry.

        Latched pursuit — the local planner keeps chasing the single waypoint, so
        we publish it exactly once and then watch /state_estimation until the
        robot is within ARRIVAL_RADIUS_M (True), the timeout expires, or progress
        stalls for ``stall_timeout`` seconds. On timeout/stall we clear the latch
        via /nav_cancel so the robot does not keep driving to an abandoned goal.

        Returns True only on odometry-verified arrival (the real oracle).
        """
        ensure_finite_nav_goal(x, y, "Go2WHardware.navigate_to")
        if self._node is None or self._waypoint_pub is None:
            logger.warning("Go2WHardware.navigate_to: not connected")
            return False

        self._publish_waypoint(x, y)
        logger.info("Go2WHardware: /way_point -> (%.2f, %.2f), timeout=%.0fs", x, y, timeout)

        self._nav_abort.clear()
        period = 1.0 / max(poll_hz, 1.0)
        stall_win = self.STALL_TIMEOUT_S if stall_timeout is None else stall_timeout
        start = time.monotonic()
        last_dist = float("inf")
        stall_accum = 0.0
        last_progress_cb = start

        while time.monotonic() - start < timeout:
            if self._nav_abort.is_set():
                logger.info("Go2WHardware: navigation cancelled by operator")
                return False
            time.sleep(period)
            px, py, _ = self._position
            dist = math.hypot(px - x, py - y)

            now = time.monotonic()
            if on_progress is not None and now - last_progress_cb >= 2.0:
                last_progress_cb = now
                on_progress(dist, now - start)

            if dist < self.ARRIVAL_RADIUS_M:
                logger.info("Go2WHardware: arrived (dist=%.2fm)", dist)
                return True

            if dist < last_dist - self.STALL_EPS_M:
                stall_accum = 0.0
            else:
                stall_accum += period
            last_dist = dist
            if stall_accum >= stall_win:
                logger.warning(
                    "Go2WHardware: stalled %.1fs at dist=%.2fm — cancelling",
                    stall_accum, dist,
                )
                self.nav_cancel()
                return False

        logger.warning("Go2WHardware: navigate_to timeout — cancelling latch")
        self.nav_cancel()
        return False

    def _publish_waypoint(self, x: float, y: float) -> None:
        """Publish one PointStamped to /way_point in the map frame."""
        from geometry_msgs.msg import PointStamped

        msg = PointStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.point.x = float(x)
        msg.point.y = float(y)
        msg.point.z = 0.0
        self._waypoint_pub.publish(msg)

    # ------------------------------------------------------------------
    # Direct velocity — /teleop_cmd_vel, clamped, >=4 Hz cadence
    # ------------------------------------------------------------------

    def set_velocity(self, vx: float, vy: float, vyaw: float) -> None:
        """Publish one clamped Twist to /teleop_cmd_vel (non-blocking).

        Rejects non-finite components at the boundary (fail-open guard), then
        clamps into the robot-side guard envelope before publishing so we never
        even ask for more than the guard would allow.
        """
        ensure_finite_base_velocity(vx, vy, vyaw, "Go2WHardware.set_velocity")
        if self._node is None or self._teleop_pub is None:
            return
        from geometry_msgs.msg import Twist

        msg = Twist()
        msg.linear.x = _clamp(vx, self.MAX_LINEAR_MPS)
        msg.linear.y = _clamp(vy, self.MAX_LINEAR_MPS)
        msg.angular.z = _clamp(vyaw, self.MAX_YAW_RPS)
        self._teleop_pub.publish(msg)

    def walk(
        self,
        vx: float = 0.0,
        vy: float = 0.0,
        vyaw: float = 0.0,
        duration: float = 1.0,
    ) -> bool:
        """Hold a body velocity for *duration* s, refreshing >=4 Hz, then stop.

        The robot-side guard drops the robot 0.4 s after the last /teleop_cmd_vel,
        so we re-send every TELEOP_PERIOD_S (5 Hz) to keep it fresh mid-stride. A
        final zero frame ends the motion cleanly; after that "stop" is just the
        absence of new commands (the deadman does the rest).
        """
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self.set_velocity(vx, vy, vyaw)
            time.sleep(self.TELEOP_PERIOD_S)
        self.set_velocity(0.0, 0.0, 0.0)
        return True

    def rotate(self, delta_yaw_rad: float, yaw_rate: float = 0.5) -> bool:
        """Rotate IN PLACE by *delta_yaw_rad* (signed: + = left/CCW, - = right/CW).

        walk()-cadence template on the same guard contract: publish an
        angular-ONLY Twist on /teleop_cmd_vel every TELEOP_PERIOD_S (5 Hz —
        strictly beating the 0.4 s deadman) for |delta|/rate seconds, then stop
        publishing (one final zero frame; the deadman is the real stop).

        Progress is tracked on get_heading() odometry with wrap-around handling
        (heading deltas wrapped into (-pi, pi] and accumulated), so the loop
        stops EARLY the moment odometry says the turn is done. Honors the
        _nav_abort seam — cancel_navigation() (stop skill / Ctrl+C twin)
        unblocks a rotation exactly like a navigate — and fails fast when this
        driver's own E-stop latch is set (the guard would silently eat the
        commands; field trace 2026-07-10).

        Returns False on not-connected / E-stop latch / operator cancel; True
        when the command window completed. An open-loop completion with dead
        odometry is NOT proof of rotation — grade with the turned() oracle.
        """
        if not (math.isfinite(delta_yaw_rad) and math.isfinite(yaw_rate)):
            raise ValueError("Go2WHardware.rotate: non-finite rotation request")
        if yaw_rate <= 0.0:
            raise ValueError("Go2WHardware.rotate: yaw_rate must be > 0")
        if self._node is None or self._teleop_pub is None:
            logger.warning("Go2WHardware.rotate: not connected")
            return False
        if self.estop_latched:
            logger.warning("Go2WHardware.rotate: E-stop latched — refusing motion")
            return False
        target = abs(float(delta_yaw_rad))
        if target == 0.0:
            return True
        rate = min(float(yaw_rate), self.MAX_YAW_RPS)
        sign = 1.0 if delta_yaw_rad > 0.0 else -1.0
        duration = target / rate
        logger.info("Go2WHardware: rotate %.1f deg @ %.2f rad/s (~%.1fs)",
                    math.degrees(delta_yaw_rad), rate, duration)

        self._nav_abort.clear()
        prev = float(self.get_heading())
        # Anchor AFTER the guards — a refused rotation must never re-anchor
        # the turned() oracle onto the current heading (it could fake-pass a
        # later check). Field trace 2026-07-13: verify's first-call origin
        # capture sampled the POST-turn heading, graded False, and the model
        # re-ran the turn — 90° of physical rotation for a 45° ask.
        self.rotate_anchor_yaw = prev
        turned_rad = 0.0
        deadline = time.monotonic() + duration
        cancelled = False
        while time.monotonic() < deadline:
            if self._nav_abort.is_set():
                logger.info("Go2WHardware: rotation cancelled by operator")
                cancelled = True
                break
            self.set_velocity(0.0, 0.0, sign * rate)
            time.sleep(self.TELEOP_PERIOD_S)
            cur = float(self.get_heading())
            turned_rad += _wrap_pi(cur - prev)
            prev = cur
            if abs(turned_rad) >= target:
                break  # odometry-confirmed arrival — stop early
        # Final zero frame, then silence: the robot-side deadman does the rest.
        self.set_velocity(0.0, 0.0, 0.0)
        return not cancelled

    def stop(self) -> None:
        """Emergency-safe stop: publish one zero Twist; never raise.

        Not a latched E-stop (use estop() for that) — this halts teleop motion.
        Stopping further is the deadman's job once we stop publishing.
        """
        try:
            if self._node is not None and self._teleop_pub is not None:
                self.set_velocity(0.0, 0.0, 0.0)
        except Exception:  # noqa: BLE001 — stop() must never raise (BaseProtocol)
            pass

    # Trigger-service helpers (standup/liedown/estop/estop_release/resume/manual/
    # nav_cancel) are provided by TriggerServiceMixin (go2w_hw_services.py).


def _clamp(v: float, limit: float) -> float:
    """Clamp *v* into [-limit, +limit]. (Finite already ensured upstream.)"""
    return max(-limit, min(limit, float(v)))


def _wrap_pi(angle: float) -> float:
    """Wrap an angle delta into (-pi, pi] — the shortest signed rotation."""
    return math.atan2(math.sin(angle), math.cos(angle))
