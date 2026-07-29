# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WCamera — REAL RealSense D435i RGB source over ROS2 (on-demand fetch).

Pure-unit and ROS-free: rclpy + sensor_msgs are ``sys.modules`` mocks exactly
like the go2w_hw / explore seam tests, so this file runs on a host with no
sourced ROS env and never touches the physical D435i. Ground truth here is the
WIRE + DECODE + ON-DEMAND-FETCH CONTRACT the perception / VLM witness consumes,
none of which the actor authors:

* the camera node is realsense2_camera launched by the ``d435i.service`` unit
  under the ``/nuc`` namespace => colour lands on ``/nuc/camera/color/image_raw``
  as a sensor_msgs/Image, encoding 'rgb8', published BEST_EFFORT; the default is
  overridable via ``ZENO_GO2W_COLOR_TOPIC`` (VECTOR_ fallback);
* NO standing subscription (zero baseline bandwidth over WiFi): each frame
  request opens a SHORT-LIVED BEST_EFFORT depth=1 subscription, awaits one frame,
  and tears it down — see ``_fetch``;
* decode is manual (NO cv_bridge dep): ``msg.data`` bytes -> numpy (H, W, 3)
  uint8 RGB, honouring ``msg.step`` row stride, swapping channels for 'bgr8';
* the consumer contract skills/perception/verifier actually call is
  ``get_camera_frame(width, height) -> (H, W, 3) uint8`` on the base (look.py,
  capability_profile._runtime_camera, visual_verifier, Go2GraspPerception);
* absent / not-yet-streaming camera degrades to a black frame + ``has_camera()``
  False — never a crash (a D435i-less host must stay quiet);
* a stale cached frame (older than the max-age) logs a warning but is still
  returned (mirrors Go2ROS2Proxy.get_camera_frame).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Stubs — ROS module fakes + a sensor_msgs/Image duck
# ---------------------------------------------------------------------------


def _ros_module_stubs() -> dict[str, Any]:
    """sys.modules stubs for the ROS packages the camera lazily imports."""
    return {
        "rclpy": MagicMock(),
        "rclpy.qos": MagicMock(),
        "sensor_msgs": MagicMock(),
        "sensor_msgs.msg": MagicMock(),
    }


def _image_msg(
    height: int,
    width: int,
    encoding: str = "rgb8",
    data: bytes | None = None,
    step: int | None = None,
) -> Any:
    """A duck-typed sensor_msgs/Image. ``data`` defaults to a deterministic ramp."""
    channels = 1 if encoding in ("mono8", "8UC1") else 3
    row_bytes = width * channels
    step = row_bytes if step is None else step
    if data is None:
        # deterministic per-row/col ramp so channel-order bugs are visible
        buf = bytearray()
        for r in range(height):
            row = bytearray()
            for c in range(width):
                base = (r * width + c) % 250
                row += bytes(range(base, base + channels))
            row += bytes(step - row_bytes)  # trailing pad up to step
            buf += row
        data = bytes(buf)
    return SimpleNamespace(
        height=height, width=width, encoding=encoding, step=step, data=data
    )


def _camera(topic: str | None = None):
    """A bare Go2WCamera (NOT node-bound); decode tests drive ``_on_image`` directly.

    With no bound node ``_fetch`` is a no-op, so the accessors serve whatever
    ``_on_image`` has cached — the pattern the decode / staleness tests rely on.
    """
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    kwargs = {} if topic is None else {"topic": topic}
    return Go2WCamera(**kwargs)


def _drive_fetch(cam, msg: Any, *, fire: bool = True, timeout_s: float = 1.0):
    """Bind a mock node to *cam* and run one ``_fetch`` under ROS stubs.

    When ``fire`` the mock ``create_subscription`` delivers *msg* to the camera's
    callback synchronously (as a live executor would), so ``_fetch`` returns
    without waiting. Returns ``(node, captured, ok)`` where ``captured`` records
    the topic the subscription was opened on.
    """
    node = MagicMock()
    captured: dict[str, Any] = {}

    def _sub(image_type, topic, cb, qos):
        captured["topic"] = topic
        captured["qos"] = qos
        if fire:
            cb(msg)
        return MagicMock(name="sub")

    node.create_subscription.side_effect = _sub
    cam.attach(node)
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = cam._fetch(timeout_s=timeout_s)
    return node, captured, ok


# ---------------------------------------------------------------------------
# Lazy-import + offline construction contract
# ---------------------------------------------------------------------------


def test_module_imports_without_rclpy() -> None:
    """Importing the camera must not require rclpy (env comes from sourced ROS)."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    assert Go2WCamera is not None


def test_construct_without_attach_is_absent() -> None:
    """A fresh camera (never bound, no frame) reports absent and yields black."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    cam = Go2WCamera()
    assert cam.has_camera() is False
    # get_camera_image() returns None when no frame has ever arrived.
    assert cam.get_camera_image() is None
    # get_camera_frame() still returns a black frame of the requested size.
    frame = cam.get_camera_frame(64, 48)
    assert frame.shape == (48, 64, 3)
    assert frame.dtype == np.uint8
    assert int(frame.sum()) == 0


