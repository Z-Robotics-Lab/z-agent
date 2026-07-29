# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WCamera — REAL RealSense D435i RGB source for the running-nav-stack Go2W.

The go2w_real world drives navigation through the nav stack (``Go2WHardware``);
this module gives that same body its EYES: the RGB frames the look / describe /
find_object / scene_query path consumes, taken from the D435i camera node the
NUC runs as a systemd unit (``~/go2w-nuc/bringup/systemd/d435i.service`` ->
``ros2 launch realsense2_camera rs_launch.py`` under the ``/nuc`` namespace).
Colour lands on ``/nuc/camera/color/image_raw`` as a ``sensor_msgs/Image``
(rgb8, 640x480), published BEST_EFFORT.

BANDWIDTH — on-demand, not a persistent stream (2026-07-29). Cross-WiFi raw RGB
640x480@15Hz is ~13 MB/s and would starve the nav odometry that shares the same
DDS link, yet perception (find_object / scene_query) is invoked only when the
agent chooses to LOOK — rarely, not continuously. So the camera keeps ZERO
baseline bandwidth: it holds NO standing subscription; each frame request opens a
SHORT-LIVED BEST_EFFORT depth=1 subscription, waits for one decoded frame, and
tears the subscription down. Measured on the 4090 over WiFi: 5/5 fetches
succeeded, 0.54–1.36 s to first frame (median ~0.94 s). This reuses the
dependency-free numpy decode below — no compressed-image / cv2 machinery, no new
pyproject dependency on the camera side. (The RynnBrain client re-encodes the
frame to JPEG with Pillow, which the [real] tier carries.)

Contract parity with the sim frame source (``Go2ROS2Proxy.get_camera_frame`` in
hardware/sim/go2_ros2_proxy.py) so sim and real feed the SAME perception code:

    get_camera_frame(width, height) -> numpy (H, W, 3) uint8 RGB   # the consumer
                                                                   # contract used
                                                                   # by look.py,
                                                                   # capability_profile._runtime_camera,
                                                                   # visual_verifier,
                                                                   # Go2GraspPerception

Plus a small liveness surface the go2w_real tools can consult:

    has_camera()       -> bool     # a real frame is reachable (camera streaming)
    get_camera_image() -> ndarray | None   # the latest RGB frame, or None if none

Design constraints (AGENTS.md):
* NO new pyproject dependency ON THE CAMERA — decode is manual (rgb8 passthrough
  / bgr8 channel swap) straight off ``msg.data``; cv_bridge is NOT imported;
* rclpy + sensor_msgs are LAZY imports (module import needs no sourced ROS env);
* a down / absent camera never raises — ``get_camera_frame`` returns a black
  frame and ``has_camera()`` stays False, exactly like the sim proxy;
