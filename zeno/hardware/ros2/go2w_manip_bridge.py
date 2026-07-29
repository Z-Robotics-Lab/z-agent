# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WManipBridge — a THIN ROS client for the Z-Mobile-manip task FSM.

The mobile-manipulation stack (repo ``Z-Mobile-manip``, recon 2026-07-29 @ HEAD
51d5f1a) runs its own ROS2 graph on the 4090 (DDS domain 20). Its operator
contract is three ``std_msgs`` topics — this bridge speaks EXACTLY those and
NOTHING else. It is a relay, not a brain: the approach-only cancel policy and
every skill decision live in ``go2w_real_manip_skills.py``; here we only publish
requests / cancels and parse the status document into read-only facts.

Contract (all verified against the FSM source in the recon):
  * publish ``/z_manip/task/request``  — std_msgs/String, RAW natural language
    (``core.begin`` uses the whole string as the instruction; there are NO
    params/flags/modes — find→approach→grasp→place is driven by the FSM).
  * publish ``/z_manip/task/cancel``   — std_msgs/Bool ``true`` = a CLEAN stop
    at ANY phase (zeros the base, cancels nav + arm, phase→CANCELED; idempotent).
  * subscribe ``/z_manip/task/status`` — std_msgs/String, ``z_manip.task_status.v1``
    JSON, LATCHED (transient-local). Carries phase, coarse_nav_ready,
    desired_camera_depth_m, result, failure and the measured base speeds.
  * subscribe ``/z_manip/navigation/coarse_ready`` — std_msgs/Bool, latched: the
    nav→servo (≈1.4 m) handoff signal, redundant with the status doc's
    ``coarse_nav_ready`` field (kept as a second, direct read).

APPROACH-COMPLETE oracle (Inv-1): there is NO single ``handoff_ready`` boolean in
the status doc for the servo→grasp point. The FSM leaves ``visual_servo`` only
AFTER the base is stopped at the standoff, entering ``final_grounding`` /
``wait_fresh_observation`` / ``planning`` (perception/compute only — no base, no
arm; the FIRST arm phase is ``transit``). The bridge LATCHES ``approach_reached``
the instant it observes one of those handoff phases in the FSM's OWN status
stream — a truth the actor cannot author (mirrors ``route_reached()``). The latch
survives until the next ``send_task`` so a verify predicate reading it after the
blocking skill returns (by then phase may be CANCELED) still sees the arrival —
the same driver-anchored-latch shape as ``moved()``/``turned()``/``route_reached()``.

