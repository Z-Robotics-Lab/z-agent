# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WRouteManager — far_planner GLOBAL route mode over the running nav stack.

Sibling of :class:`~zeno.hardware.ros2.go2w_hw_explore.Go2WExploreManager`, built
on the SAME shared seam (``OverlayLauncher`` + SIGINT-only teardown + guarded
resume + orphan detection — reused, not reimplemented). Wraps ``nav.sh route`` (a
FOREGROUND overlay that execs ``ros2 launch far_planner far_planner.launch``) and
drives far_planner's goal/arrival contract (all source-verified in far_planner.cpp):

* **Goal** — far_planner subscribes ``geometry_msgs/PointStamped`` on
  ``/goal_point`` (``WaypointCallBack``); ``world_frame`` defaults to ``map`` and
  the callback TF-transforms any other frame, so we publish the goal in ``map``
  directly. far_planner plans a GLOBAL route over its visibility graph and
  republishes the local target to ``/way_point`` ITSELF — so route mode must
  NEVER publish ``/way_point`` (navigate mode owns that; route owns /goal_point).
* **Arrival oracle** — graded on ``/state_estimation`` odometry proximity to the
  goal (Inv-1: the estimated pose the actor cannot forge), like navigate_to.
  far_planner's own ``std_msgs/Bool`` ``/far_reach_goal_status`` (``is_reach_goal``)
  is recorded + used as the launching->active liveness proof, but is NEVER the
  sole arrival authority (a stale True must not fabricate an arrival).

