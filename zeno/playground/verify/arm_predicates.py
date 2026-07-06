# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Re-export shim: arm sim-oracle predicates moved to the kernel.

The deterministic arm verify predicates are now SINGLE-SOURCED in
``zeno.vcli.worlds.arm_sim_oracle`` so BOTH the playground world and the
plain RobotWorld can consume them without the kernel importing the playground
(ADR-008 / kernel rule 2: the dependency edge is one-way, playground -> kernel).
This module stays only so existing imports keep resolving; it adds no logic.
"""

from __future__ import annotations

from zeno.vcli.worlds.arm_sim_oracle import (
    _NEAR_EE_RADIUS,
    _LIFT_MIN_Z,
    _HOME_TOL_RAD,
    _HOME_JOINTS,
    _ee_position,
    _get_arm,
    _gripper_is_holding,
    _parse_region,
    make_arm_at_home,
    make_holding_object,
    make_placed_count,
)

__all__ = [
    "_HOME_JOINTS",
    "_HOME_TOL_RAD",
    "_LIFT_MIN_Z",
    "_NEAR_EE_RADIUS",
    "_ee_position",
    "_get_arm",
    "_gripper_is_holding",
    "_parse_region",
    "make_arm_at_home",
    "make_holding_object",
    "make_placed_count",
]
