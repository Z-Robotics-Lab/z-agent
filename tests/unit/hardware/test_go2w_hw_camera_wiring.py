# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware <-> Go2WCamera wiring + capability-profile reflection (P5.6).

Pure-unit / ROS-free. Ground truth is the CONSUMER CONTRACT the perception / VLM
witness reaches the camera through, none of which the actor authors:

* the driver exposes ``get_camera_frame(width, height) -> (H, W, 3) uint8`` — the
  SAME duck-typed accessor look.py, visual_verifier, Go2GraspPerception and
  capability_profile._runtime_camera call — so a Go2WHardware base drives the
  look/describe/detect path exactly like the sim Go2ROS2Proxy does;
* ``has_camera()`` reports LIVENESS (a real frame has arrived), so a tool can
  tell 'camera present but not streaming' from 'streaming', while the frozen
  capability gate (callable-presence of get_camera_frame) keeps its CEO-set
  authority — the body HAS a D435i mount whether or not it is powered right now;
* an absent / down camera degrades to a black frame + has_camera() False, never
  a crash (Go2ROS2Proxy semantics), and connect() attaches the camera lazily so
  a bridge-less host stays offline-quiet.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import numpy as np


def _image_msg(height: int, width: int, encoding: str = "rgb8") -> Any:
    data = bytes((i % 256) for i in range(height * width * 3))
    return SimpleNamespace(
        height=height, width=width, encoding=encoding,
        step=width * 3, data=data,
    )


# ---------------------------------------------------------------------------
# Driver surface — get_camera_frame / has_camera exist and are offline-safe
# ---------------------------------------------------------------------------


def test_disconnected_driver_has_camera_false_and_black_frame() -> None:
    """A fresh (unconnected) driver: has_camera() False, get_camera_frame() black."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    hw = Go2WHardware()
    assert hw.has_camera() is False
    frame = hw.get_camera_frame(320, 240)
    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8
    assert int(frame.sum()) == 0


def test_get_camera_frame_is_callable_for_capability_gate() -> None:
    """capability_profile._runtime_camera duck-types ``get_camera_frame`` on _base;
    the driver must expose it as a bound callable (mount-present authority)."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    hw = Go2WHardware()
    assert callable(getattr(hw, "get_camera_frame", None))


def test_driver_frame_reflects_camera_after_ingest() -> None:
    """When the camera has a live frame, the driver serves it through get_camera_frame."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    hw = Go2WHardware()
    # Inject a live frame straight into the camera the driver owns.
    hw._camera._on_image(_image_msg(24, 32, encoding="rgb8"))  # type: ignore[attr-defined]

    assert hw.has_camera() is True
    frame = hw.get_camera_frame(32, 24)
    assert frame.shape == (24, 32, 3)
    assert int(frame.sum()) > 0


# ---------------------------------------------------------------------------
# connect() attaches the camera onto the same node (best-effort, offline-safe)
# ---------------------------------------------------------------------------


def test_install_node_for_test_attaches_camera_subscription() -> None:
    """The test seam wires the camera's Image subscription onto the driver node,
    so a Go2WHardware built for tests exposes the camera exactly like connect()."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware
    from zeno.hardware.ros2.go2w_hw_camera import Go2WCamera

    node = MagicMock()
    node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock()
    node.create_publisher.return_value = MagicMock()
    node.create_client.return_value = MagicMock()

    hw = Go2WHardware()
    hw._install_node_for_test(node)

    topics = [c.args[1] for c in node.create_subscription.call_args_list]
    assert Go2WCamera.COLOR_TOPIC in topics


# ---------------------------------------------------------------------------
# Capability profile — a Go2WHardware base makes the world's camera flag True
# ---------------------------------------------------------------------------


def test_capability_profile_reports_camera_for_go2w_real_base() -> None:
    """resolve_capability_profile(agent).camera is True for a Go2WHardware base —
    so the go2w_real world enables the detector/look path (byte-identical gate)."""
    from zeno.embodiments.capability_profile import resolve_capability_profile
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    agent = SimpleNamespace(_base=Go2WHardware(), _arm=None, _perception=None)
    profile = resolve_capability_profile(agent)
    assert profile.camera is True
    assert profile.has_base is True


def test_agent_has_camera_true_for_go2w_real_base() -> None:
    """robot._agent_has_camera (the look/detector camera gate) sees the driver camera."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware
    from zeno.vcli.worlds.robot import _agent_has_camera

    agent = SimpleNamespace(_base=Go2WHardware(), _arm=None, _perception=None)
    assert _agent_has_camera(agent) is True
