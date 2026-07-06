# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the AcceptanceGate is DOWNGRADE-ONLY and disagreement-as-product (ADR-002).

Vision can FAIL/flag a green but can NEVER turn a GT fail into an ACCEPT. Oracle-vs-vision
disagreement on a GT-pass routes to red-team and blocks the headline.
"""
from __future__ import annotations

import pytest

from zeno.acceptance import gate


def test_gt_pass_vision_pass_accepts():
    d = gate.decide(True, "PASS")
    assert d.decision == gate.ACCEPT
    assert not d.disagreement and not d.needs_red_team and not d.block_headline


def test_gt_pass_vision_fail_is_red_flag():
    d = gate.decide(True, "FAIL")
    assert d.decision == gate.RED_FLAG
    assert d.disagreement and d.needs_red_team and d.block_headline


def test_gt_pass_vision_abstain_is_red_flag_fail_closed():
    d = gate.decide(True, "ABSTAIN")
    assert d.decision == gate.RED_FLAG
    assert d.needs_red_team and d.block_headline


def test_gt_pass_vision_unavailable_accepts_with_warning():
    d = gate.decide(True, None)
    assert d.decision == gate.ACCEPT_WITH_WARNING
    assert not d.block_headline


@pytest.mark.parametrize("vision", ["PASS", "FAIL", "ABSTAIN", None])
def test_gt_fail_always_rejects_vision_never_rescues(vision):
    """The downgrade-only invariant: a GT fail is REJECT for EVERY vision value, including PASS."""
    d = gate.decide(False, vision)
    assert d.decision == gate.REJECT
    assert d.block_headline


@pytest.mark.parametrize("vision", ["PASS", "FAIL", "ABSTAIN", None])
def test_gt_fail_is_never_an_oracle_vs_vision_disagreement(vision):
    """A GT fail is NOT a disagreement for ANY vision value — the visual rubric is ORTHOGONAL to
    task success (upright/floating, rendered/black, body-intact, workspace-in-frame), so a vision
    PASS on a failed turn never *claims* success and cannot contradict the GT fail. The disagreement
    that matters is the inverse (GT pass + vision FAIL). Flagging GT-fail+vision-PASS would red-team
    every ordinary failed-but-rendered trial — noise, not the D91-D95 false-green signal."""
    d = gate.decide(False, vision)
    assert not d.disagreement and not d.needs_red_team


def test_vision_pass_can_never_produce_accept_when_gt_fails():
    """No code path lets a vision PASS upgrade a GT fail to ACCEPT/ACCEPT_WITH_WARNING."""
    for vision in ("PASS", "FAIL", "ABSTAIN", None):
        assert gate.decide(False, vision).decision == gate.REJECT
