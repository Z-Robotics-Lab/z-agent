# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WCamera — REAL RealSense D435i RGB source for the running-nav-stack Go2W.

The go2w_real world drives navigation through the nav stack (``Go2WHardware``);
this module gives that same body its EYES: the RGB frames the look / describe /
detect path consumes, taken from the D435i camera node the NUC runs as a systemd
unit (``~/go2w-nuc/bringup/systemd/d435i.service`` -> ``ros2 launch
realsense2_camera rs_launch.py``). With realsense2_camera's default
``camera_name=camera`` / ``camera_namespace=camera``, colour lands on
``/camera/camera/color/image_raw`` as a ``sensor_msgs/Image`` (RGB8).

Contract parity with the sim frame source (``Go2ROS2Proxy.get_camera_frame`` in
hardware/sim/go2_ros2_proxy.py, lines 303-317) so sim and real feed the SAME
perception code:

    get_camera_frame(width, height) -> numpy (H, W, 3) uint8 RGB   # the consumer
                                                                   # contract used
                                                                   # by look.py,
                                                                   # capability_profile._runtime_camera,
                                                                   # visual_verifier,
                                                                   # Go2GraspPerception

Plus a small liveness surface the go2w_real tools can consult:

    has_camera()       -> bool     # a real frame has arrived (camera streaming)
    get_camera_image() -> ndarray | None   # the latest RGB frame, or None if none yet

Design constraints (AGENTS.md):
* NO new pyproject dependency — decode is manual (rgb8 passthrough / bgr8 channel
  swap) straight off ``msg.data``; cv_bridge is NOT imported;
* rclpy + sensor_msgs are LAZY imports (module import needs no sourced ROS env);
* a down / absent camera never raises — ``get_camera_frame`` returns a black
  frame and ``has_camera()`` stays False, exactly like the sim proxy;
* the camera does NOT own a node: it ATTACHES its Image subscription onto the
  driver's existing node (like ``Go2WHardware._on_odom``), so it joins the shared
  ROS2 runtime's single executor with no extra spin thread.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class Go2WCamera:
    """Lazy RealSense D435i RGB subscriber -> numpy RGB, decoded without cv_bridge.

    Construct freely with no ROS env (offline-safe); ``attach(node)`` wires the
    Image subscription onto an already-created rclpy node. Until a frame arrives
    ``has_camera()`` is False and ``get_camera_frame`` yields black.
    """

    # realsense2_camera default-namespace colour stream (d435i.service defaults:
    # camera_name=camera, camera_namespace=camera). Overridable via the ctor for
    # a differently-namespaced launch.
    COLOR_TOPIC: str = "/camera/camera/color/image_raw"

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
        self._topic: str = topic if topic is not None else self.COLOR_TOPIC
        self._node: Any = None
        self._last_frame: Any = None       # numpy (H, W, 3) uint8 RGB
        self._last_ts: float = 0.0         # monotonic time of last decoded frame

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------

    def attach(self, node: Any) -> None:
        """Subscribe to the colour Image topic on *node* (BEST_EFFORT sensor QoS).

        Best-effort: a missing rclpy / sensor_msgs leaves the camera unattached
        (a debug line, not an error — a D435i-less host must stay quiet), exactly
        like Go2WHardware.connect degrades. Safe to call once per node.
        """
        if node is None:
            return
        try:
            from rclpy.qos import QoSProfile, ReliabilityPolicy
            from sensor_msgs.msg import Image

            qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, depth=1)
            node.create_subscription(Image, self._topic, self._on_image, qos)
            self._node = node
            logger.info("Go2WCamera subscribed to %s", self._topic)
        except ImportError as exc:
            logger.debug("Go2WCamera: ROS2/sensor_msgs unavailable, no camera: %s", exc)
        except Exception as exc:  # noqa: BLE001 — attach boundary, never fatal
            logger.error("Go2WCamera attach failed: %s", exc)

    def attach_node_for_test(self, node: Any) -> None:
        """Test seam: wire the Image subscription onto a mock node with no ROS.

        Mirrors what ``attach`` does but drives the (mocked) node's factory
        directly so seam tests never import rclpy — the same pattern as
        ``Go2WHardware._install_node_for_test``. Not used in production.
        """
        node.create_subscription(None, self._topic, self._on_image, 1)
        self._node = node

    # ------------------------------------------------------------------
    # Subscription callback — decode wire bytes to numpy RGB
    # ------------------------------------------------------------------

    def _on_image(self, msg: Any) -> None:
        """Decode a sensor_msgs/Image to (H, W, 3) uint8 RGB and cache it.

        Manual decode (no cv_bridge): reshape ``msg.data`` by the row ``step``,
        crop to width*channels (drops alignment padding), and swap B<->R for
        bgr8. A malformed / undecodable message is DROPPED (the last good frame
        stays cached) — the callback never raises into the executor thread.
        """
        frame = self._decode(msg)
        if frame is None:
            return
        self._last_frame = frame
        self._last_ts = time.monotonic()

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
        """True iff a real frame has been decoded (the camera is streaming)."""
        return self._last_frame is not None

    def get_camera_image(self) -> Any:
        """Return the latest RGB frame as (H, W, 3) uint8, or None if none yet.

        A copy is returned so a caller mutating it cannot poison the cache. Logs a
        staleness warning (still serves the frame) if it is older than MAX_AGE_S.
        """
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
        get_camera_frame``: NEVER raises and NEVER returns None — with no live
        frame (camera absent / not streaming yet) it returns a black frame of the
        requested size so the perception path degrades gracefully. Resize is a
        dependency-free nearest-neighbour sample (avoids pulling in cv2/PIL).
        """
        import numpy as np

        w = self.DEFAULT_WIDTH if width is None else int(width)
        h = self.DEFAULT_HEIGHT if height is None else int(height)

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