State machine ``idle -> launching -> active -> stopped``: -> active on the first
reach frame or first ``goto_via_route``; -> stopped on request or unexpected
child death (orphan detection + one background ``/nav_cancel`` for the latched
waypoint). Stop = SIGINT our child -> ``/nav_cancel`` -> resume GUARDED by the
estop latch (never silently release an operator's E-stop). No rclpy at import.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Callable

from zeno.hardware.base import ensure_finite_nav_goal
from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher
from zeno.hardware.ros2.go2w_hw_route_ros import (
    RouteConfig,
    RouteStatus,
    attach_route_oracle,
    publish_goal_point,
)

logger = logging.getLogger(__name__)

# RouteConfig / RouteStatus are re-exported (imported above) so callers and tests
# can import them from this module alongside Go2WRouteManager.
_ACTIVE_STATES: frozenset[str] = frozenset({"launching", "active"})


class Go2WRouteManager:
    """Own one far_planner route overlay + its honest goal/arrival oracle.

    ``hw`` is the session's :class:`Go2WHardware` (may be None offline): it
    supplies the ROS node the goal publisher + oracle subscribe on, plus
    ``nav_cancel`` / ``estop_release`` / ``estop_latched`` for the stop
    semantics. All public methods are thread-safe and never raise into callers
    (tool boundary).
    """

    GOAL_TOPIC: str = "/goal_point"            # geometry_msgs/PointStamped
    GOAL_FRAME: str = "map"                    # far_planner world_frame default
    ODOM_TOPIC: str = "/state_estimation"      # nav_msgs/Odometry (map frame)
    REACH_TOPIC: str = "/far_reach_goal_status"  # std_msgs/Bool (far_planner)

    def __init__(
        self,
        hw: Any,
        config: RouteConfig | None = None,
        popen_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._hw = hw
        self._config = config or RouteConfig()
        self._launcher = OverlayLauncher(
            "route", nav_sh=self._config.nav_sh, popen_factory=popen_factory
        )
        self._lock = threading.RLock()
        self._state = "idle"
        self._reason = ""
        self._goal: tuple[float, float] | None = None
        self._reached = False           # goal-relative arrival latch (odometry)
        self._far_reach = False         # far_planner's own last reach view
        self._runtime_s: float | None = None
        self._position: tuple[float, float] = (0.0, 0.0)
        self._have_odom = False
        self._goal_pub: Any = None
        self._oracle_attached = False
        self._orphan_cancel_fired = False
        self._cancel_requested = False  # unblocks a running goto poll loop

    # ------------------------------------------------------------------
    # Oracle predicates + status (the verify surface)
    # ------------------------------------------------------------------

    def state(self) -> str:
        with self._lock:
            self._refresh_locked()
            return self._state

    @property
    def is_active(self) -> bool:
        return self.state() in _ACTIVE_STATES

    def route_reached(self) -> bool:
        """True iff the robot reached the CURRENT goal (odometry-verified).

        Latches on arrival and stays True until a new goal is issued — so a
        verify predicate reading it after the blocking ``goto_via_route`` returns
        still sees the arrival. Fail-safe False when no goal has been sent.
        """
        with self._lock:
            return self._reached

    def status(self) -> RouteStatus:
        with self._lock:
            self._refresh_locked()
            return RouteStatus(
                state=self._state,
                pid=self._launcher.pid,
                reached=self._reached,
                goal=self._goal,
                far_reach=self._far_reach,
                runtime_s=self._runtime_s,
                reason=self._reason,
                oracle_attached=self._oracle_attached,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_route(self) -> tuple[bool, str]:
        """Launch the far_planner overlay (non-blocking; then use goto_via_route).

        Requires a connected driver (one ``connect()`` heal is attempted):
        without its node there is no ``/goal_point`` publisher and the arrival
        oracle would be blind — an unverifiable route must not launch (Inv-1).
        """
        with self._lock:
            self._refresh_locked()
            if self._state in _ACTIVE_STATES:
                return False, (
                    f"route already {self._state} (pid {self._launcher.pid}) — "
                    f"stop_route first"
                )
            if not self._heal_connect():
                return False, (
                    "hardware driver not connected — the route oracle would be "
                    "blind. Run go2w_real_bringup(action='start'), wait for SLAM "
                    "(~40-60s), then retry."
                )
            if not self._attach_oracle_locked():
                return False, (
                    "could not attach the route goal publisher (/goal_point) + "
                    "oracle (/state_estimation, /far_reach_goal_status) to the node"
                )
            # Reset the per-session oracle BEFORE the child exists.
            self._goal = None
            self._reached = False
            self._far_reach = False
            self._runtime_s = None
            self._reason = ""
            self._orphan_cancel_fired = False
            self._cancel_requested = False
            ok, msg = self._launcher.launch()
            if not ok:
                return False, msg
            self._state = "launching"
            self._sync_overlay_flag_locked()
            return True, (
                f"far_planner route launched (pid={self._launcher.pid}); send a "
                f"goal with goto_via_route(x, y) — plans a global route on "
                f"{self.GOAL_TOPIC}, arrival verified from odometry"
            )

    def goto_via_route(
        self, x: float, y: float, timeout: float | None = None
    ) -> bool:
        """Publish ONE ``/goal_point`` (map frame) then poll odometry to arrival.

        Blocking: far_planner plans the global route and republishes ``/way_point``
        itself; we watch ``/state_estimation`` until the robot is within
        ``arrival_tol_m`` (True + latch ``route_reached``), the timeout expires,
        or ``cancel_route`` is called. On timeout/cancel we clear the latch via
        ``/nav_cancel`` so far_planner's republished waypoint does not keep
        driving to an abandoned goal. Returns True only on odometry-verified
        arrival (the real oracle). A non-finite goal is rejected at the boundary.
        """
        try:
            ensure_finite_nav_goal(x, y, "Go2WRouteManager.goto_via_route")
        except Exception as exc:  # noqa: BLE001 — reject bad input, never crash
            logger.warning("Go2WRouteManager.goto_via_route: %s", exc)
            return False
        bound = self._config.goto_timeout_s if timeout is None else float(timeout)
        with self._lock:
            self._refresh_locked()
            if self._state not in _ACTIVE_STATES:
                logger.warning("Go2WRouteManager.goto_via_route: no route overlay "
                               "(state=%s) — start_route first", self._state)
                return False
            if self._goal_pub is None:
                return False
            # New goal: reset the arrival latch + any pending cancel, promote
            # launching -> active (far_planner is up and now pursuing a goal).
            self._goal = (float(x), float(y))
            self._reached = False
            self._cancel_requested = False
            if self._state == "launching":
                self._state = "active"
            self._sync_overlay_flag_locked()
        self._publish_goal(float(x), float(y))
        logger.info("Go2WRouteManager: %s -> (%.2f, %.2f), timeout=%.0fs",
                    self.GOAL_TOPIC, x, y, bound)

        period = 1.0 / max(self._config.poll_hz, 1.0)
        start = time.monotonic()
        while time.monotonic() - start < bound:
            with self._lock:
                if self._cancel_requested:
                    self._reason = "route goal cancelled"
                    return False
                px, py = self._position
                dist = math.hypot(px - x, py - y)
                if dist < self._config.arrival_tol_m:
                    self._reached = True
                    logger.info("Go2WRouteManager: arrived (dist=%.2fm)", dist)
                    return True
            time.sleep(period)

        logger.warning("Go2WRouteManager: goto timeout — cancelling latch")
        self._fire_nav_cancel(sync=True)
        with self._lock:
            self._reason = "route goto timeout"
        return False

    def cancel_route(self) -> tuple[bool, str]:
        """Clear the current goal (``/nav_cancel``) but KEEP the overlay running.

        Unblocks any in-flight ``goto_via_route`` and stops the robot chasing the
        latched waypoint, while leaving far_planner up so a new goal can be sent
        without a relaunch. Does NOT touch the estop/manual latches.
        """
        with self._lock:
            self._refresh_locked()
            self._cancel_requested = True
            self._reached = False
        cancelled = self._fire_nav_cancel(sync=True)
        return True, f"route goal cancelled; /nav_cancel {'ok' if cancelled else 'FAILED'}"

    def stop_route(self, resume: bool = False) -> tuple[bool, str]:
        """SIGINT our overlay -> wait -> ``/nav_cancel`` -> GUARDED optional resume.

        ``resume=True`` releases the estop/manual latches afterwards ONLY when the
        driver has not latched an E-stop itself — an operator's E-stop is never
        released as a side effect of stopping routing.
        """
        with self._lock:
            self._refresh_locked()
            active = self._state in _ACTIVE_STATES
            need_orphan_cancel = self._orphan_cancel_needed_locked()
            self._cancel_requested = True
        if not active:
            if need_orphan_cancel:
                self._fire_nav_cancel(sync=True)
            return True, f"no route session running (state={self.state()})"

        clean, rc = self._launcher.stop(self._config.stop_grace_s)
        with self._lock:
            if clean:
                self._state = "stopped"
                self._sync_overlay_flag_locked()
                self._reason = f"stopped by request (rc={rc})"
                msg = f"route stopped (child exited rc={rc})"
            else:
                pid = self._launcher.pid
                self._reason = (
                    f"SIGINT timeout — overlay (pid {pid}) still running; "
                    f"retry stop_route"
                )
                msg = self._reason
        cancelled = self._fire_nav_cancel(sync=True)
        msg += f"; /nav_cancel {'ok' if cancelled else 'FAILED'}"
        if resume and clean:
            msg += "; " + self._guarded_resume()
        return clean, msg

    # ------------------------------------------------------------------
    # ROS callbacks (executor thread — keep them tiny, never raise)
    # ------------------------------------------------------------------

    def _on_reach(self, msg: Any) -> None:
        with self._lock:
            self._refresh_locked()
            if self._state not in _ACTIVE_STATES:
                return  # stale frame from a dead/previous session
            self._far_reach = bool(msg.data)
            if self._state == "launching":
                self._state = "active"  # liveness proof: far_planner is planning
                self._sync_overlay_flag_locked()

    def _on_odom(self, msg: Any) -> None:
        with self._lock:
            p = msg.pose.pose.position
            px, py = float(p.x), float(p.y)
            if math.isfinite(px) and math.isfinite(py):
                self._position = (px, py)
                self._have_odom = True

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _publish_goal(self, x: float, y: float) -> None:
        """Publish one PointStamped to /goal_point in the map frame."""
        node = getattr(self._hw, "_node", None)
        publish_goal_point(node, self._goal_pub, self.GOAL_FRAME, x, y)

    def _sync_overlay_flag_locked(self) -> None:
        """Mirror the active state onto the driver's ``route_overlay_active``.

        far_planner republishes ``/way_point`` continuously toward its route
        while the overlay is up; the driver reads this flag to classify those
        frames as PLUMBING (not an operator RViz click). Best-effort: an older
        driver without the attribute is simply set once, harmlessly.
        """
        hw = self._hw
        if hw is None:
            return
        try:
            hw.route_overlay_active = self._state in _ACTIVE_STATES
        except Exception:  # noqa: BLE001 — flag sync must never raise
            pass

    def _refresh_locked(self) -> None:
        """Orphan detection: an active state with a dead child => stopped."""
        if self._state not in _ACTIVE_STATES or self._launcher.is_running():
            self._sync_overlay_flag_locked()
            return
        rc = self._launcher.returncode()
        self._state = "stopped"
        self._cancel_requested = True  # unblock any in-flight goto
        if self._launcher.stop_requested:
            self._reason = f"stopped by request (rc={rc})"
        else:
            self._reason = f"overlay exited unexpectedly (rc={rc})"
            logger.warning("Go2WRouteManager: %s", self._reason)
            # A dead far_planner leaves its last republished /way_point latched —
            # the robot would keep chasing it. Fire one background cancel (this
            # may run on the rclpy executor thread, where a synchronous service
            # call cannot complete — hence the daemon thread).
            if not self._orphan_cancel_fired:
                self._orphan_cancel_fired = True
                self._fire_nav_cancel(sync=False)
        # Just left an active state (orphan death) — the overlay is no longer
        # republishing /way_point, so operator clicks are external again.
        self._sync_overlay_flag_locked()

    def _orphan_cancel_needed_locked(self) -> bool:
        """True when an orphan death was seen but the async cancel may need a
        synchronous retry (stop_route gives it a reliable second shot)."""
        return self._state == "stopped" and "unexpectedly" in self._reason

    def _fire_nav_cancel(self, sync: bool) -> bool:
        hw = self._hw
        cancel = getattr(hw, "nav_cancel", None) if hw is not None else None
        if not callable(cancel):
            return False
        if sync:
            try:
                return bool(cancel())
            except Exception:  # noqa: BLE001 — service boundary
                return False
        threading.Thread(target=self._fire_nav_cancel, args=(True,),
                         daemon=True, name="go2w-route-navcancel").start()
        return True

    def _guarded_resume(self) -> str:
        hw = self._hw
        if bool(getattr(hw, "estop_latched", False)):
            return (
                "E-STOP latched — NOT auto-resuming (release explicitly with "
                "go2w_real_resume)"
            )
        release = getattr(hw, "estop_release", None) if hw is not None else None
        if not callable(release):
            return "resume unavailable (no driver)"
        try:
            ok = bool(release())
        except Exception:  # noqa: BLE001 — service boundary
            ok = False
        return "autonomy resumed" if ok else "resume FAILED (estop_release)"

    def _heal_connect(self) -> bool:
        hw = self._hw
        if hw is None:
            return False
        if not bool(getattr(hw, "is_connected", False)):
            try:
                hw.connect()
            except Exception:  # noqa: BLE001 — connect is best-effort
                pass
        return bool(getattr(hw, "is_connected", False))

    def _attach_oracle_locked(self) -> bool:
        """Create the /goal_point publisher + subscribe odom/reach (idempotent)."""
        if self._oracle_attached:
            return True
        node = getattr(self._hw, "_node", None)
        goal_pub = attach_route_oracle(
            node, self.GOAL_TOPIC, self.ODOM_TOPIC, self.REACH_TOPIC,
            self._on_odom, self._on_reach,
        )
        if goal_pub is None:
            return False
        self._goal_pub = goal_pub
        self._oracle_attached = True
        return True
