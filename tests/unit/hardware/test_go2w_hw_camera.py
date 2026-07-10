# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WCamera — REAL RealSense D435i RGB source over ROS2 (P5.6 look path).

Pure-unit and ROS-free: rclpy + sensor_msgs are ``sys.modules`` mocks exactly
like the go2w_hw / explore seam tests, so this file runs on a host with no
sourced ROS env and never touches the physical D435i. Ground truth here is the
WIRE + DECODE CONTRACT the perception / VLM witness consumes, none of which the
actor authors:

* the camera node is realsense2_camera launched by the ``d435i.service`` unit
  (``camera_name=camera`` / ``camera_namespace=camera`` defaults) => colour lands
  on ``/camera/camera/color/image_raw`` as a sensor_msgs/Image, encoding 'rgb8';
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
    """A Go2WCamera bound to a MagicMock node; returns (cam, node)."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    node = MagicMock()
    kwargs = {} if topic is None else {"topic": topic}
    cam = Go2WCamera(**kwargs)
    with patch.dict("sys.modules", _ros_module_stubs()):
        cam.attach(node)
    return cam, node


def _image_callback(node: MagicMock, topic: str) -> Any:
    """Extract the Image subscription callback the camera registered."""
    for call in node.create_subscription.call_args_list:
        if call.args[1] == topic:
            return call.args[2]
    raise AssertionError(f"no subscription created for {topic}")


# ---------------------------------------------------------------------------
# Lazy-import + offline construction contract
# ---------------------------------------------------------------------------


def test_module_imports_without_rclpy() -> None:
    """Importing the camera must not require rclpy (env comes from sourced ROS)."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    assert Go2WCamera is not None


def test_construct_without_attach_is_absent() -> None:
    """A fresh camera (never attached, no frame) reports absent and yields black."""
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


def test_default_topic_is_realsense_color() -> None:
    """The default topic is the realsense2_camera default-namespace colour stream."""
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    assert Go2WCamera.COLOR_TOPIC == "/camera/camera/color/image_raw"


# ---------------------------------------------------------------------------
# Subscription wiring — Image on the colour topic, BEST_EFFORT sensor QoS
# ---------------------------------------------------------------------------


def test_attach_subscribes_to_color_topic() -> None:
    cam, node = _camera()
    topics = [c.args[1] for c in node.create_subscription.call_args_list]
    assert cam.COLOR_TOPIC in topics


def test_attach_uses_best_effort_sensor_qos() -> None:
    """Camera streams are sensor data — BEST_EFFORT so we never block the node."""
    from zeno.hardware.ros2 import go2w_hw_camera as mod

    node = MagicMock()
    with patch.dict("sys.modules", _ros_module_stubs()) as mods:
        qos_mod = mods["rclpy.qos"]
        cam = mod.Go2WCamera()
        cam.attach(node)
    # A QoSProfile was constructed with BEST_EFFORT reliability.
    assert qos_mod.QoSProfile.called
    _, kwargs = qos_mod.QoSProfile.call_args
    assert kwargs.get("reliability") == qos_mod.ReliabilityPolicy.BEST_EFFORT


# ---------------------------------------------------------------------------
# Decode math — rgb8 passthrough, bgr8 channel swap, step stride, guards
# ---------------------------------------------------------------------------


def test_rgb8_decodes_to_hwc_uint8_passthrough() -> None:
    """rgb8: bytes reshape to (H, W, 3) with channels in R,G,B order untouched."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    # A tiny explicit frame so channel order is unambiguous.
    #   pixel (0,0) = 10,20,30 ; pixel (0,1) = 40,50,60
    data = bytes([10, 20, 30, 40, 50, 60])
    cb(_image_msg(1, 2, encoding="rgb8", data=data, step=6))

    assert cam.has_camera() is True
    frame = cam.get_camera_image()
    assert frame.shape == (1, 2, 3)
    assert frame.dtype == np.uint8
    assert list(frame[0, 0]) == [10, 20, 30]
    assert list(frame[0, 1]) == [40, 50, 60]


def test_bgr8_is_swapped_to_rgb() -> None:
    """bgr8: the wire is B,G,R — decode must return R,G,B so the VLM sees truth."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    # wire bytes B,G,R = 30,20,10  ->  decoded R,G,B must be 10,20,30
    data = bytes([30, 20, 10])
    cb(_image_msg(1, 1, encoding="bgr8", data=data, step=3))

    frame = cam.get_camera_image()
    assert list(frame[0, 0]) == [10, 20, 30]


