# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Operator interrupt: blocking navigate must be cancellable instantly.

Field trace 2026-07-10: during '往前走5米' the REPL was blocked inside
navigate_to's poll loop; the operator could not type stop, and Ctrl+C
crashed the whole process (KeyboardInterrupt through time.sleep).
"""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

ROS_STUBS = {}


def _hw():
    from zeno.hardware.ros2.go2w_hw import Go2WHardware
    hw = Go2WHardware()
    # simulate a connected driver without ROS: node/pub present, odom flowing
    hw._node = object()
    hw._waypoint_pub = type("P", (), {"publish": lambda self, m: None})()
    hw._position = (0.0, 0.0, 0.0)
    hw._publish_waypoint = lambda x, y: None
    calls = {"nav_cancel": 0}
    hw.nav_cancel = lambda: calls.__setitem__("nav_cancel", calls["nav_cancel"] + 1) or True
    return hw, calls


def test_cancel_navigation_unblocks_navigate_fast():
    hw, calls = _hw()
    t0 = time.monotonic()
    canceller = threading.Timer(0.3, hw.cancel_navigation)
    canceller.start()
    ok = hw.navigate_to(5.0, 0.0, timeout=30.0)
    dt = time.monotonic() - t0
    assert ok is False
    assert dt < 3.0  # unblocked promptly, not the 30s timeout
    assert calls["nav_cancel"] >= 1  # latched goal actually cleared


def test_cancel_flag_resets_for_next_navigation():
    hw, _ = _hw()
    hw.cancel_navigation()
    # a NEW navigate must not be pre-cancelled by the stale flag; robot is at
    # goal immediately so it returns True fast
    hw._position = (1.0, 0.0, 0.0)
    assert hw.navigate_to(1.0, 0.0, timeout=5.0) is True