def test_default_topic_is_nuc_namespaced_color() -> None:
    """The default topic is the /nuc-namespaced d435i colour stream."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    assert Go2WCamera.COLOR_TOPIC == "/nuc/camera/color/image_raw"
    assert Go2WCamera()._topic == "/nuc/camera/color/image_raw"


def test_env_overrides_color_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZENO_GO2W_COLOR_TOPIC (then VECTOR_ fallback) overrides the default."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    monkeypatch.setenv("ZENO_GO2W_COLOR_TOPIC", "/nuc/camera/color/image_raw2")
    assert Go2WCamera()._topic == "/nuc/camera/color/image_raw2"

    monkeypatch.delenv("ZENO_GO2W_COLOR_TOPIC", raising=False)
    monkeypatch.setenv("VECTOR_GO2W_COLOR_TOPIC", "/legacy/color")
    assert Go2WCamera()._topic == "/legacy/color"


# ---------------------------------------------------------------------------
# Binding — attach holds the node WITHOUT opening a standing subscription
# ---------------------------------------------------------------------------


def test_attach_opens_no_standing_subscription() -> None:
    """Zero baseline bandwidth: attach binds the node but subscribes to nothing."""
    cam = _camera()
    node = MagicMock()
    cam.attach(node)
    assert cam._node is node
    node.create_subscription.assert_not_called()


# ---------------------------------------------------------------------------
# On-demand fetch — short-lived Image sub on the colour topic, BEST_EFFORT QoS,
# torn down after one frame
# ---------------------------------------------------------------------------


def test_fetch_subscribes_to_color_topic_best_effort_then_tears_down() -> None:
    cam = _camera()
    node, captured, ok = _drive_fetch(cam, _image_msg(2, 2, encoding="rgb8"))
    assert ok is True
    assert captured["topic"] == cam.COLOR_TOPIC
    # The short-lived subscription is destroyed after the frame arrives (the
    # BEST_EFFORT QoS is asserted in test_fetch_uses_best_effort_reliability).
    node.destroy_subscription.assert_called_once()
    assert cam.has_camera() is True


def test_fetch_uses_best_effort_reliability() -> None:
    """The QoSProfile the fetch builds is BEST_EFFORT — matches the d435i publisher."""
    cam = _camera()
    node = MagicMock()
    node.create_subscription.side_effect = (
        lambda image_type, topic, cb, qos: cb(_image_msg(2, 2)) or MagicMock()
    )
    cam.attach(node)
    stubs = _ros_module_stubs()
    with patch.dict("sys.modules", stubs):
        cam._fetch(timeout_s=1.0)
    qos_mod = stubs["rclpy.qos"]
    assert qos_mod.QoSProfile.called
    _, kwargs = qos_mod.QoSProfile.call_args
    assert kwargs.get("reliability") == qos_mod.ReliabilityPolicy.BEST_EFFORT


def test_fetch_times_out_returns_false_and_caches_nothing() -> None:
    """No frame within the window: honest False, cache untouched, sub torn down."""
    cam = _camera()
    node = MagicMock()
    node.create_subscription.return_value = MagicMock()  # never delivers a frame
    cam.attach(node)
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = cam._fetch(timeout_s=0.05)
    assert ok is False
    assert cam._last_frame is None
    node.destroy_subscription.assert_called_once()


def test_fetch_is_noop_without_bound_node() -> None:
    """With no node bound, a fetch is a no-op (offline / pre-connect safe)."""
    cam = _camera()
    assert cam._fetch() is False


# ---------------------------------------------------------------------------
# Decode math — rgb8 passthrough, bgr8 channel swap, step stride, guards
# (driven straight through the callback; a bare camera serves the cache)
# ---------------------------------------------------------------------------


def test_rgb8_decodes_to_hwc_uint8_passthrough() -> None:
    """rgb8: bytes reshape to (H, W, 3) with channels in R,G,B order untouched."""
    cam = _camera()

    # A tiny explicit frame so channel order is unambiguous.
    #   pixel (0,0) = 10,20,30 ; pixel (0,1) = 40,50,60
    data = bytes([10, 20, 30, 40, 50, 60])
    cam._on_image(_image_msg(1, 2, encoding="rgb8", data=data, step=6))

    assert cam.has_camera() is True
    frame = cam.get_camera_image()
    assert frame.shape == (1, 2, 3)
    assert frame.dtype == np.uint8
    assert list(frame[0, 0]) == [10, 20, 30]
    assert list(frame[0, 1]) == [40, 50, 60]


def test_bgr8_is_swapped_to_rgb() -> None:
    """bgr8: the wire is B,G,R — decode must return R,G,B so the VLM sees truth."""
    cam = _camera()

    # wire bytes B,G,R = 30,20,10  ->  decoded R,G,B must be 10,20,30
    data = bytes([30, 20, 10])
    cam._on_image(_image_msg(1, 1, encoding="bgr8", data=data, step=3))

    frame = cam.get_camera_image()
    assert list(frame[0, 0]) == [10, 20, 30]


def test_step_stride_padding_is_respected() -> None:
    """A row step larger than width*3 (alignment padding) must not corrupt pixels."""
    cam = _camera()

    # 2x1 rgb8, but step=5 (2 bytes of pad after the 3 real bytes per row).
    row0 = bytes([1, 2, 3]) + bytes([0, 0])   # pixel 1,2,3 then pad
    row1 = bytes([4, 5, 6]) + bytes([0, 0])
    cam._on_image(_image_msg(2, 1, encoding="rgb8", data=row0 + row1, step=5))

    frame = cam.get_camera_image()
    assert frame.shape == (2, 1, 3)
    assert list(frame[0, 0]) == [1, 2, 3]
    assert list(frame[1, 0]) == [4, 5, 6]


def test_undersized_buffer_is_rejected_not_crashed() -> None:
    """A truncated / malformed buffer must not update the frame or raise."""
    cam = _camera()

    # claims 4x4x3 = 48 bytes but only 3 provided.
    cam._on_image(_image_msg(4, 4, encoding="rgb8", data=bytes([1, 2, 3]), step=12))
    # No valid frame cached -> still absent, no exception escaped the callback.
    assert cam.has_camera() is False
    assert cam.get_camera_image() is None


def test_unknown_encoding_is_ignored() -> None:
    """An encoding we cannot decode (e.g. yuyv) is dropped, not crashed."""
    cam = _camera()

    cam._on_image(_image_msg(2, 2, encoding="yuyv", data=bytes(8), step=4))
    assert cam.has_camera() is False


# ---------------------------------------------------------------------------
# get_camera_frame — resize contract + copy isolation
# ---------------------------------------------------------------------------


def test_get_camera_frame_returns_requested_size() -> None:
    """get_camera_frame(w, h) returns exactly (h, w, 3) even if the source differs."""
    cam = _camera()
    cam._on_image(_image_msg(30, 40, encoding="rgb8"))  # source 40x30

    frame = cam.get_camera_frame(320, 240)
    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8


def test_get_camera_image_returns_a_copy() -> None:
    """Mutating the returned frame must not poison the internal cache."""
    cam = _camera()
    cam._on_image(_image_msg(2, 2, encoding="rgb8"))

    frame = cam.get_camera_image()
    frame[:] = 255
    again = cam.get_camera_image()
    assert int(again.sum()) != int(frame.sum())


# ---------------------------------------------------------------------------
# Staleness guard — warns on an old frame but still serves it
# ---------------------------------------------------------------------------


def test_stale_frame_warns_but_is_served(caplog: pytest.LogCaptureFixture) -> None:
    """A frame older than MAX_AGE_S logs a warning yet is still returned."""
    import logging

    cam = _camera()

    # Freeze the clock: ingest at t0, read far in the future. No node bound, so
    # get_camera_image's _fetch is a no-op and never calls monotonic() itself.
    times = iter([100.0, 100.0 + cam.MAX_AGE_S + 5.0])
    with patch("zeno.hardware.ros2.go2w_hw_camera.time.monotonic",
               side_effect=lambda: next(times)):
        cam._on_image(_image_msg(2, 2, encoding="rgb8"))  # cached at t=100
        with caplog.at_level(logging.WARNING):
            frame = cam.get_camera_image()  # read at t=100+age+5

    assert frame is not None  # still served
    assert any("old" in r.message.lower() or "stale" in r.message.lower()
               for r in caplog.records)


def test_fresh_frame_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    cam = _camera()

    times = iter([200.0, 200.2])  # 0.2s old — well within MAX_AGE_S
    with patch("zeno.hardware.ros2.go2w_hw_camera.time.monotonic",
               side_effect=lambda: next(times)):
        cam._on_image(_image_msg(2, 2, encoding="rgb8"))
        with caplog.at_level(logging.WARNING):
            cam.get_camera_image()

    assert not any("old" in r.message.lower() or "stale" in r.message.lower()
                   for r in caplog.records)


# ---------------------------------------------------------------------------
# Custom topic override (ctor)
# ---------------------------------------------------------------------------


def test_custom_topic_is_honoured() -> None:
    cam = _camera(topic="/my/cam/image")
    assert cam._topic == "/my/cam/image"
    assert cam.COLOR_TOPIC not in ("/my/cam/image",)
    _, captured, ok = _drive_fetch(cam, _image_msg(2, 2, encoding="rgb8"))
    assert ok is True
    assert captured["topic"] == "/my/cam/image"
