# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""The `--sim-go2` path may SKIP the external ROS2 nav stack (VECTOR_NO_ROS2=1).

`MuJoCoGo2.navigate_to` plans in-process via the visibility-graph planner, so the
external Vector Nav Stack (pathFollower / terrainAnalysis / far_planner, launched
by `_launch_ros2_stack` -> `launch_nav_only.sh`) is NOT needed for the fetch flow
(look -> navigate_to_object -> perception_grasp); it is only needed for explore
(TARE/FAR). Launching that multi-process stack inside an unattended `claude -p`
verification round OOM/SIGKILLs it (rc=137). `VECTOR_NO_ROS2=1` lets the bare
`cli --sim-go2` path run FULLY in-process so the live bare-cli fetch e2e is
runnable autonomously. Default (unset) is unchanged: the stack launches as before
for interactive sessions.
"""
from __future__ import annotations

import importlib

import pytest

cli = importlib.import_module("vector_os_nano.vcli.cli")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("VECTOR_NO_ROS2", raising=False)


def test_default_launches_ros2_stack():
    """Unset VECTOR_NO_ROS2 -> launch the stack (interactive default unchanged)."""
    assert cli._should_launch_ros2_stack() is True


def test_no_ros2_one_skips_stack(monkeypatch):
    """VECTOR_NO_ROS2=1 -> skip the external stack (lightweight in-process path)."""
    monkeypatch.setenv("VECTOR_NO_ROS2", "1")
    assert cli._should_launch_ros2_stack() is False


def test_no_ros2_zero_launches_stack(monkeypatch):
    """VECTOR_NO_ROS2=0 is an explicit opt-IN to the stack (not the skip)."""
    monkeypatch.setenv("VECTOR_NO_ROS2", "0")
    assert cli._should_launch_ros2_stack() is True


def test_no_ros2_other_value_launches_stack(monkeypatch):
    """Only the exact string "1" skips; any other value keeps the default."""
    monkeypatch.setenv("VECTOR_NO_ROS2", "true")
    assert cli._should_launch_ros2_stack() is True
