# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Re-export shim: scene sim-oracle predicates moved to the kernel.

The deterministic ``detect_objects`` / ``describe_scene`` verify predicates are
now SINGLE-SOURCED in ``vector_os_nano.vcli.worlds.arm_sim_oracle`` so BOTH the
playground world and the plain RobotWorld can consume them without the kernel
importing the playground (ADR-008 / kernel rule 2: the dependency edge is one-way,
playground -> kernel). This module stays only so existing imports keep resolving;
it adds no logic.
"""

from __future__ import annotations

from vector_os_nano.vcli.worlds.arm_sim_oracle import (
    _scene_objects,
    make_describe_scene,
    make_detect_objects,
    make_detect_producer,
)

__all__ = [
    "_scene_objects",
    "make_describe_scene",
    "make_detect_objects",
    "make_detect_producer",
]
