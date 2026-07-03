# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for _build_go2_perception (Spec 3 — perception wiring guard).

The go2 sim launchers (SimStartTool._start_go2 and the in-process --sim-go2
path in cli) must wire a REAL RGB-D + detector + segmenter perception backend
onto agent._perception so look/explore can depth-localize VLM-named objects to
accurate world (x, y, z) via localize_objects_3d.

Guard contract: only wire perception when the base exposes the full RGB-D frame
source (get_camera_frame / get_depth_frame / get_camera_pose).  A base without a
camera (or any construction failure) leaves perception None so a launch never
crashes and non-perception embodiments stay unaffected.

No MuJoCo, no GPU, no network — pure stub bases.
"""
from __future__ import annotations

from typing import Any

from vector_os_nano.vcli.tools.sim_tool import _build_go2_perception


class _FullCameraBase:
    """Stub base exposing the complete RGB-D frame source."""

    def get_camera_frame(self, width: int = 320, height: int = 240) -> Any:
        return None

    def get_depth_frame(self, width: int = 320, height: int = 240) -> Any:
        return None

    def get_camera_pose(self) -> tuple:
        return ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))


class _NoCameraBase:
    """Stub locomotion-only base with NO camera (e.g. a bare driver)."""

    def get_position(self) -> tuple:
        return (0.0, 0.0, 0.0)


class _MissingDepthBase:
    """Has camera + pose but no depth frame — must NOT wire perception."""

    def get_camera_frame(self, width: int = 320, height: int = 240) -> Any:
        return None

    def get_camera_pose(self) -> tuple:
        return ((0.0, 0.0, 0.0), tuple([1.0] + [0.0] * 8))


def test_build_perception_with_full_camera_base():
    """A base with the full RGB-D frame source yields a Go2GraspPerception."""
    from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception

    base = _FullCameraBase()
    perception = _build_go2_perception(base)
    assert isinstance(perception, Go2GraspPerception)
    # The perception wraps the exact base it was given.
    assert perception._base is base


def test_build_perception_none_when_base_is_none():
    """base=None -> perception None (never crash)."""
    assert _build_go2_perception(None) is None


def test_build_perception_none_when_no_camera():
    """A locomotion-only base (no camera) -> perception None."""
    assert _build_go2_perception(_NoCameraBase()) is None


def test_build_perception_none_when_missing_depth():
    """A base missing get_depth_frame -> perception None (guard rejects it)."""
    assert _build_go2_perception(_MissingDepthBase()) is None


def test_built_perception_is_localizer_usable():
    """The wired perception satisfies localize_objects_3d's usability guard
    (exposes every required method), so depth-localization can run end to end."""
    from vector_os_nano.perception.object_localizer import _perception_is_usable

    perception = _build_go2_perception(_FullCameraBase())
    assert perception is not None
    assert _perception_is_usable(perception) is True


# ---------------------------------------------------------------------------
# describe seam: caption() / visual_query() route to Go2VLMPerception.describe_scene
# (R248 — the brain's `describe` recovery raised AttributeError because
# Go2GraspPerception exposed detect() but not caption()/visual_query()).
# ---------------------------------------------------------------------------


class _FrameBase:
    """Stub base yielding a fixed RGB frame (never a ground-truth pose)."""

    def get_camera_frame(self, width: int = 640, height: int = 480) -> Any:
        import numpy as np

        return np.zeros((height, width, 3), dtype=np.uint8)


class _FakeDescribeVLM:
    """Stub Go2VLMPerception recording the frame it was asked to describe."""

    def __init__(self) -> None:
        self.calls = 0

    def describe_scene(self, frame: Any) -> Any:
        from vector_os_nano.perception.vlm_go2 import (
            DetectedObject,
            SceneDescription,
        )

        self.calls += 1
        return SceneDescription(
            summary="a courtyard tabletop",
            objects=[DetectedObject(name="green bottle", description="", confidence=0.9)],
            room_type="courtyard",
            details="A sandstone courtyard with a green bottle on a table.",
        )


def _grasp_perception_with_describe_vlm():
    from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception

    vlm = _FakeDescribeVLM()
    p = Go2GraspPerception(_FrameBase(), describe_vlm=vlm)
    return p, vlm


def test_grasp_perception_caption_routes_to_describe_scene():
    """caption() renders a frame and returns the describe_scene text (no GT)."""
    p, vlm = _grasp_perception_with_describe_vlm()
    cap = p.caption(length="long")
    assert isinstance(cap, str) and cap
    assert vlm.calls == 1
    assert "green bottle" in cap
    assert "courtyard" in cap


def test_grasp_perception_visual_query_routes_to_describe_scene():
    """visual_query() answers via the SAME describe_scene seam (never crashes)."""
    p, vlm = _grasp_perception_with_describe_vlm()
    ans = p.visual_query("what do you see?")
    assert isinstance(ans, str) and ans
    assert vlm.calls == 1
    assert "bottle" in ans


def test_grasp_perception_satisfies_perception_protocol_describe_methods():
    """The describe skill's contract: caption + visual_query are callable."""
    p, _ = _grasp_perception_with_describe_vlm()
    assert callable(getattr(p, "caption", None))
    assert callable(getattr(p, "visual_query", None))
