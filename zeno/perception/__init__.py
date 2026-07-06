# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Perception stack — camera drivers, VLM detection, tracking, pointcloud.

No ROS2 imports anywhere in this subpackage.
ROS2 perception bridge lives in zeno.ros2.nodes.perception_node.

Public API
----------
PerceptionProtocol   — structural Protocol all backends satisfy
RealSenseCamera      — Intel RealSense D405 driver (lazy pyrealsense2)
VLMDetector          — Moondream VLM (local / Station / API)
EdgeTAMTracker       — EdgeTAM segmentation tracker (lazy torch)
PointCloudProcessor  — functional helpers: rgbd_to_pointcloud_fast, etc.
PerceptionPipeline   — orchestrator: camera -> VLM -> tracker -> 3D
Calibration          — camera-to-arm coordinate transform
"""
from __future__ import annotations

from zeno.perception.base import PerceptionProtocol
from zeno.perception.calibration import Calibration
from zeno.perception.pipeline import PerceptionPipeline
from zeno.perception.pointcloud import (
    pointcloud_to_bbox3d_fast,
    remove_statistical_outliers,
    rgbd_to_pointcloud_fast,
)
from zeno.perception.realsense import RealSenseCamera
from zeno.perception.tracker import EdgeTAMTracker
from zeno.perception.vlm import VLMDetector


# Functional namespace alias for pointcloud utilities (matches task spec)
class PointCloudProcessor:
    """Namespace for pointcloud utility functions.

    Provides a class-level alias so callers can write:
        from zeno.perception import PointCloudProcessor
        pts, colors = PointCloudProcessor.rgbd_to_pointcloud_fast(...)
    """

    rgbd_to_pointcloud_fast = staticmethod(rgbd_to_pointcloud_fast)
    pointcloud_to_bbox3d_fast = staticmethod(pointcloud_to_bbox3d_fast)
    remove_statistical_outliers = staticmethod(remove_statistical_outliers)


__all__ = [
    "PerceptionProtocol",
    "RealSenseCamera",
    "VLMDetector",
    "EdgeTAMTracker",
    "PointCloudProcessor",
    "PerceptionPipeline",
    "Calibration",
    # Direct function exports
    "rgbd_to_pointcloud_fast",
    "pointcloud_to_bbox3d_fast",
    "remove_statistical_outliers",
]
