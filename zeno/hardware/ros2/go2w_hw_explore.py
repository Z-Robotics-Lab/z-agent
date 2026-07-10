# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WExploreManager — TARE autonomous exploration over the running nav stack.

Wraps ``bash ~/go2w-nuc/scripts/nav.sh explore [scenario]`` (a FOREGROUND
overlay that execs ``ros2 launch tare_planner explore.launch``) in an
:class:`~zeno.hardware.ros2.go2w_hw_overlay.OverlayLauncher`, and layers the
HONEST exploration oracle on top (Inv-1: no ``/gt`` on hardware):

* **TARE's own finish signal** — the tare_planner node publishes
  ``std_msgs/Bool`` on ``/exploration_finish`` every planning cycle
  (source: sensor_coverage_planner_ground.cpp, ``exploration_finish_pub_``;
  param ``pub_exploration_finish_topic_`` defaults to the relative name
  ``exploration_finish`` and the node is launched with NO namespace and NO
  remaps, so it resolves to ``/exploration_finish``). ``data`` stays False
  while exploring and latches True once coverage completes — the actor
  cannot author it. ``std_msgs/Float32 /runtime`` carries TARE's total
  planning runtime in seconds.
* **An INDEPENDENT progress metric** — travel distance integrated from
  ``/state_estimation`` odometry (:class:`TravelTracker`), so verify can
  distinguish "finished because the map is explored" from "finished but the
  robot never left the spawn".

State machine: ``idle -> launching -> exploring -> finishing -> stopped``.
``launching -> exploring`` on the first finish=False frame (liveness proof);
``-> finishing`` when TARE latches finish=True; ``-> stopped`` on request or
when the child dies unexpectedly (orphan detection, with the exit code in
``reason``; a one-shot background ``/nav_cancel`` clears the waypoint a dead
TARE left latched). Stop semantics: SIGINT our child -> wait -> ``/nav_cancel``
-> optional resume that is GUARDED by the driver's estop latch (stopping TARE
must never silently release an operator's E-stop).

No rclpy at module import; ROS message types import lazily at attach time.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
from typing import Any, Callable

from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher, TravelTracker

logger = logging.getLogger(__name__)

# The nav.sh scenario names — each maps to a TARE config yaml
# (Z-Navigation-Stack/src/exploration_planner/tare_planner/config/<name>.yaml).
_SCENARIOS: tuple[str, ...] = ("indoor_small", "indoor_large", "outdoor")

_ACTIVE_STATES: frozenset[str] = frozenset({"launching", "exploring", "finishing"})


@dataclasses.dataclass(frozen=True)
class ExploreConfig:
    """Immutable knobs for the explore session (additive-only, Inv-7)."""

    nav_sh: str = "~/go2w-nuc/scripts/nav.sh"
    default_scenario: str = "indoor_small"   # nav.sh's own default
    scenarios: tuple[str, ...] = _SCENARIOS
    stop_grace_s: float = 10.0               # per-SIGINT wait for ros2 launch
    min_step_m: float = 0.02                 # travel-oracle odom noise floor
    max_step_m: float = 5.0                  # travel-oracle SLAM-jump filter


@dataclasses.dataclass(frozen=True)
class ExploreStatus:
    """One immutable snapshot of the explore session (tool/status surface)."""

    state: str
    scenario: str
    pid: int | None
    finished: bool
    travel_m: float
    runtime_s: float | None
    reason: str
    oracle_attached: bool


