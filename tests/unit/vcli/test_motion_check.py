# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the motion cross-check makes the pose-delta the AUTHORITY and vision a flag-only
narrator (ADR-002 Stage 3). The hard channel decides 'did it move'; vision can only agree or raise
a disagreement — it is never the sole motion judge.
"""
from __future__ import annotations

from vector_os_nano.acceptance import motion_check as mc


def test_path_length_planar():
    assert mc.path_length([{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]) == 2.0
    assert mc.path_length([(0, 0), (3, 4)]) == 5.0
    assert mc.path_length([{"x": 0, "y": 0}]) == 0.0


def test_hard_moved_plus_vision_pass_agree():
    v = mc.cross_check([{"x": 0, "y": 0}, {"x": 1, "y": 0}], "PASS")
    assert v.hard_moved and v.agree and not v.disagreement


def test_hard_moved_plus_vision_fail_is_disagreement():
    # moved per GT pose-delta, but vision says NOT locomoted -> slide/teleport -> flag
    v = mc.cross_check([{"x": 0, "y": 0}, {"x": 1, "y": 0}], "FAIL")
    assert v.hard_moved and v.disagreement


def test_hard_static_plus_vision_pass_is_disagreement():
    # vision claims locomotion but the pose-delta is static -> hallucination / render glitch -> flag
    v = mc.cross_check([{"x": 0, "y": 0}, {"x": 0.001, "y": 0}], "PASS")
    assert (not v.hard_moved) and v.disagreement


def test_hard_static_plus_vision_fail_agree():
    v = mc.cross_check([{"x": 0, "y": 0}, {"x": 0.001, "y": 0}], "FAIL")
    assert (not v.hard_moved) and not v.disagreement


def test_vision_unavailable_no_disagreement_hard_stands_alone():
    v = mc.cross_check([{"x": 0, "y": 0}, {"x": 1, "y": 0}], None)
    assert v.hard_moved and not v.disagreement


def test_vision_abstain_on_moving_robot_is_disagreement():
    # couldn't confirm plausible motion on a robot the pose-delta says moved -> fail-closed flag
    v = mc.cross_check([{"x": 0, "y": 0}, {"x": 1, "y": 0}], "ABSTAIN")
    assert v.disagreement
