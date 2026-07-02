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

from vector_os_nano.skills.perception_grasp import _parse_ordinal, _resolve_ordinal_target


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