class Go2WExploreManager:
    """Own one TARE explore overlay + its honest finish/progress oracle.

    ``hw`` is the session's :class:`Go2WHardware` (may be None offline): it
    supplies the ROS node the oracle subscribes on, plus ``nav_cancel`` /
    ``estop_release`` / ``estop_latched`` for the stop semantics. All public
    methods are thread-safe and never raise into callers (tool boundary).
    """

    FINISH_TOPIC: str = "/exploration_finish"   # std_msgs/Bool, TARE's own
    RUNTIME_TOPIC: str = "/runtime"             # std_msgs/Float32, seconds
    ODOM_TOPIC: str = "/state_estimation"       # nav_msgs/Odometry (map frame)

    def __init__(
        self,
        hw: Any,
        config: ExploreConfig | None = None,
        popen_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._hw = hw
        self._config = config or ExploreConfig()
        self._launcher = OverlayLauncher(
            "explore", nav_sh=self._config.nav_sh, popen_factory=popen_factory
        )
        self._lock = threading.RLock()
        self._state = "idle"
        self._scenario = ""
        self._reason = ""
        self._finished = False
        self._runtime_s: float | None = None
        self._travel = TravelTracker(
            min_step_m=self._config.min_step_m, max_step_m=self._config.max_step_m
        )
        self._oracle_attached = False
        self._orphan_cancel_fired = False

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

    def explore_finished(self) -> bool:
        """True iff TARE itself published exploration_finish=True this session."""
        with self._lock:
            self._refresh_locked()
            return self._finished

    def explored_progress(self) -> float:
        """Meters actually travelled during this explore session (monotone)."""
        with self._lock:
            return float(self._travel.meters)

    def status(self) -> ExploreStatus:
        with self._lock:
            self._refresh_locked()
            return ExploreStatus(
                state=self._state,
                scenario=self._scenario,
                pid=self._launcher.pid,
                finished=self._finished,
                travel_m=round(self._travel.meters, 3),
                runtime_s=self._runtime_s,
                reason=self._reason,
                oracle_attached=self._oracle_attached,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_explore(self, scenario: str | None = None) -> tuple[bool, str]:
        """Launch the TARE overlay (non-blocking; poll status / predicates).

        Requires a connected driver (one ``connect()`` heal is attempted):
        without its node the finish/progress oracle would be blind, and a
        blind exploration cannot be verified (Inv-1) — so it must not launch.
        """
        scen = str(scenario) if scenario else self._config.default_scenario
        if scen not in self._config.scenarios:
            return False, (
                f"unknown scenario {scen!r}; valid: {sorted(self._config.scenarios)}"
            )
        with self._lock:
            self._refresh_locked()
            if self._state in _ACTIVE_STATES:
                return False, (
                    f"explore already {self._state} (pid {self._launcher.pid}) — "
                    f"stop_explore first"
                )
            if not self._heal_connect():
                return False, (
                    "hardware driver not connected — the explore oracle would be "
                    "blind. Run go2w_real_bringup(action='start'), wait for SLAM "
                    "(~40-60s), then retry."
                )
            if not self._attach_oracle_locked():
                return False, (
                    "could not attach the explore oracle "
                    "(/exploration_finish + /state_estimation) to the ROS node"
                )
            # Reset the per-session oracle BEFORE the child exists so no frame
            # from the new TARE is ever dropped or double-counted.
            self._finished = False
            self._runtime_s = None
            self._travel.reset()
            self._reason = ""
            self._scenario = scen
            self._orphan_cancel_fired = False
            ok, msg = self._launcher.launch(scen)
            if not ok:
                return False, msg
            self._state = "launching"
            return True, (
                f"TARE exploration launched (scenario={scen}, "
                f"pid={self._launcher.pid}); poll status — finish oracle on "
                f"{self.FINISH_TOPIC}, progress from odometry travel"
            )

    def stop_explore(self, resume: bool = False) -> tuple[bool, str]:
        """SIGINT our overlay -> wait -> /nav_cancel -> GUARDED optional resume.

        ``resume=True`` releases the estop/manual latches afterwards ONLY when
        the driver has not latched an E-stop itself — an operator's E-stop is
        never released as a side effect of stopping TARE.
        """
        with self._lock:
            self._refresh_locked()
            active = self._state in _ACTIVE_STATES
            need_orphan_cancel = self._orphan_cancel_needed_locked()
        if not active:
            if need_orphan_cancel:
                self._fire_nav_cancel(sync=True)
            return True, f"no explore session running (state={self.state()})"

        clean, rc = self._launcher.stop(self._config.stop_grace_s)
        with self._lock:
            if clean:
                self._state = "stopped"
                self._reason = f"stopped by request (rc={rc})"
                msg = f"explore stopped (child exited rc={rc})"
            else:
                # Honest: the child is still alive — do not claim 'stopped'.
                pid = self._launcher.pid
                self._reason = (
                    f"SIGINT timeout — overlay (pid {pid}) still running; "
                    f"retry stop_explore"
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

    def _on_finish(self, msg: Any) -> None:
        with self._lock:
            self._refresh_locked()
            if self._state not in _ACTIVE_STATES:
                return  # stale frame from a dead/previous session
            if bool(msg.data):
                self._finished = True          # latches; False never un-finishes
                self._state = "finishing"
            elif self._state == "launching":
                self._state = "exploring"      # liveness proof: TARE is planning

    def _on_runtime(self, msg: Any) -> None:
        with self._lock:
            if self._state in _ACTIVE_STATES:
                self._runtime_s = float(msg.data)

    def _on_odom(self, msg: Any) -> None:
        with self._lock:
            self._refresh_locked()
            if self._state in _ACTIVE_STATES:
                p = msg.pose.pose.position
                self._travel.sample(float(p.x), float(p.y))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _refresh_locked(self) -> None:
        """Orphan detection: an active state with a dead child => stopped."""
        if self._state not in _ACTIVE_STATES or self._launcher.is_running():
            return
        rc = self._launcher.returncode()
        self._state = "stopped"
        if self._launcher.stop_requested:
            self._reason = f"stopped by request (rc={rc})"
        else:
            self._reason = f"overlay exited unexpectedly (rc={rc})"
            logger.warning("Go2WExploreManager: %s", self._reason)
            # A dead TARE leaves its last /way_point latched — the robot would
            # keep chasing it. Fire one background cancel (this may run on the
            # rclpy executor thread, where a synchronous service call cannot
            # complete — hence the daemon thread).
            if not self._orphan_cancel_fired:
                self._orphan_cancel_fired = True
                self._fire_nav_cancel(sync=False)

    def _orphan_cancel_needed_locked(self) -> bool:
        """True when an orphan death was seen but the async cancel may need a
        synchronous retry (stop_explore gives it a reliable second shot)."""
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
                         daemon=True, name="go2w-explore-navcancel").start()
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
        """Subscribe finish/runtime/odometry on the driver's node (idempotent)."""
        if self._oracle_attached:
            return True
        node = getattr(self._hw, "_node", None)
        if node is None:
            return False
        try:
            from nav_msgs.msg import Odometry
            from rclpy.qos import QoSProfile, ReliabilityPolicy
            from std_msgs.msg import Bool, Float32

            node.create_subscription(Bool, self.FINISH_TOPIC, self._on_finish, 10)
            node.create_subscription(
                Float32, self.RUNTIME_TOPIC, self._on_runtime, 10
            )
            sensor = QoSProfile(
                reliability=ReliabilityPolicy.BEST_EFFORT, depth=10
            )
            node.create_subscription(
                Odometry, self.ODOM_TOPIC, self._on_odom, sensor
            )
            self._oracle_attached = True
            return True
        except Exception as exc:  # noqa: BLE001 — attach boundary, fail loud
            logger.warning("Go2WExploreManager: oracle attach failed: %s", exc)
            return False
