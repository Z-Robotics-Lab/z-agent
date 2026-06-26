# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""AcceptanceGate — the ONLY bridge between the frozen GT verdict and the visual witness (ADR-002).

DOWNGRADE-ONLY: vision can FAIL/flag a green, NEVER create one. The GT oracle stays the sole
authority on success — a GT fail is REJECT no matter what vision says. Oracle-vs-vision DISAGREEMENT
is the product (it surfaces the D91-D95 stub/bypass class the symbolic oracle is blind to) and routes
to red-team while BLOCKING any "it works" headline.

This is a pure function over (gt_verified, vision_witness). It never touches ``evidence_passed`` /
``classify_step_evidence`` / the ``VECTOR_VERDICT`` sentinel — the vision result rides OUTSIDE the
deterministic gate.
"""
from __future__ import annotations

from dataclasses import dataclass

# Decisions
ACCEPT = "ACCEPT"                              # GT verified AND vision PASS
RED_FLAG = "RED_FLAG"                          # GT verified BUT vision FAIL/ABSTAIN -> disagreement
REJECT = "REJECT"                             # GT not verified -> reject regardless of vision
ACCEPT_WITH_WARNING = "ACCEPT_WITH_WARNING"    # GT verified, vision unavailable (coverage gap)

# Vision witness values (mirror vision_judge)
_PASS = "PASS"


@dataclass(frozen=True)
class AcceptanceDecision:
    decision: str
    gt_verified: bool
    vision_witness: str | None
    disagreement: bool
    needs_red_team: bool
    block_headline: bool
    reason: str


def decide(gt_verified: bool, vision_witness: str | None) -> AcceptanceDecision:
    """Combine the frozen GT verdict with the visual witness. Vision can only DOWNGRADE.

    Truth table:
      GT fail   + any vision           -> REJECT (vision never rescues; NOT a disagreement — the
                                          orthogonal rubric is silent on task success, see below)
      GT pass   + vision None          -> ACCEPT_WITH_WARNING (coverage gap)
      GT pass   + vision PASS          -> ACCEPT
      GT pass   + vision FAIL/ABSTAIN  -> RED_FLAG (disagreement -> red-team, block headline)
    """
    if not gt_verified:
        # GT-fail is REJECT regardless of vision, and it is NOT an oracle-vs-vision disagreement:
        # the visual rubric is ORTHOGONAL to task success (upright/floating, rendered/black,
        # body-intact, workspace-in-frame) — a vision PASS only says "the scene rendered and the
        # robot looks fine", it never claims the task succeeded, so it cannot contradict a GT fail.
        # The disagreement that matters is the INVERSE (GT pass + vision FAIL: "oracle says success
        # but the picture looks wrong"), handled below. Flagging GT-fail+vision-PASS here would
        # red-team every ordinary failed-but-rendered trial = noise, not signal.
        return AcceptanceDecision(
            decision=REJECT,
            gt_verified=False,
            vision_witness=vision_witness,
            disagreement=False,
            needs_red_team=False,
            block_headline=True,
            reason="GT oracle did not verify — vision can never rescue a fail",
        )
    if vision_witness is None:
        return AcceptanceDecision(
            decision=ACCEPT_WITH_WARNING,
            gt_verified=True,
            vision_witness=None,
            disagreement=False,
            needs_red_team=False,
            block_headline=False,
            reason="GT verified; visual witness unavailable (coverage gap logged)",
        )
    if vision_witness == _PASS:
        return AcceptanceDecision(
            decision=ACCEPT,
            gt_verified=True,
            vision_witness=_PASS,
            disagreement=False,
            needs_red_team=False,
            block_headline=False,
            reason="GT verified AND visual witness PASS",
        )
    return AcceptanceDecision(
        decision=RED_FLAG,
        gt_verified=True,
        vision_witness=vision_witness,
        disagreement=True,
        needs_red_team=True,
        block_headline=True,
        reason=f"oracle-vs-vision DISAGREEMENT (GT verified, vision {vision_witness}) — red-team before any headline",
    )
