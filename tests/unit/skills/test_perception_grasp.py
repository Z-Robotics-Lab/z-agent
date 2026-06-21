# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""RED-4 — PerceptionGraspSkill flow, fully mocked (no GPU / GL / model / sim).

Proves the honest perception-driven grasp end-to-end at the skill level:
  - the 3D grasp point is computed from the PERCEIVED depth + mask (via the pure
    grasp_point_from_rgbd), NOT from a ground-truth object pose — the world model
    is EMPTY and the arm exposes no get_object_positions, so any GT shortcut fails;
  - the proven PickTopDownSkill motion is REUSED via its params['target_xyz'] seam
    (no re-implemented motion);
  - each perception failure FAILS LOUD with a specific diagnosis, never a fabricated
    point or a silent GT fallback.
"""
from __future__ import annotations

import numpy as np
import pytest

from vector_os_nano.core.skill import SkillContext
from vector_os_nano.core.types import Detection
from vector_os_nano.core.world_model import WorldModel
from vector_os_nano.perception.depth_projection import mujoco_intrinsics
from vector_os_nano.perception.grasp_point import grasp_point_from_rgbd
from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill

_W, _H = 64, 48
_INTR = mujoco_intrinsics(_W, _H, vfov_deg=42.0)
# A camera pose that puts a 1 m-forward point at a sensible, reachable world spot.
_CAM_XPOS = np.array([0.5, 0.0, 0.5], dtype=np.float64)
_CAM_XMAT = np.eye(3, dtype=np.float64).reshape(9)


def _depth_mask(depth_val: float = 1.0):
    depth = np.zeros((_H, _W), dtype=np.float32)
    color = np.zeros((_H, _W, 3), dtype=np.uint8)
    mask = np.zeros((_H, _W), dtype=np.uint8)
    for v in range(21, 28):
        for u in range(29, 36):
            depth[v, u] = depth_val
            mask[v, u] = 1
    return depth, color, mask


class FakePerception:
    """Mock backend with the exact surface PerceptionGraspSkill consumes."""

    def __init__(self, *, detections=None, mask=None, depth=None, color=None):
        d, c, m = _depth_mask()
        self._depth = depth if depth is not None else d
        self._color = color if color is not None else c
        self._mask = mask if mask is not None else m
        self._dets = detections if detections is not None else [
            Detection(label="banana", bbox=(29.0, 21.0, 35.0, 27.0), confidence=0.9)
        ]
        self.calls: list[str] = []

    def get_color_frame(self):
        self.calls.append("color")
        return self._color

    def get_depth_frame(self):
        self.calls.append("depth")
        return self._depth

    def get_intrinsics(self):
        return _INTR

    def get_camera_pose(self):
        return _CAM_XPOS, _CAM_XMAT

    def detect(self, query):
        self.calls.append(f"detect:{query}")
        return list(self._dets)

    def segment(self, image, bbox):
        self.calls.append("segment")
        return self._mask


class FakeArm:
    name = "piper"

    def __init__(self):
        self.ik_calls: list[tuple] = []
        self.move_calls = 0

    def ik_top_down(self, xyz, current_joints=None):
        self.ik_calls.append(tuple(float(v) for v in xyz))
        return [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

    def move_joints(self, q, duration=1.0):
        self.move_calls += 1
        return True

    def fk(self, q):
        return ([0.0, 0.0, 0.0], np.eye(3))


class FakeGripper:
    def __init__(self, holding_after_close=True):
        self._closed = False
        self._holding_after = holding_after_close

    def open(self):
        self._closed = False
        return True

    def close(self):
        self._closed = True
        return True

    def is_holding(self):
        return self._closed and self._holding_after


def _ctx(perception, *, arm=None, gripper=None, wm=None):
    return SkillContext(
        arm=arm if arm is not None else FakeArm(),
        gripper=gripper if gripper is not None else FakeGripper(),
        world_model=wm if wm is not None else WorldModel(),  # EMPTY but not None
        perception=perception,
        config={},
    )


def test_grasp_point_comes_from_perceived_depth_not_ground_truth():
    """The delegated target_xyz must equal grasp_point_from_rgbd(perceived inputs).

    World model is EMPTY and the arm has no get_object_positions — there is NO GT
    to read, so a passing run can only be using the perceived point.
    """
    perc = FakePerception()
    arm = FakeArm()
    skill = PerceptionGraspSkill()
    res = skill.execute({"query": "banana"}, _ctx(perc, arm=arm))

    assert res.success is True
    rd = res.result_data
    assert rd["perceived"] is True
    assert rd["detection_label"] == "banana"

    depth, color, mask = perc._depth, perc._color, perc._mask
    expected = grasp_point_from_rgbd(depth, color, mask, _INTR, _CAM_XPOS, _CAM_XMAT)
    assert expected is not None
    assert rd["grasp_world"] == pytest.approx([expected.x, expected.y, expected.z], abs=1e-6)

    # Motion was DELEGATED (ik solved) and aimed at the perceived x,y.
    assert arm.ik_calls, "PickTopDownSkill motion was not reused (no IK call)"
    assert arm.ik_calls[0][0] == pytest.approx(expected.x, abs=1e-6)
    assert arm.ik_calls[0][1] == pytest.approx(expected.y, abs=1e-6)


def test_pipeline_order_detect_then_segment():
    perc = FakePerception()
    PerceptionGraspSkill().execute({"query": "banana"}, _ctx(perc))
    di = next(i for i, c in enumerate(perc.calls) if c.startswith("detect"))
    si = perc.calls.index("segment")
    assert di < si, "must VLM-detect before EdgeTAM-segment"


def test_no_detections_fails_loud():
    perc = FakePerception(detections=[])
    res = PerceptionGraspSkill().execute({"query": "ghost"}, _ctx(perc))
    assert res.success is False
    assert res.result_data["diagnosis"] == "no_detections"


def test_empty_mask_fails_segmentation():
    perc = FakePerception(mask=np.zeros((_H, _W), dtype=np.uint8))
    res = PerceptionGraspSkill().execute({"query": "banana"}, _ctx(perc))
    assert res.success is False
    assert res.result_data["diagnosis"] == "segmentation_failed"


def test_all_zero_depth_fails_no_depth_points():
    perc = FakePerception(depth=np.zeros((_H, _W), dtype=np.float32))
    res = PerceptionGraspSkill().execute({"query": "banana"}, _ctx(perc))
    assert res.success is False
    assert res.result_data["diagnosis"] == "no_depth_points"


def test_no_perception_fails_loud():
    res = PerceptionGraspSkill().execute({"query": "banana"}, _ctx(None))
    assert res.success is False
    assert res.result_data["diagnosis"] in ("no_perception", "no_camera")


def test_ik_unreachable_surfaced():
    class DeadArm(FakeArm):
        def ik_top_down(self, xyz, current_joints=None):
            return None

    perc = FakePerception()
    res = PerceptionGraspSkill().execute({"query": "banana"}, _ctx(perc, arm=DeadArm()))
    assert res.success is False
    assert res.result_data["diagnosis"] == "ik_unreachable"


class FrontPerception(FakePerception):
    """Adds the deictic front-object resolver surface."""

    def front_object_mask(self, rgb=None, depth=None, *, color=None):
        self.calls.append(f"front:{color}" if color else "front")
        return self._mask


def test_deictic_query_uses_front_object_not_vlm():
    """'抓前面的东西' must resolve via the front-object mask, NOT a VLM name."""
    perc = FrontPerception()
    arm = FakeArm()
    res = PerceptionGraspSkill().execute({"query": "前面的东西"}, _ctx(perc, arm=arm))
    assert res.success is True
    assert res.result_data["perceived"] is True
    assert "front" in perc.calls
    assert not any(c.startswith("detect") for c in perc.calls)  # no VLM naming
    expected = grasp_point_from_rgbd(perc._depth, perc._color, perc._mask,
                                     _INTR, _CAM_XPOS, _CAM_XMAT)
    assert res.result_data["grasp_world"] == pytest.approx(
        [expected.x, expected.y, expected.z], abs=1e-6)


def test_deictic_nothing_in_front_fails_loud():
    perc = FrontPerception(mask=np.zeros((_H, _W), dtype=np.uint8))
    res = PerceptionGraspSkill().execute({"query": "前面的东西"}, _ctx(perc))
    assert res.success is False
    assert res.result_data["diagnosis"] == "no_detections"


def test_named_query_empty_vlm_falls_back_to_front():
    """A named query the VLM misses falls back to the front object (honest)."""
    perc = FrontPerception(detections=[])
    res = PerceptionGraspSkill().execute({"query": "banana"}, _ctx(perc))
    assert res.success is True
    assert "front" in perc.calls


def test_color_query_threads_color_and_maps_verify_label():
    """ATTRIBUTE grasp (D47): '抓红色的东西' resolves via front_object_mask(color='red')
    and the verify LABEL maps to the colour's scene name (pickable_can_red)."""
    perc = FrontPerception()
    arm = FakeArm()
    res = PerceptionGraspSkill().execute({"query": "抓红色的东西"}, _ctx(perc, arm=arm))
    assert res.success is True
    assert "front:red" in perc.calls               # colour threaded to the resolver
    assert not any(c.startswith("detect") for c in perc.calls)  # no VLM naming
    assert res.result_data["detection_label"] == "pickable_can_red"  # verify LABEL


