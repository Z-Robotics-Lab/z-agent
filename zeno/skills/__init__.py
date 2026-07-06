# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Built-in robot skills — all use @skill decorator for routing metadata."""
from __future__ import annotations

from zeno.skills.describe import DescribeSkill
from zeno.skills.detect import DetectSkill
from zeno.skills.gripper import GripperCloseSkill, GripperOpenSkill
from zeno.skills.handover import HandoverSkill
from zeno.skills.home import HomeSkill
from zeno.skills.pick import PickSkill
from zeno.skills.place import PlaceSkill
from zeno.skills.scan import ScanSkill
from zeno.skills.wave import WaveSkill

__all__ = [
    "DescribeSkill",
    "DetectSkill",
    "GripperCloseSkill",
    "GripperOpenSkill",
    "HandoverSkill",
    "HomeSkill",
    "PickSkill",
    "PlaceSkill",
    "ScanSkill",
    "WaveSkill",
    "get_default_skills",
]


def get_default_skills() -> list:
    """Return one instance of each built-in skill."""
    return [
        HomeSkill(),
        ScanSkill(),
        DescribeSkill(),
        DetectSkill(),
        PickSkill(),
        PlaceSkill(),
        HandoverSkill(),
        GripperOpenSkill(),
        GripperCloseSkill(),
        WaveSkill(),
    ]