def test_step_stride_padding_is_respected() -> None:
    """A row step larger than width*3 (alignment padding) must not corrupt pixels."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    # 2x1 rgb8, but step=5 (2 bytes of pad after the 3 real bytes per row).
    row0 = bytes([1, 2, 3]) + bytes([0, 0])   # pixel 1,2,3 then pad
    row1 = bytes([4, 5, 6]) + bytes([0, 0])
    cb(_image_msg(2, 1, encoding="rgb8", data=row0 + row1, step=5))

    frame = cam.get_camera_image()
    assert frame.shape == (2, 1, 3)
    assert list(frame[0, 0]) == [1, 2, 3]
    assert list(frame[1, 0]) == [4, 5, 6]


def test_undersized_buffer_is_rejected_not_crashed() -> None:
    """A truncated / malformed buffer must not update the frame or raise."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    # claims 4x4x3 = 48 bytes but only 3 provided.
    cb(_image_msg(4, 4, encoding="rgb8", data=bytes([1, 2, 3]), step=12))
    # No valid frame cached -> still absent, no exception escaped the callback.
    assert cam.has_camera() is False
    assert cam.get_camera_image() is None


def test_unknown_encoding_is_ignored() -> None:
    """An encoding we cannot decode (e.g. yuyv) is dropped, not crashed."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    cb(_image_msg(2, 2, encoding="yuyv", data=bytes(8), step=4))
    assert cam.has_camera() is False


# ---------------------------------------------------------------------------
# get_camera_frame — resize contract + copy isolation
# ---------------------------------------------------------------------------


def test_get_camera_frame_returns_requested_size() -> None:
    """get_camera_frame(w, h) returns exactly (h, w, 3) even if the source differs."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)
    cb(_image_msg(30, 40, encoding="rgb8"))  # source 40x30

    frame = cam.get_camera_frame(320, 240)
    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8


def test_get_camera_image_returns_a_copy() -> None:
    """Mutating the returned frame must not poison the internal cache."""
    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)
    cb(_image_msg(2, 2, encoding="rgb8"))

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

    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    # Freeze the clock: ingest at t0, read far in the future.
    times = iter([100.0, 100.0 + cam.MAX_AGE_S + 5.0])
    with patch("zeno.hardware.ros2.go2w_hw_camera.time.monotonic",
               side_effect=lambda: next(times)):
        cb(_image_msg(2, 2, encoding="rgb8"))  # cached at t=100
        with caplog.at_level(logging.WARNING):
            frame = cam.get_camera_image()  # read at t=100+age+5

    assert frame is not None  # still served
    assert any("old" in r.message.lower() or "stale" in r.message.lower()
               for r in caplog.records)


def test_fresh_frame_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    cam, node = _camera()
    cb = _image_callback(node, cam.COLOR_TOPIC)

    times = iter([200.0, 200.2])  # 0.2s old — well within MAX_AGE_S
    with patch("zeno.hardware.ros2.go2w_hw_camera.time.monotonic",
               side_effect=lambda: next(times)):
        cb(_image_msg(2, 2, encoding="rgb8"))
        with caplog.at_level(logging.WARNING):
            cam.get_camera_image()

    assert not any("old" in r.message.lower() or "stale" in r.message.lower()
                   for r in caplog.records)


# ---------------------------------------------------------------------------
# Custom topic override
# ---------------------------------------------------------------------------


def test_custom_topic_is_honoured() -> None:
    cam, node = _camera(topic="/my/cam/image")
    topics = [c.args[1] for c in node.create_subscription.call_args_list]
    assert "/my/cam/image" in topics
    assert cam.COLOR_TOPIC not in topics
