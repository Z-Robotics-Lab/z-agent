# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Embodiment configuration package.

An embodiment (robot morphology) is described by a per-robot ``robot.yaml``
manifest — spawn pose, joint/stance layout, sensor mounts, root body, gait/policy
reference and a capability profile — the way a ROS2 nav stack ships per-robot
param YAMLs (project CLAUDE.md Rule 11: "embodiments are CONFIG, not code").

Stage 1 (this module) provides the typed, frozen config schema and a loader.
Stage 2 wires the drivers to READ these configs instead of hardcoding constants.
"""
from __future__ import annotations

from vector_os_nano.embodiments.config import (
    EmbodimentConfig,
    load_embodiment_config,
)

__all__ = ["EmbodimentConfig", "load_embodiment_config"]