RED LINE: this module NEVER touches can0, the arm, ``/piper/*``, or any executor.
It only pub/subs three std_msgs topics. It shares the process-singleton executor
via :func:`~zeno.hardware.ros2.runtime.get_ros2_runtime` and NEVER spins its own
thread. No ``rclpy`` import at module load — safe to import with no ROS env (the
skill/verify/vocab/test paths import it offline).
"""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
import time
from typing import Any

from zeno.hardware.ros2.runtime import get_ros2_runtime

logger = logging.getLogger(__name__)

# --- The Z-Mobile-manip operator topic contract (recon 2026-07-29) -----------
REQUEST_TOPIC: str = "/z_manip/task/request"              # std_msgs/String (raw NL)
CANCEL_TOPIC: str = "/z_manip/task/cancel"                # std_msgs/Bool  (true = stop)
STATUS_TOPIC: str = "/z_manip/task/status"                # std_msgs/String (latched JSON)
COARSE_READY_TOPIC: str = "/z_manip/navigation/coarse_ready"  # std_msgs/Bool (latched)

#: The status document schema string (``schema`` field of task_status.v1).
STATUS_SCHEMA: str = "z_manip.task_status.v1"

# --- RuntimePhase groupings (core.py:69-101 enum; recon Q6) -------------------
#: Approach COMPLETE / servo→grasp handoff: base stopped at the standoff (~0.55 m),
#: perception/compute only — NO base motion, NO arm yet. Cancelling here keeps the
#: run provably arm-free (``transit`` is the first arm phase, and it comes after).
HANDOFF_PHASES: frozenset[str] = frozenset(
    {"final_grounding", "wait_fresh_observation", "planning"}
)
#: The FIRST arm phase is ``transit``; every phase at/after it moves the arm. The
#: skill cancels at HANDOFF, so seeing one of these is a safety breach → hard abort.
ARM_PHASES: frozenset[str] = frozenset(
    {
        "transit", "pregrasp_reobserve", "approach_planning", "approach",
        "closing", "lift", "verify", "carry", "pick_complete",
        "place_grounding", "place_planning", "place_transit", "place_approach",
        "releasing", "place_retreat", "post_release_verification", "complete",
    }
)
#: Terminal failure phase (fail-closed with a named reason in status.failure).
TERMINAL_FAIL_PHASES: frozenset[str] = frozenset({"failed"})
#: Terminal cancel phase (idempotent, set by /z_manip/task/cancel).
CANCELED_PHASE: str = "canceled"


@dataclasses.dataclass(frozen=True)
class ManipStatus:
    """One immutable snapshot of the manip FSM status (the tool/status surface)."""

    connected: bool
    phase: str | None
    coarse_ready: bool
    desired_camera_depth_m: float | None
    measured_base_linear_speed_mps: float | None
    measured_base_angular_speed_rps: float | None
    result: str
    failure: str
    approach_reached: bool
    status_age_s: float | None
    schema: str | None
    raw: dict


def _num(value: Any) -> float | None:
    """Coerce a JSON number to float, else None (never raise)."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _dig_speed(doc: dict, key: str) -> float | None:
    """Read a measured-speed field: top level, else nested under ``visual_search``.

    The recon located ``measured_base_linear_speed_mps`` /
    ``measured_base_angular_speed_rps`` under the status doc's ``visual_search``
    block (node.py:8185-8186); tolerate a future flattening by checking the top
    level first. Best-effort — a missing/misshaped field yields None.
    """
    if key in doc:
        return _num(doc.get(key))
    nested = doc.get("visual_search")
    if isinstance(nested, dict) and key in nested:
        return _num(nested.get(key))
    return None


class Go2WManipBridge:
    """Own one node's worth of pub/sub onto the Z-Manip task topics (thread-safe).

    Constructed OFFLINE (no ROS touched); :meth:`connect` wires the node onto the
    shared runtime lazily and best-effort. Every public method is fail-honest — an
    unavailable ROS env / down graph leaves ``is_connected`` False and the
    publishers no-ops, never a raise into the caller (tool boundary).
    """

    _NODE_NAME: str = "zeno_go2w_manip_bridge"

    def __init__(self, node_name: str | None = None) -> None:
        self._node_name = node_name or self._NODE_NAME
        self._lock = threading.RLock()
        self._node: Any = None
        self._connected = False
        self._shared_runtime_used = False
        self._req_pub: Any = None
        self._cancel_pub: Any = None
        # Latest parsed status doc + its arrival time (monotonic).
        self._status: dict = {}
        self._status_mono: float | None = None
        # Latched /z_manip/navigation/coarse_ready Bool (redundant with the doc).
        self._coarse_ready_topic = False
        # Approach-reached latch (Inv-1): set from the FSM status stream, reset by
        # send_task. The actor can trigger a task but cannot author this fact.
        self._approach_reached = False
        self._last_instruction = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        """Wire the node + pub/sub onto the shared ROS2 runtime (best-effort).

        Idempotent. A missing rclpy / ROS env leaves the bridge disconnected (a
        debug line, not an error — a graph-absent host must not bleed ERROR into
        the REPL), exactly like ``Go2WHardware.connect``.
        """
        with self._lock:
            if self._connected and self._node is not None:
                return
            try:
                import rclpy
                from rclpy.node import Node
                from rclpy.qos import (
                    DurabilityPolicy,
                    QoSProfile,
                    ReliabilityPolicy,
                )
                from std_msgs.msg import Bool, String

                if not rclpy.ok():
                    rclpy.init()
                node = Node(self._node_name)

                # Requests/cancels: reliable, volatile (the FSM subscribes RELIABLE).
                cmd_qos = QoSProfile(
                    reliability=ReliabilityPolicy.RELIABLE, depth=10
                )
                # Status/coarse_ready are LATCHED (transient-local) — match the
                # durability so a late-joining subscriber still gets the last doc.
                latched = QoSProfile(
                    reliability=ReliabilityPolicy.RELIABLE,
                    durability=DurabilityPolicy.TRANSIENT_LOCAL,
                    depth=1,
                )
                self._req_pub = node.create_publisher(String, REQUEST_TOPIC, cmd_qos)
                self._cancel_pub = node.create_publisher(Bool, CANCEL_TOPIC, cmd_qos)
                node.create_subscription(
                    String, STATUS_TOPIC, self._on_status, latched
                )
                node.create_subscription(
                    Bool, COARSE_READY_TOPIC, self._on_coarse_ready, latched
                )

                self._node = node
                get_ros2_runtime().add_node(node)
                self._shared_runtime_used = True
                self._connected = True
                logger.info("Go2WManipBridge connected (domain from sourced ROS env)")
            except ImportError as exc:
                logger.debug("Go2WManipBridge: ROS2 unavailable, offline: %s", exc)
                self._connected = False
            except Exception as exc:  # noqa: BLE001 — connection boundary, fail honest
                logger.error("Go2WManipBridge connect failed: %s", exc)
                self._connected = False

    def disconnect(self) -> None:
        """Detach from the shared runtime and destroy the node (idempotent)."""
        with self._lock:
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
            self._req_pub = None
            self._cancel_pub = None
            self._connected = False

    def _install_pubs_for_test(self, req_pub: Any, cancel_pub: Any) -> None:
        """Test seam: attach recording publishers without a real ROS node."""
        self._req_pub = req_pub
        self._cancel_pub = cancel_pub
        self._connected = True

    # ------------------------------------------------------------------
    # Publish (command surface)
    # ------------------------------------------------------------------

    def send_task(self, instruction: str) -> bool:
        """Publish ONE raw-NL task request; reset the per-task oracle first.

        Resets ``approach_reached`` and the cached status BEFORE publishing so a
        stale latch from a previous task can never fake-pass the new one. Returns
        False (never raises) when disconnected or the publish fails.
        """
        text = str(instruction or "").strip()
        if not text:
            return False
        with self._lock:
            self._approach_reached = False
            self._status = {}
            self._status_mono = None
            self._last_instruction = text
            pub = self._req_pub
        if pub is None:
            return False
        try:
            from std_msgs.msg import String

            msg = String()
            msg.data = text
            pub.publish(msg)
            logger.info("Go2WManipBridge: task/request -> %r", text)
            return True
        except Exception as exc:  # noqa: BLE001 — publish boundary, never crash
            logger.warning("Go2WManipBridge task/request publish failed: %s", exc)
            return False

    def cancel_task(self) -> bool:
        """Publish ``/z_manip/task/cancel`` true — a clean stop at ANY phase.

        The FSM's cancel zeros the base, cancels nav + arm and latches CANCELED
        (idempotent, safe to fire repeatedly). Returns False when disconnected or
        the publish fails; never raises.
        """
        with self._lock:
            pub = self._cancel_pub
        if pub is None:
            return False
        try:
            from std_msgs.msg import Bool

            msg = Bool()
            msg.data = True
            pub.publish(msg)
            logger.info("Go2WManipBridge: task/cancel -> true")
            return True
        except Exception as exc:  # noqa: BLE001 — publish boundary, never crash
            logger.warning("Go2WManipBridge task/cancel publish failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # ROS callbacks (executor thread — keep tiny, never raise)
    # ------------------------------------------------------------------

    def _on_status(self, msg: Any) -> None:
        try:
            doc = json.loads(getattr(msg, "data", "") or "{}")
        except (ValueError, TypeError):
            return
        if not isinstance(doc, dict):
            return
        with self._lock:
            self._status = doc
            self._status_mono = time.monotonic()
            phase = doc.get("phase")
            # Latch approach-complete the instant the FSM's OWN stream reports a
            # handoff phase (post-servo, pre-arm). Never un-latches within a task.
            if isinstance(phase, str) and phase in HANDOFF_PHASES:
                self._approach_reached = True

    def _on_coarse_ready(self, msg: Any) -> None:
        with self._lock:
            self._coarse_ready_topic = bool(getattr(msg, "data", False))

    # ------------------------------------------------------------------
    # Read-only accessors (the verify / status surface — no business logic)
    # ------------------------------------------------------------------

    @property
    def phase(self) -> str | None:
        with self._lock:
            phase = self._status.get("phase")
            return phase if isinstance(phase, str) else None

    @property
    def coarse_ready(self) -> bool:
        """The nav→servo handoff fact: status ``coarse_nav_ready`` OR the topic latch."""
        with self._lock:
            return bool(self._status.get("coarse_nav_ready")) or self._coarse_ready_topic

    @property
    def desired_camera_depth_m(self) -> float | None:
        with self._lock:
            return _num(self._status.get("desired_camera_depth_m"))

    @property
    def measured_base_linear_speed_mps(self) -> float | None:
        with self._lock:
            return _dig_speed(self._status, "measured_base_linear_speed_mps")

    @property
    def measured_base_angular_speed_rps(self) -> float | None:
        with self._lock:
            return _dig_speed(self._status, "measured_base_angular_speed_rps")

    @property
    def result(self) -> str:
        with self._lock:
            return str(self._status.get("result", "") or "")

    @property
    def failure(self) -> str:
        with self._lock:
            return str(self._status.get("failure", "") or "")

    @property
    def schema(self) -> str | None:
        with self._lock:
            schema = self._status.get("schema")
            return schema if isinstance(schema, str) else None

    def status_age_s(self) -> float | None:
        """Seconds since the last status doc arrived (None if none ever did)."""
        with self._lock:
            if self._status_mono is None:
                return None
            return max(0.0, time.monotonic() - self._status_mono)

    def approach_reached(self) -> bool:
        """The Inv-1 approach-complete latch (set from the FSM status stream)."""
        with self._lock:
            return self._approach_reached

    def status_snapshot(self) -> ManipStatus:
        """One immutable snapshot for the status skill (never raises)."""
        with self._lock:
            phase = self._status.get("phase")
            schema = self._status.get("schema")
            age = (None if self._status_mono is None
                   else max(0.0, time.monotonic() - self._status_mono))
            return ManipStatus(
                connected=self._connected,
                phase=phase if isinstance(phase, str) else None,
                coarse_ready=(bool(self._status.get("coarse_nav_ready"))
                              or self._coarse_ready_topic),
                desired_camera_depth_m=_num(self._status.get("desired_camera_depth_m")),
                measured_base_linear_speed_mps=_dig_speed(
                    self._status, "measured_base_linear_speed_mps"),
                measured_base_angular_speed_rps=_dig_speed(
                    self._status, "measured_base_angular_speed_rps"),
                result=str(self._status.get("result", "") or ""),
                failure=str(self._status.get("failure", "") or ""),
                approach_reached=self._approach_reached,
                status_age_s=age,
                schema=schema if isinstance(schema, str) else None,
                raw=dict(self._status),
            )
