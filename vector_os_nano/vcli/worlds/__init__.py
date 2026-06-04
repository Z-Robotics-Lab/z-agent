# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""World plugins for the agent kernel.

A *world* adapts the domain-general kernel to a domain (dev/code, robot, ...).
The default ``DevWorld`` ships with the kernel; ``RobotWorld`` is selected when
a robot agent is connected.
"""

from __future__ import annotations

from typing import Any

from vector_os_nano.vcli.worlds.base import DecomposeVocab, World
from vector_os_nano.vcli.worlds.dev import DevWorld, dev_verify_namespace
from vector_os_nano.vcli.worlds.robot import RobotWorld

__all__ = [
    "World",
    "DecomposeVocab",
    "DevWorld",
    "RobotWorld",
    "dev_verify_namespace",
    "resolve_world",
]


def resolve_world(agent: Any = None) -> World:
    """Select the active world.

    A connected robot agent selects the robot world; otherwise the default dev
    world (the cross-platform, robot-free general agent).
    """
    if agent is not None:
        return RobotWorld()
    return DevWorld()
