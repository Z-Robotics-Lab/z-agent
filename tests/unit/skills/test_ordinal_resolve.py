# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R194 — ORDINAL+CATEGORY reference resolution over perceived detections.

An ordinal reference ("最左边的瓶子" / "the leftmost bottle") cannot be resolved from the
scene NAME catalog alone (names carry no position) nor by the VLM bbox route reliably:
R192 grounded 把最左边的瓶子 -> green (correct) but R193 re-ran the IDENTICAL utterance and
grasped the red CAN — the leftmost OBJECT (y=3.22) with the 瓶子/bottle CATEGORY filter
DROPPED (acceptance.jsonl R192 refuted / R193 adopted-miss).

This resolver grounds the ordinal DETERMINISTICALLY: parse the ordinal + the category noun,
FILTER the perceived detections to that category, sort by horizontal image position, and pick
the ordinal extreme. Convention: ``cx`` is the bbox horizontal centre in image pixels — smaller
cx is further LEFT. Pure function — no sim, no model, no ground-truth pose; it only chooses
WHICH detection to grasp, so the verify oracle stays untouched.
"""
from __future__ import annotations

from vector_os_nano.perception.depth_projection import mujoco_intrinsics
from vector_os_nano.skills.perception_grasp import (
    _ordinal_detections_from_catalog,
    _parse_ordinal,
    _resolve_ordinal_target,
    _resolve_ordinal_via_catalog,
)


def _det(label: str, cx: float) -> dict:
    return {"label": label, "cx": cx}


# ILLUSTRATIVE image-cx values (smaller cx = further left in the image) — NOT the real scene.
# These test the resolver's CONTRACT (category filter + min/max-cx pick), independent of the
# world frame. The real scene's world->image sign (green at world y=3.00 is the leftmost BOTTLE,
# blue y=2.78 the rightmost) is a WIRING concern proven only when this is wired + sim-run (E30).
_DETS = [_det("pickable_bottle_blue", 100.0),
         _det("pickable_bottle_green", 200.0),
         _det("pickable_can_red", 300.0)]


# ---- _parse_ordinal --------------------------------------------------------
def test_parse_ordinal_zh():
    assert _parse_ordinal("把最左边的瓶子拿过来") == "left"
    assert _parse_ordinal("最右边的蓝色瓶子") == "right"
    assert _parse_ordinal("中间的瓶子") == "middle"


def test_parse_ordinal_en():
    assert _parse_ordinal("the leftmost bottle") == "left"
    assert _parse_ordinal("grab the right-most can") == "right"
    assert _parse_ordinal("the middle bottle") == "middle"


def test_parse_ordinal_none_when_absent():
    assert _parse_ordinal("把红色的瓶子拿过来") is None
    assert _parse_ordinal("grab the green bottle") is None
    assert _parse_ordinal("") is None


# ---- _resolve_ordinal_target ----------------------------------------------
def test_leftmost_bottle_excludes_the_can():
    # THE R193 bug: 最左边的瓶子 must resolve to the leftmost BOTTLE (blue, cx=100),
    # NOT the leftmost OBJECT (the red can is not a bottle and must be filtered out).
    chosen = _resolve_ordinal_target("把最左边的瓶子拿过来", _DETS)
    assert chosen is not None and chosen["label"] == "pickable_bottle_blue"


def test_rightmost_bottle_is_green_not_the_can():
    # Among BOTTLES only, rightmost is green (cx=200); the can (cx=300) is filtered out.
    chosen = _resolve_ordinal_target("最右边的瓶子", _DETS)
    assert chosen is not None and chosen["label"] == "pickable_bottle_green"


def test_middle_of_three_same_category():
    dets = [_det("pickable_bottle_a", 10.0), _det("pickable_bottle_b", 20.0),
            _det("pickable_bottle_c", 30.0)]
    chosen = _resolve_ordinal_target("中间的瓶子", dets)
    assert chosen is not None and chosen["label"] == "pickable_bottle_b"


def test_ordinal_without_category_ranks_all_detections():
    # A deictic ordinal ("最左边的") with no category noun ranks over ALL detections.
    chosen = _resolve_ordinal_target("把最左边的拿过来", _DETS)
    assert chosen is not None and chosen["label"] == "pickable_bottle_blue"


def test_no_ordinal_returns_none():
    # No ordinal word -> not our job -> None (caller keeps existing behaviour).
    assert _resolve_ordinal_target("把红色的瓶子拿过来", _DETS) is None


def test_category_absent_returns_none():
    # Ordinal + a category that no detection matches -> cannot resolve -> None.
    assert _resolve_ordinal_target("最左边的杯子", _DETS) is None


def test_empty_detections_returns_none():
    assert _resolve_ordinal_target("最左边的瓶子", []) is None


def test_single_candidate_after_filter_resolves():
    dets = [_det("pickable_bottle_blue", 100.0), _det("pickable_can_red", 300.0)]
    chosen = _resolve_ordinal_target("最右边的瓶子", dets)
    assert chosen is not None and chosen["label"] == "pickable_bottle_blue"


# ---- R195 WIRING: catalog-projection supplies the real image columns ------
# A camera at the origin looking along +x with +z up. MuJoCo cam_xmat columns are
# (right, up, -forward); with forward=+x, up=+z the right axis is world -y, so an object
# at MORE POSITIVE world-y projects to a SMALLER cx (further LEFT). This is the exact sign
# the sim must exhibit for 最左边的瓶子 → green (world y=3.00) over blue (y=2.78): the
# larger-y bottle is the leftmost. The projection COMPUTES the sign from geometry.
_INTR = mujoco_intrinsics(320, 240, vfov_deg=42.0)
_CAM_XPOS = (0.0, 0.0, 0.0)
_CAM_XMAT = (0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0)  # right=-y, up=+z, -forward=-x
# collinear along y at x=2 in front of the camera (mirrors the real go2 room scene ordering)
_CATALOG = {
    "pickable_bottle_green": (2.0, 0.30, 0.32),   # larger y → LEFT
    "pickable_bottle_blue": (2.0, 0.10, 0.32),    # smaller y → RIGHT (of the two bottles)
    "pickable_can_red": (2.0, 0.50, 0.32),        # leftmost OBJECT, excluded by 瓶子
}


def test_catalog_projection_sign_larger_y_is_more_left():
    dets = _ordinal_detections_from_catalog(_CATALOG, _INTR, _CAM_XPOS, _CAM_XMAT)
    by = {d["label"]: d["cx"] for d in dets}
    # larger world-y ⇒ smaller cx (further left): red(0.50) < green(0.30) < blue(0.10) in cx
    assert by["pickable_can_red"] < by["pickable_bottle_green"] < by["pickable_bottle_blue"]


def test_catalog_projection_drops_object_behind_camera():
    behind = {"pickable_bottle_green": (-2.0, 0.0, 0.32)}  # behind the +x-looking camera
    dets = _ordinal_detections_from_catalog(behind, _INTR, _CAM_XPOS, _CAM_XMAT)
    assert dets == []


class _FakeArm:
    def get_object_positions(self):
        return dict(_CATALOG)


class _FakePerception:
    def get_intrinsics(self):
        return _INTR

    def get_camera_pose(self):
        return (_CAM_XPOS, _CAM_XMAT)


def test_wiring_leftmost_bottle_resolves_to_green_the_can_excluded():
    # THE E30 bug end-to-end: 把最左边的瓶子 must resolve to the leftmost BOTTLE (green),
    # NOT the leftmost OBJECT (the red can, which the VLM route wrongly grasped in R193).
    hit = _resolve_ordinal_via_catalog("把最左边的瓶子拿过来", _FakeArm(), _FakePerception())
    assert hit == ("green", "pickable_bottle_green")


def test_wiring_rightmost_bottle_resolves_to_blue():
    hit = _resolve_ordinal_via_catalog("最右边的瓶子", _FakeArm(), _FakePerception())
    assert hit == ("blue", "pickable_bottle_blue")


# ---- R299/E90 regression: the yellow bottle (added R211, world-y=3.11) is now the
# TRUE leftmost bottle, superseding the R209/R210 "SCENE_SWAP → leftmost=blue" expectation.
# Among the live 3-bottle set {green 2.78, blue 3.00, yellow 3.11}, larger world-y ⇒ smaller
# cx ⇒ more LEFT, so `最左边的瓶子` resolves to YELLOW — in BOTH baseline and swap (the swap
# moves only blue↔green; the extreme yellow is unmoved, so the swap no longer probes
# invariance). The skill-direct probe grasped yellow cleanly; the "regression" was a STALE BAR,
# not a grasp-execution fault. This test would have flagged the expected-blue when yellow landed.
_SCENE3 = {
    "pickable_bottle_green": (2.0, 0.30, 0.32),
    "pickable_bottle_blue": (2.0, 0.45, 0.32),
    "pickable_bottle_yellow": (2.0, 0.60, 0.32),  # largest y ⇒ true leftmost
}


class _Scene3Arm:
    def get_object_positions(self):
        return dict(_SCENE3)


def test_wiring_leftmost_is_yellow_not_blue_after_R211_scene_growth():
    hit = _resolve_ordinal_via_catalog("把最左边的瓶子拿过来", _Scene3Arm(), _FakePerception())
    assert hit is not None and hit[1] == "pickable_bottle_yellow"


def test_wiring_no_ordinal_returns_none():
    assert _resolve_ordinal_via_catalog("把绿色的瓶子拿过来", _FakeArm(), _FakePerception()) is None


def test_wiring_empty_catalog_returns_none():
    class _EmptyArm:
        def get_object_positions(self):
            return {}

    assert _resolve_ordinal_via_catalog("最左边的瓶子", _EmptyArm(), _FakePerception()) is None