* the camera does NOT own a node: its short-lived subscriptions are created and
  destroyed on the driver's existing node (like ``Go2WHardware._on_odom``), so
  they ride the shared ROS2 runtime's single executor with no extra spin thread.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class Go2WCamera:
    """On-demand RealSense D435i RGB source -> numpy RGB, decoded without cv_bridge.

    Construct freely with no ROS env (offline-safe); ``attach(node)`` binds the
    driver's rclpy node so a frame request can open a short-lived subscription on
    it. Until a fetch succeeds ``has_camera()`` is False and ``get_camera_frame``
    yields black.
    """

    # NUC-namespaced realsense2_camera colour stream (d435i.service publishes the
    # camera under the ``/nuc`` namespace, BEST_EFFORT). Overridable per instance
    # via the ctor, or per deployment via ``ZENO_GO2W_COLOR_TOPIC`` (VECTOR_
    # fallback) — a differently-namespaced launch needs no code change.
    COLOR_TOPIC: str = "/nuc/camera/color/image_raw"

    # Seconds to wait for one frame after opening the short-lived subscription.
    # Generous vs the measured worst case (~1.4 s) so a busy WiFi link still lands
    # a frame; a timeout degrades honestly (None / black), never raises.
    FETCH_TIMEOUT_S: float = 5.0

    # A cached frame this fresh is reused instead of opening a new subscription,
    # so back-to-back accessors (has_camera() then get_camera_image()) cost ONE
    # round trip. Shorter than MAX_AGE_S so a served cache is never "stale".
    FRESH_TTL_S: float = 0.3

    # Frames older than this (seconds) are still served but log a staleness
    # warning — mirrors Go2ROS2Proxy.get_camera_frame's 1s guard.
    MAX_AGE_S: float = 1.0

    # Default render size when a caller does not pin one — matches the go2 head
    # camera resolution the perception stack expects (GO2_HEAD_CAM_WIDTH/HEIGHT).
    DEFAULT_WIDTH: int = 320
    DEFAULT_HEIGHT: int = 240

    # Encodings we can decode with plain numpy (no cv_bridge). 3-channel colour
    # only — depth / mono / yuyv are out of scope for the RGB witness path.
    _RGB_ENCODINGS: frozenset[str] = frozenset({"rgb8", "bgr8"})

    def __init__(self, topic: str | None = None) -> None:
        self._topic: str = topic if topic is not None else self._resolve_topic()
        self._node: Any = None
        self._last_frame: Any = None       # numpy (H, W, 3) uint8 RGB
        self._last_ts: float = 0.0         # monotonic time of last decoded frame
        # Serialises on-demand fetches (one short-lived subscription at a time)
        # and hands a decoded frame back from the executor thread to the caller.
        self._fetch_lock = threading.Lock()
        self._frame_event = threading.Event()

    @classmethod
    def _resolve_topic(cls) -> str:
        """Default topic, overridable via ZENO_/VECTOR_ GO2W_COLOR_TOPIC.

        Routed through the single-source env resolver (AGENTS.md), imported
        lazily so the camera module has no import-time coupling to vcli (and no
        cycle through tool discovery); falls back to a bare os read, then to the
        class default, so resolution never raises.
        """
        try:
            from zeno.vcli.env import read_env

            return read_env("GO2W_COLOR_TOPIC", cls.COLOR_TOPIC) or cls.COLOR_TOPIC
        except Exception:  # noqa: BLE001 — env resolution must never block construction
            import os

            return (os.environ.get("ZENO_GO2W_COLOR_TOPIC")
                    or os.environ.get("VECTOR_GO2W_COLOR_TOPIC")
                    or cls.COLOR_TOPIC)

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def attach(self, node: Any) -> None:
        """Bind the driver's rclpy *node* so frame requests can subscribe on it.

        No standing subscription is created (zero baseline bandwidth); the node
        is simply remembered so ``_fetch`` can open a short-lived subscription on
        demand. Safe to call once per node; a None node is ignored.
        """
        if node is None:
            return
        self._node = node
        logger.info("Go2WCamera bound to node for on-demand %s", self._topic)

    def attach_node_for_test(self, node: Any) -> None:
        """Test seam: bind a mock node with no ROS (mirrors ``attach``).

        Same pattern as ``Go2WHardware._install_node_for_test``. Not used in
        production.
        """
        self._node = node

    # ------------------------------------------------------------------
    # On-demand fetch — open a short-lived subscription, await one frame
    # ------------------------------------------------------------------

    def _fetch(self, timeout_s: float | None = None) -> bool:
        """Refresh the cache with a fresh frame; return True iff one was decoded.

        No-op (returns False) with no bound node — offline / pre-connect hosts
        and injection tests keep whatever is cached. A cache younger than
        ``FRESH_TTL_S`` is reused (no round trip). Otherwise opens a BEST_EFFORT
        depth=1 subscription (matching the d435i publisher), waits up to
        ``FETCH_TIMEOUT_S`` for ``_on_image`` to decode one frame, and tears the
        subscription down. Never raises — a timeout / missing ROS degrades to
        False and the caller serves cache-or-black.
        """
        node = self._node
        if node is None:
            return False
        if self._last_ts > 0.0 and (time.monotonic() - self._last_ts) < self.FRESH_TTL_S:
            return True
        timeout = self.FETCH_TIMEOUT_S if timeout_s is None else timeout_s
        with self._fetch_lock:
            # Re-check under the lock: a concurrent fetch may have just landed one.
            if self._last_ts > 0.0 and (time.monotonic() - self._last_ts) < self.FRESH_TTL_S:
                return True
            try:
                from rclpy.qos import QoSProfile, ReliabilityPolicy
                from sensor_msgs.msg import Image
            except ImportError as exc:
                logger.debug("Go2WCamera: ROS2/sensor_msgs unavailable, no frame: %s", exc)
                return False
            prev_ts = self._last_ts
            self._frame_event.clear()
            sub = None
            try:
                qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=1)
                sub = node.create_subscription(Image, self._topic, self._on_image, qos)
            except Exception as exc:  # noqa: BLE001 — subscribe boundary, never fatal
                logger.error("Go2WCamera fetch subscribe failed: %s", exc)
                return False
            try:
                got = self._frame_event.wait(timeout)
            finally:
                try:
                    node.destroy_subscription(sub)
                except Exception:  # noqa: BLE001 — best-effort teardown
                    pass
            if not got:
                logger.warning(
                    "Go2WCamera: no frame on %s within %.1fs (stream not flowing?)",
                    self._topic, timeout,
                )
            return got and self._last_ts > prev_ts

    # ------------------------------------------------------------------
    # Subscription callback — decode wire bytes to numpy RGB
    # ------------------------------------------------------------------

    def _on_image(self, msg: Any) -> None:
        """Decode a sensor_msgs/Image to (H, W, 3) uint8 RGB, cache it, signal.

        Manual decode (no cv_bridge): reshape ``msg.data`` by the row ``step``,
        crop to width*channels (drops alignment padding), and swap B<->R for
        bgr8. A malformed / undecodable message is DROPPED (the last good frame
        stays cached, the event stays clear) — the callback never raises into the
        executor thread. Setting ``_frame_event`` wakes the on-demand ``_fetch``.
        """
        frame = self._decode(msg)
        if frame is None:
            return
        self._last_frame = frame
        self._last_ts = time.monotonic()
        self._frame_event.set()

    def _decode(self, msg: Any) -> Any:
        """Return a decoded (H, W, 3) uint8 RGB array, or None if undecodable."""
        try:
            import numpy as np

            encoding = str(getattr(msg, "encoding", "")).lower()
            if encoding not in self._RGB_ENCODINGS:
                logger.debug("Go2WCamera: unsupported encoding %r, dropping", encoding)
                return None

            height = int(msg.height)
            width = int(msg.width)
            if height <= 0 or width <= 0:
                return None

            row_bytes = width * 3
            step = int(getattr(msg, "step", 0)) or row_bytes
            buf = np.frombuffer(bytes(msg.data), dtype=np.uint8)
            if buf.size < step * height:
                logger.debug(
                    "Go2WCamera: short buffer (%d < %d), dropping frame",
                    buf.size, step * height,
                )
                return None

            # Reshape by the true row stride, then crop off any trailing padding.
            frame = buf[: step * height].reshape(height, step)[:, :row_bytes]
            frame = frame.reshape(height, width, 3)
            if encoding == "bgr8":
                frame = frame[:, :, ::-1]
            # Materialise a contiguous, writable copy (the buffer is read-only).
            return np.ascontiguousarray(frame, dtype=np.uint8)
        except Exception as exc:  # noqa: BLE001 — decode must never raise
            logger.debug("Go2WCamera: decode failed (%s), dropping frame", exc)
            return None

    # ------------------------------------------------------------------
    # Liveness surface
    # ------------------------------------------------------------------

    def has_camera(self) -> bool:
        """True iff a real frame is reachable (camera streaming).

        Probes on demand: opens a short-lived subscription if the cache is not
        already fresh. Returns whether any real frame is now cached.
        """
        self._fetch()
        return self._last_frame is not None

    def get_camera_image(self) -> Any:
        """Return the latest RGB frame as (H, W, 3) uint8, or None if none.

        Fetches a fresh frame on demand. A copy is returned so a caller mutating
        it cannot poison the cache. Logs a staleness warning (still serves the
        frame) if the served cache is older than MAX_AGE_S (e.g. the fetch timed
        out and an earlier frame is being reused).
        """
        self._fetch()
        if self._last_frame is None:
            return None
        self._warn_if_stale()
        return self._last_frame.copy()

    # ------------------------------------------------------------------
    # Consumer contract — get_camera_frame(width, height) (sim proxy parity)
    # ------------------------------------------------------------------

    def get_camera_frame(self, width: int | None = None, height: int | None = None) -> Any:
        """Return the latest RGB frame resized to (height, width, 3) uint8.

        Parity with ``Go2ROS2Proxy.get_camera_frame`` / ``MuJoCoGo2.
        get_camera_frame``: NEVER raises and NEVER returns None — it fetches a
        fresh frame on demand, and with no live frame (camera absent / stream not
        flowing) it returns a black frame of the requested size so the perception
        path degrades gracefully. Resize is a dependency-free nearest-neighbour
        sample (avoids pulling in cv2/PIL).
        """
        import numpy as np

        w = self.DEFAULT_WIDTH if width is None else int(width)
        h = self.DEFAULT_HEIGHT if height is None else int(height)

        self._fetch()
        if self._last_frame is None:
            return np.zeros((h, w, 3), dtype=np.uint8)

        self._warn_if_stale()
        frame = self._last_frame
        if frame.shape[0] == h and frame.shape[1] == w:
            return frame.copy()
        return self._resize_nn(frame, w, h)

    @staticmethod
    def _resize_nn(frame: Any, width: int, height: int) -> Any:
        """Nearest-neighbour resize to (height, width, 3) — no cv2/PIL dependency."""
        import numpy as np

        src_h, src_w = frame.shape[0], frame.shape[1]
        if src_h <= 0 or src_w <= 0:
            return np.zeros((height, width, 3), dtype=np.uint8)
        ys = (np.arange(height) * src_h // max(height, 1)).clip(0, src_h - 1)
        xs = (np.arange(width) * src_w // max(width, 1)).clip(0, src_w - 1)
        return np.ascontiguousarray(frame[ys][:, xs], dtype=np.uint8)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _warn_if_stale(self) -> None:
        if self._last_ts <= 0:
            return
        age = time.monotonic() - self._last_ts
        if age > self.MAX_AGE_S:
            logger.warning("Go2WCamera: RGB frame is %.1fs old (stale)", age)


class CameraMixin:
    """Camera accessors mixed into Go2WHardware (repo rule: files under 400 lines).

    Thin delegators to ``self._camera`` (a ``Go2WCamera`` the host constructs and
    attaches to its node). ``get_camera_frame`` is the duck-typed accessor the
    perception path reaches the camera through — capability_profile._runtime_camera
    / robot._agent_has_camera / look.py / visual_verifier / Go2GraspPerception — so
    its mere PRESENCE as a bound callable is the runtime-authoritative camera gate
    (the same one the sim Go2ROS2Proxy satisfies). ``has_camera`` adds liveness.
    """

    _camera: Go2WCamera  # provided by the host class

    def get_camera_frame(self, width: int | None = None, height: int | None = None) -> Any:
        """Latest D435i RGB frame as (H, W, 3) uint8 (black if not streaming)."""
        return self._camera.get_camera_frame(width, height)

    def get_camera_image(self) -> Any:
        """Latest D435i RGB frame, or None if none has arrived yet (liveness)."""
        return self._camera.get_camera_image()

    def has_camera(self) -> bool:
        """True iff the D435i is streaming (a real frame has been decoded)."""
        return self._camera.has_camera()
