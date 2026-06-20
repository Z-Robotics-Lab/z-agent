# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2GraspPerception — REAL RGB-D + VLM + EdgeTAM backend on the Go2 d435 camera.

The perception backend PerceptionGraspSkill consumes on the go2+piper sim. Unlike
the legacy MuJoCoPerception (which returns ground-truth poses + a zero depth
stub), this backend uses ONLY what a real robot has:

  - RGB + metric depth rendered from the on-robot d435_rgb / d435_depth MuJoCo
    cameras (MuJoCoGo2.get_camera_frame / get_depth_frame — float32 metres);
  - intrinsics from the MJCF camera fovy (depth_projection.mujoco_intrinsics);
  - the exact camera->world pose (MuJoCoGo2.get_camera_pose -> cam_xpos/cam_xmat);
  - Moondream VLM for detection, EdgeTAM for segmentation.

It exposes NO get_object_positions / ground-truth pose — the 3D grasp point is
derived from depth + mask downstream (grasp_point.py). VLM + EdgeTAM are loaded
LAZILY on first use so importing this module needs no GPU/torch.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from vector_os_nano.core.types import Detection
from vector_os_nano.perception.depth_projection import mujoco_intrinsics

logger = logging.getLogger(__name__)


class Go2GraspPerception:
    """Real RGB-D + VLM + EdgeTAM perception over a MuJoCoGo2 base.

    Args:
        base: A connected MuJoCoGo2 (provides get_camera_frame/get_depth_frame/
            get_camera_pose). Real depth is in METRES.
        vlm: Optional pre-built VLMDetector (else lazily constructed).
        tracker: Optional pre-built EdgeTAMTracker (else lazily constructed).
        width/height: Render resolution; intrinsics derive from fovy + this.
    """

    def __init__(
        self,
        base: Any,
        *,
        vlm: Any = None,
        tracker: Any = None,
        width: int = 640,
        height: int = 480,
    ) -> None:
        self._base = base
        self._vlm = vlm
        self._tracker = tracker
        self._w = int(width)
        self._h = int(height)

    # --- frames / geometry ---------------------------------------------------

    def get_color_frame(self) -> np.ndarray:
        return self._base.get_camera_frame(self._w, self._h)

    def get_depth_frame(self) -> np.ndarray:
        """(H, W) float32 depth in METRES (use depth_scale=1.0 downstream)."""
        return self._base.get_depth_frame(self._w, self._h)

    def get_intrinsics(self):
        return mujoco_intrinsics(self._w, self._h, vfov_deg=42.0)

    def get_camera_pose(self) -> tuple:
        """(cam_xpos (3,), cam_xmat (9,)) for the d435 camera, world frame."""
        return self._base.get_camera_pose()

    # --- VLM + EdgeTAM (lazy) -------------------------------------------------

    def _ensure_vlm(self) -> None:
        if self._vlm is None:
            from vector_os_nano.perception.vlm import VLMDetector
            logger.info("[GO2-PERCEPT] loading VLM detector (lazy)")
            self._vlm = VLMDetector()

    def _ensure_tracker(self) -> None:
        if self._tracker is None:
            from vector_os_nano.perception.tracker import EdgeTAMTracker
            logger.info("[GO2-PERCEPT] loading EdgeTAM tracker (lazy)")
            self._tracker = EdgeTAMTracker()

    def detect(self, query: str) -> list[Detection]:
        """Run the VLM on the live RGB frame; pixel-space bboxes."""
        self._ensure_vlm()
        return self._vlm.detect(self.get_color_frame(), query)

    def segment(self, image: np.ndarray, bbox: Any) -> np.ndarray | None:
        """EdgeTAM mask for a single bbox on *image*, or None."""
        self._ensure_tracker()
        x1, y1, x2, y2 = (int(round(float(v))) for v in bbox)
        results = self._tracker.init_track(image, bboxes=[(x1, y1, x2, y2)])
        if not results:
            return None
        mask = results[0].get("mask")
        return mask if mask is not None else None

    # --- lifecycle -----------------------------------------------------------

    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        """Release the EdgeTAM inference state (frees GPU between runs)."""
        if self._tracker is not None:
            try:
                self._tracker.stop()
            except Exception as exc:  # noqa: BLE001
                logger.debug("[GO2-PERCEPT] tracker stop failed: %s", exc)
