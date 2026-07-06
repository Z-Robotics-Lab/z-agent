# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Camera-to-base calibration transform for Vector OS skills.

Loads the affine transform matrix produced by the workspace calibration
script (workspace_calibration.yaml) and applies it to convert 3D positions
from the camera frame to the robot base_link frame.

No ROS2 imports — pure Python + numpy.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import yaml

logger = logging.getLogger(__name__)


def load_calibration(calib_file: str | None = None) -> np.ndarray:
    """Load camera→base_link 4x4 affine transform matrix from YAML.

    File resolution order:
      1. ``calib_file`` argument (explicit caller override).
      2. ``VECTOR_CALIB_FILE`` environment variable.
      3. None — no calibration file configured.

    When no file is configured or the resolved path does not exist, returns
    a 4x4 identity matrix and logs at DEBUG level.  Absence of a calibration
    file is the expected state in simulation (the oracle returns world-frame
    coordinates directly), so it is not a warning.

    Args:
        calib_file: explicit path to workspace_calibration.yaml, or None to
            fall back to the VECTOR_CALIB_FILE env var (then to identity).

    Returns:
        4x4 numpy float64 array representing the homogeneous transform.
    """
    path: str | None = calib_file or os.environ.get("VECTOR_CALIB_FILE")
    if not path or not Path(path).exists():
        logger.debug(
            "No calibration file configured/found%s — using identity transform.",
            f" (tried {path})" if path else "",
        )
        return np.eye(4)

    with open(path) as f:
        data = yaml.safe_load(f)

    T = np.array(data["transform_matrix"], dtype=np.float64)
    logger.info(
        "Loaded workspace calibration from %s (mean error: %s mm)",
        path,
        data.get("mean_error_mm", "?"),
    )
    return T


def camera_to_base(cam_pos: np.ndarray, T: np.ndarray) -> np.ndarray:
    """Transform a 3D position from camera frame to base_link frame.

    Args:
        cam_pos: (3,) array — position in camera frame [x, y, z] in metres.
        T: 4x4 homogeneous transform matrix (camera→base).

    Returns:
        (3,) array — position in base_link frame [x, y, z] in metres.
    """
    p_hom = np.array([cam_pos[0], cam_pos[1], cam_pos[2], 1.0], dtype=np.float64)
    p_base = T @ p_hom
    return p_base[:3]
