# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2-6: expected 'ROS2 unavailable' must not bleed an ERROR log into the REPL.

On a macOS/Windows sim host rclpy is absent; that is an expected fallback, not an
error. An ERROR-level line there interleaves with the live rich panels. The proxy
must log the unavailable case at DEBUG so it stays quiet in the non-verbose REPL
(and is still visible under --verbose).
"""
import importlib.util
import logging

import pytest

_RCLPY_PRESENT = importlib.util.find_spec("rclpy") is not None
_PROXY_LOGGER = "vector_os_nano.hardware.sim.go2_ros2_proxy"


@pytest.mark.skipif(_RCLPY_PRESENT, reason="tests the rclpy-absent fallback path")
def test_ros2_proxy_unavailable_logs_debug_not_error(caplog):
    from vector_os_nano.hardware.sim.go2_ros2_proxy import Go2ROS2Proxy

    proxy = Go2ROS2Proxy()
    with caplog.at_level(logging.DEBUG, logger=_PROXY_LOGGER):
        proxy.connect()

    assert proxy._connected is False
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert not errors, (
        f"ROS2-unavailable must not log ERROR (it bleeds into the panels); "
        f"got: {[r.getMessage() for r in errors]}"
    )
    debugs = [
        r for r in caplog.records
        if r.levelno == logging.DEBUG and "unavailable" in r.getMessage().lower()
    ]
    assert debugs, "expected a DEBUG 'ROS2 unavailable' record (visible under --verbose)"
