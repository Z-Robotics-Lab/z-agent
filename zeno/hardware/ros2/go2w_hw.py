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
    # Arrival radius, measured on /state_estimation (SENSOR pose, 0.2 m ahead
    # of base_link). Nav-stack forensics 2026-07-13: the planner's own
    # goalReachedThreshold is 0.3 (base frame) — 0.8 here declared "arrived"
    # up to ~1 m short in base terms (the CEO's "不准确"). Floor is
    # goalReachedThreshold + 0.2 frame skew + noise, so keep >= 0.35.
    ARRIVAL_RADIUS_M: float = 0.4      # real-oracle arrival tolerance
    STALL_TIMEOUT_S: float = 10.0      # no-progress window before aborting
    STALL_EPS_M: float = 0.1           # min distance decrease counted as progress

    # --- Operator RViz-goal classification ---
    #: A /way_point echo matching our own publish within this window (and ~coords)
    #: is our own round-trip, not an operator click.
    OWN_ECHO_WINDOW_S: float = 1.0
    OWN_ECHO_EPS_M: float = 1e-4       # ~coordinate-match tolerance for an echo

    # Topics / services (the robot's EXISTING interface — we add none).
    WAYPOINT_TOPIC: str = "/way_point"
    GOALPOINT_TOPIC: str = "/goal_point"   # far_planner's goal input (park seam)
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
        # Operator RViz-goal seam (CEO field ask 2026-07-14): the driver
        # subscribes its OWN /way_point and classifies each frame. A publish of
        # our own records (x, y, monotonic) so the echo is ignored; while the
        # route overlay streams /way_point (route_overlay_active, set by the
        # route manager) frames are plumbing; anything else is an operator click
        # stored as external_goal. navigate_to yields to a mid-drive external
        # goal (nav_overridden) WITHOUT nav_cancel — the operator's latched goal
        # must keep driving the robot.
        self._own_goal: tuple[float, float, float] | None = None  # x, y, mono
        self._external_goal: tuple[float, float, float] | None = None
        self._goalpoint_pub: Any = None
        #: Last park order (x, y, mono): far_planner echoes /way_point at these
        #: coords for a beat after parking — plumbing, not an operator click.
        self._park_goal: tuple[float, float, float] | None = None
        #: Set/cleared by Go2WRouteManager while far_planner republishes
        #: /way_point toward its route — those frames are plumbing, not clicks.
        self.route_overlay_active: bool = False
        #: True when the LAST navigate_to yielded to an operator RViz goal.
        #: Cleared at each navigate start (it describes THIS drive).
        self.nav_overridden: bool = False
        # Operator-interrupt seam: set by cancel_navigation() (Ctrl+C handler,
        # stop skill); navigate_to's poll loop exits promptly when set.
        self._nav_abort = __import__("threading").Event()
        # moved() oracle anchor: odometry position sampled by navigate_to()/
        # walk() at command start (None until the first move is commanded).
        # The actor can trigger a move but cannot author this value (Inv-1).
        self.move_anchor_xy: tuple[float, float] | None = None
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
            # Park seam: re-goal the resident far_planner to the CURRENT pose
            # before any direct motion so its stale-goal republish loop can
            # never fight our waypoint (single-author rule, field 2026-07-14).
            self._goalpoint_pub = node.create_publisher(
                PointStamped, self.GOALPOINT_TOPIC, reliable
            )
            self._teleop_pub = node.create_publisher(Twist, self.TELEOP_TOPIC, reliable)
            node.create_subscription(Odometry, self.ODOM_TOPIC, self._on_odom, sensor)
            # Listen to our OWN /way_point so an operator RViz click (which
            # OVERWRITES our latched goal) is seen — reliable QoS like the
            # publisher so no click frame is dropped.
            node.create_subscription(
                PointStamped, self.WAYPOINT_TOPIC, self._on_waypoint, reliable
            )
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
        self._goalpoint_pub = node.create_publisher(None, self.GOALPOINT_TOPIC, 10)
        self._teleop_pub = node.create_publisher(None, self.TELEOP_TOPIC, 10)
        node.create_subscription(None, self.ODOM_TOPIC, self._on_odom, 10)
        node.create_subscription(None, self.WAYPOINT_TOPIC, self._on_waypoint, 10)
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

    def clear_all_goals(self) -> None:
        """THE clean slate (CEO 2026-07-14): kill every cached goal everywhere.

        One call sweeps all four goal caches: ① aborts any in-flight
        navigate/rotate/reverse/dock poll loop (_nav_abort), ② clears the
        local planner's latched /way_point (/nav_cancel), ③ parks the
        resident far_planner (stale route goals stop republishing), ④ drops
        the recorded operator RViz goal. Deliberately does NOT touch the
        E-stop latch — releasing an E-stop stays its own explicit action
        (resume). Best-effort throughout; never raises.
        """
        self.cancel_navigation()          # ① in-flight loops + ② /nav_cancel
        self.park_route_planner()         # ③ far_planner stale goals
        try:
            self.clear_external_goal()    # ④ operator-goal record
        except Exception:  # noqa: BLE001 — sweep must never raise
            pass
        logger.info("Go2WHardware: ALL goals cleared (clean slate)")

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

        # Anchor AFTER the guards — a refused command must never re-anchor the
        # moved() oracle. Twin of rotate_anchor_yaw (field trace 2026-07-13):
        # verify runs AFTER the skill, so a verify-side origin capture samples
        # the POST-motion pose, grades False, and the model re-runs the walk.
        px, py, _ = self._position
        self.move_anchor_xy = (px, py)
        # This drive's operator-override verdict starts clean; remember the
        # external-goal timestamp at start so only a goal arriving AFTER this
        # navigate began counts as a mid-drive takeover (a pre-existing one is
        # not this drive's business).
        self.nav_overridden = False
        prev_ext = self._external_goal
        self.park_route_planner()  # single-author rule: silence far_planner
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
            # Operator RViz takeover: an external /way_point arrived AFTER this
            # navigate started (a NEW record vs prev_ext). The operator's click
            # already OVERWROTE our latched goal and is driving the robot — stop
            # polling OUR goal and yield, but do NOT nav_cancel (that would kill
            # the operator's goal too). The skill layer reports the honest yield.
            if self._external_goal is not None and self._external_goal is not prev_ext:
                gx, gy, _gt = self._external_goal
                logger.info("Go2WHardware: yielding to operator RViz goal "
                            "(%.2f, %.2f) — NOT cancelling (operator drives)", gx, gy)
                self.nav_overridden = True
                return False
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

    def park_route_planner(self) -> None:
        """Silence the resident far_planner: re-goal it to the CURRENT pose.

        far_planner republishes /way_point toward its last goal FOREVER — a
        stale goal fights every direct move on the same channel (field
        2026-07-14: 3m in a staggering 24s, then spin-in-place chasing a goal
        BEHIND). Publishing /goal_point at our own position makes it
        instantly 'reached' and silent. Harmless no-op when far_planner is
        absent (no subscriber) or the driver is disconnected. Never raises.
        """
        if self._node is None or self._goalpoint_pub is None:
            return
        try:
            from geometry_msgs.msg import PointStamped

            px, py, _ = self._position
            msg = PointStamped()
            msg.header.frame_id = "map"
            msg.header.stamp = self._node.get_clock().now().to_msg()
            msg.point.x, msg.point.y, msg.point.z = float(px), float(py), 0.0
            self._park_goal = (float(px), float(py), time.monotonic())
            self._goalpoint_pub.publish(msg)
            logger.debug("Go2WHardware: route planner parked at (%.2f, %.2f)",
                         px, py)
        except Exception:  # noqa: BLE001 — parking is best-effort protection
            pass

    def _publish_waypoint(self, x: float, y: float) -> None:
        """Publish one PointStamped to /way_point in the map frame."""
        from geometry_msgs.msg import PointStamped

        msg = PointStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.point.x = float(x)
        msg.point.y = float(y)
        msg.point.z = 0.0
        # Record this as our OWN goal so its /way_point echo is not misread as
        # an operator RViz click (own-echo suppression in _on_waypoint).
        self._own_goal = (float(x), float(y), time.monotonic())
        self._waypoint_pub.publish(msg)

    # ------------------------------------------------------------------
    # Operator RViz-goal detection (own /way_point subscription)
    # ------------------------------------------------------------------

    def _on_waypoint(self, msg: Any) -> None:
        """Classify a /way_point frame: own echo / route plumbing / operator.

        OWN ECHO — matches our last _publish_waypoint within OWN_ECHO_WINDOW_S
        and ~OWN_ECHO_EPS_M coords -> ignore. ROUTE PLUMBING — far_planner
        streams /way_point toward its route while the overlay is active
        (route_overlay_active) -> ignore. Otherwise EXTERNAL: an operator clicked
        a goal in RViz, which OVERWROTE our latched waypoint — store it so
        navigate_to can yield and the status line can surface it. Executor-thread
        callback: tiny, never raises.
        """
        try:
            x = float(msg.point.x)
            y = float(msg.point.y)
        except Exception:  # noqa: BLE001 — malformed frame, ignore
            return
        if self.route_overlay_active:
            return  # far_planner route plumbing, not an operator click
        park = self._park_goal
        if park is not None:
            kx, ky, kt = park
            if (time.monotonic() - kt <= 5.0
                    and abs(x - kx) <= 0.05 and abs(y - ky) <= 0.05):
                return  # far_planner echoing our park order — plumbing
        own = self._own_goal
        if own is not None:
            ox, oy, ot = own
            if (time.monotonic() - ot <= self.OWN_ECHO_WINDOW_S
                    and abs(x - ox) <= self.OWN_ECHO_EPS_M
                    and abs(y - oy) <= self.OWN_ECHO_EPS_M):
                return  # our own publish round-tripping back
        self._external_goal = (x, y, time.monotonic())
        logger.info("Go2WHardware: EXTERNAL /way_point (operator RViz click) "
                    "-> (%.2f, %.2f) — will yield", x, y)

    def external_goal_info(self) -> tuple[float, float, float] | None:
        """Operator RViz goal as (x, y, age_s), or None when never/cleared."""
        ext = self._external_goal
        if ext is None:
            return None
        return (ext[0], ext[1], time.monotonic() - ext[2])

    def clear_external_goal(self) -> None:
        """Consume/forget the recorded operator goal (idempotent)."""
        self._external_goal = None

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
        # walk() is the other displacement command — anchor the moved() oracle
        # like navigate_to (rotate stays hands-off: in-place turns don't displace).
        px, py, _ = self._position
        self.move_anchor_xy = (px, py)
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            self.set_velocity(vx, vy, vyaw)
            time.sleep(self.TELEOP_PERIOD_S)
        self.set_velocity(0.0, 0.0, 0.0)
        return True

    #: Blind-escape reverse speed ceiling. The Mid-360 is front-mounted and
    #: pitched 20° down-forward — the robot is BLIND behind (CEO safety
    #: ruling 2026-07-13): reverse is never a driving mode, only a short
    #: escape crawl the operator watches with the E-stop in hand.
    BLIND_REVERSE_SPEED_CAP: float = 0.3

    def reverse_blind(self, distance_m: float, speed: float = 0.25) -> bool:
        """Crawl STRAIGHT back *distance_m* metres on the direct teleop channel.

        Escape-only maneuver — the planner never drives this robot backward
        (nav stack is forward-only; rear = lidar blind zone). walk()-cadence
        contract: linear-only Twist (vx<0) on /teleop_cmd_vel at 5 Hz, one
        final zero then silence. Odometry-tracked EARLY stop when the
        displacement covers the request; open-loop window capped at
        distance/speed * 1.6 if odometry freezes. Honors _nav_abort
        (cancel_navigation / Ctrl+C) and refuses on the E-stop latch.
        Anchors move_anchor_xy so moved() grades the escape (Inv-1).
        """
        if not (math.isfinite(distance_m) and math.isfinite(speed)):
            raise ValueError("Go2WHardware.reverse_blind: non-finite request")
        if self._node is None or self._teleop_pub is None:
            logger.warning("Go2WHardware.reverse_blind: not connected")
            return False
        if self.estop_latched:
            logger.warning(
                "Go2WHardware.reverse_blind: E-stop latched — refusing motion")
            return False
        target = abs(float(distance_m))
        if target == 0.0:
            return True
        v = min(max(float(speed), 0.05), self.BLIND_REVERSE_SPEED_CAP)
        logger.info("Go2WHardware: BLIND reverse %.2fm @ %.2f m/s (rear is a "
                    "sensor blind zone — escape maneuver)", target, v)
        self.park_route_planner()  # single-author rule: silence far_planner
        self._nav_abort.clear()
        sx, sy, _ = self._position
        self.move_anchor_xy = (sx, sy)
        deadline = time.monotonic() + (target / v) * 1.6
        cancelled = False
        while time.monotonic() < deadline:
            if self._nav_abort.is_set():
                logger.info("Go2WHardware: blind reverse cancelled by operator")
                cancelled = True
                break
            self.set_velocity(-v, 0.0, 0.0)
            time.sleep(self.TELEOP_PERIOD_S)
            px, py, _ = self._position
            if math.hypot(px - sx, py - sy) >= target:
                break  # odometry-confirmed arrival — stop early
        self.set_velocity(0.0, 0.0, 0.0)
        return not cancelled

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

        self.park_route_planner()  # single-author rule: silence far_planner
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

    # --- Docking (manipulation-grade precision arrival, CEO 2026-07-14) ---
    DOCK_TOL_M: float = 0.08           # position tolerance at the station
    DOCK_YAW_TOL_RAD: float = 0.05     # ~3° heading tolerance
    DOCK_SPEED: float = 0.15           # slow omni servo (well under guard 0.6)
    DOCK_YAW_RATE: float = 0.4         # slow yaw servo
    DOCK_MAX_RANGE_M: float = 1.0      # docking is a last-metre maneuver

    def dock_to(self, x: float, y: float, yaw: float | None = None,
                timeout: float = 30.0) -> bool:
        """Precision servo to map-frame (x, y[, yaw]) — the fine stage AFTER
        coarse navigation, for manipulation stations.

        Omni body-frame velocities on the direct teleop channel at 5 Hz,
        computed each tick from live odometry (the pure-localization prior
        map keeps the map frame honest): P-servo toward the target, clamped
        to DOCK_SPEED / DOCK_YAW_RATE, until within DOCK_TOL_M (and the
        target heading within DOCK_YAW_TOL_RAD when *yaw* is given).

        Guards: refuses beyond DOCK_MAX_RANGE_M (coarse nav first), refuses
        on the E-stop latch, clears any latched waypoint (nav_cancel) so the
        planner cannot fight the servo, honors _nav_abort (stop/Ctrl+C).
        Anchors move_anchor_xy AFTER the guards (moved() oracle).
        """
        if not (math.isfinite(x) and math.isfinite(y)
                and (yaw is None or math.isfinite(yaw))):
            raise ValueError("Go2WHardware.dock_to: non-finite target")
        if self._node is None or self._teleop_pub is None:
            logger.warning("Go2WHardware.dock_to: not connected")
            return False
        if self.estop_latched:
            logger.warning("Go2WHardware.dock_to: E-stop latched — refusing")
            return False
        px, py, _ = self._position
        if math.hypot(px - x, py - y) > self.DOCK_MAX_RANGE_M:
            logger.warning("Go2WHardware.dock_to: target %.2fm away (> %.1fm) — "
                           "coarse-navigate first", math.hypot(px - x, py - y),
                           self.DOCK_MAX_RANGE_M)
            return False
        self.park_route_planner()  # single-author rule: silence far_planner
        try:
            self.nav_cancel()  # clear the latched waypoint — no planner fights
        except Exception:  # noqa: BLE001 — cancel is best-effort
            pass
        self.move_anchor_xy = (px, py)
        self._nav_abort.clear()
        logger.info("Go2WHardware: docking to (%.2f, %.2f%s)", x, y,
                    f", yaw={yaw:.2f}" if yaw is not None else "")
        gain_v, gain_w = 1.2, 1.5
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._nav_abort.is_set():
                logger.info("Go2WHardware: docking cancelled by operator")
                self.set_velocity(0.0, 0.0, 0.0)
                return False
            px, py, _ = self._position
            cur_yaw = float(self._heading)
            dx, dy = x - px, y - py
            dist = math.hypot(dx, dy)
            yaw_err = 0.0
            if yaw is not None:
                yaw_err = math.atan2(math.sin(yaw - cur_yaw),
                                     math.cos(yaw - cur_yaw))
            if dist <= self.DOCK_TOL_M and abs(yaw_err) <= self.DOCK_YAW_TOL_RAD:
                self.set_velocity(0.0, 0.0, 0.0)
                logger.info("Go2WHardware: docked (dist=%.3fm yaw_err=%.3frad)",
                            dist, yaw_err)
                return True
            # map-frame delta -> body frame (omni: translate + rotate together)
            bx = math.cos(-cur_yaw) * dx - math.sin(-cur_yaw) * dy
            by = math.sin(-cur_yaw) * dx + math.cos(-cur_yaw) * dy
            vx = _clamp(gain_v * bx, self.DOCK_SPEED)
            vy = _clamp(gain_v * by, self.DOCK_SPEED)
            wz = _clamp(gain_w * yaw_err, self.DOCK_YAW_RATE)
            if dist <= self.DOCK_TOL_M:
                vx = vy = 0.0  # position done — finish the heading only
            self.set_velocity(vx, vy, wz)
            time.sleep(self.TELEOP_PERIOD_S)
        self.set_velocity(0.0, 0.0, 0.0)
        logger.warning("Go2WHardware: docking timed out")
        return False

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