def test_color_query_blue_maps_to_blue_bottle():
    perc = FrontPerception()
    res = PerceptionGraspSkill().execute({"query": "抓蓝色的"}, _ctx(perc, arm=FakeArm()))
    assert res.success is True
    assert "front:blue" in perc.calls
    assert res.result_data["detection_label"] == "pickable_bottle_blue"


def test_deictic_no_color_keeps_query_label():
    """A plain deictic query parses no colour: front_object_mask(color=None), label unchanged."""
    perc = FrontPerception()
    res = PerceptionGraspSkill().execute({"query": "前面的东西"}, _ctx(perc, arm=FakeArm()))
    assert res.success is True
    assert "front" in perc.calls and "front:red" not in perc.calls
    assert res.result_data["detection_label"] == "前面的东西"


class _FakeBase:
    """A go2 stand-in: walk(vx,..,duration) advances x by vx*duration*0.7 (gait
    under-shoot); get_position returns the live pose. Faces +x (toward the table)."""
    def __init__(self, x=10.0, y=3.0):
        self._x, self._y = x, y
        self.walks = 0
    def get_heading(self):
        return 0.0  # faces +x toward the table
    def get_position(self):
        return [self._x, self._y, 0.3]
    def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=1.0):
        self.walks += 1
        self._x += vx * duration * 0.7  # under-shoot, like the real gait
        return True


def test_approach_object_converges_with_position_feedback():
    """The scripted forward-walk approach closes the gap to within reach via feedback
    despite gait under-shoot (D27: non-gated, the base walk primitive not FAR)."""
    from vector_os_nano.skills.perception_grasp import _approach_object, _GRASP_REACH_M
    base = _FakeBase(x=10.0, y=3.0)
    ok = _approach_object(base, (11.0, 3.0))  # object 1.0m ahead, out of ~0.34m reach
    assert ok
    assert base.walks >= 1                       # it actually walked
    assert (11.0 - base.get_position()[0]) <= _GRASP_REACH_M + 0.15  # within reach now


def test_approach_noop_when_already_in_reach():
    from vector_os_nano.skills.perception_grasp import _approach_object
    base = _FakeBase(x=10.97, y=3.0)  # already 0.03m from the object -> within reach_m=0.05
    ok = _approach_object(base, (11.0, 3.0))
    assert ok
    assert base.walks == 0           # no walk needed


def test_no_arm_fails_loud():
    perc = FakePerception()
    ctx = SkillContext(arm=None, gripper=FakeGripper(), world_model=WorldModel(),
                       perception=perc, config={})
    res = PerceptionGraspSkill().execute({"query": "banana"}, ctx)
    assert res.success is False
    assert res.result_data["diagnosis"] == "no_arm"
