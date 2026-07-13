# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real world-layer quick wins (v2, RED first).

Field traces 2026-07-13, bare-zeno REPL on the real Go2W:

1. TURN ALIAS PREFIXES + FAST-PATH ANGLE SAFETY. '往左转动30度' matched no
   alias prefix ('左转' exists; '往左转...' did not), so it took a full LLM
   hop. Worse: the engine's VGG fast path extracts generic params by NAME —
   it knows 'angle', not 'degrees'. The turn skill declared ONLY 'degrees',
   so a fast-pathed '左转45度' produced strategy_params without any angle and
   RealTurnSkill defaulted to 90° — a 45° ask turning 90° (a REAL hazard).
   Pinned: prefix aliases (往左转/向左转/往右转/向右转/原地转/原地左转/
   原地右转) + an 'angle' MIRROR entry in RealTurnSkill.parameters that the
   fast path can populate and _parse_degrees already reads.

2. HONEST REVERSE HINT. move_relative backward failing with ZERO displacement
   while NOT estop-latched today wrongly hinted resume/retry — the model
   burned a resume + 3 retries + invented a 掉头-detour. The nav stack's local
   planner is known to refuse reverse-driving; the honest hint names that and
   suggests 掉头+前进 (or reporting to the operator), NOT a resume goose-chase.

3. VOCAB. '后退1米' -> ONE move_relative step {direction: backward,
   distance: 1}, verify at(...) (semantics correct regardless of the
   nav-stack reverse-drive fix landing; the skill fails honestly).

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


class _TurnFakeHW:
    """Fake driver: records rotate() calls; optionally actually 'turns'."""

    def __init__(self, latched: bool = False, turns: bool = True,
                 yaw: float = 0.0) -> None:
        self.estop_latched = latched
        self.rotate_anchor_yaw: float | None = None
        self._yaw = yaw
        self._turns = turns
        self.calls: list[tuple[float, float]] = []

    def get_heading(self) -> float:
        return self._yaw

    def rotate(self, delta_yaw_rad: float, yaw_rate: float = 0.5) -> bool:
        self.calls.append((float(delta_yaw_rad), float(yaw_rate)))
        self.rotate_anchor_yaw = self._yaw
        if self._turns:
            h = self._yaw + float(delta_yaw_rad)
            self._yaw = math.atan2(math.sin(h), math.cos(h))
        return self._turns


def _ctx(base=None, instruction: str = ""):
    return SimpleNamespace(base=base, services={}, instruction=instruction)


def _turn_skill():
    from zeno.vcli.worlds.go2w_real_turn_skills import RealTurnSkill

    return RealTurnSkill()


# ---------------------------------------------------------------------------
# (1a) Turn alias PREFIXES — '往左转动30度' must prefix-match, not LLM-hop
# ---------------------------------------------------------------------------

_PREFIX_ALIASES = ("往左转", "向左转", "往右转", "向右转",
                   "原地转", "原地左转", "原地右转")


def test_turn_skill_declares_prefix_aliases():
    """Every '往左转...'-shaped utterance must PREFIX-match a turn alias so the
    router short-circuits to turn_skill instead of a full LLM decomposition."""
    aliases = set(getattr(_turn_skill(), "__skill_aliases__", []))
    for a in _PREFIX_ALIASES:
        assert a in aliases, f"missing turn prefix alias {a!r}"


# ---------------------------------------------------------------------------
# (1b) FAST-PATH ANGLE SAFETY — the 'angle' mirror stops a 45°-ask→90°-turn
# ---------------------------------------------------------------------------


def test_turn_parameters_expose_angle_mirror():
    """The engine fast path extracts generic params by NAME ('angle', not
    'degrees'). Without an 'angle' entry it silently drops the magnitude and
    the skill defaults to 90 — the 45°→90° hazard. The mirror closes it."""
    params = _turn_skill().parameters
    assert "angle" in params, (
        "RealTurnSkill.parameters must expose an 'angle' mirror so the VGG "
        "fast path (which knows 'angle', not 'degrees') can pass the magnitude")


def test_turn_angle_param_dict_turns_that_many_degrees():
    """{'direction':'left','angle':45} — exactly what the fast path builds —
    must rotate 45°, NOT the 90° default (the real hazard)."""
    hw = _TurnFakeHW()
    result = _turn_skill().execute({"direction": "left", "angle": 45}, _ctx(base=hw))
    assert result.success, result.error_message
    delta, _rate = hw.calls[0]
    assert delta == pytest.approx(math.radians(45)), (
        "angle=45 must turn 45°, not the 90° default — the fast-path hazard")


def test_turn_angle_param_right_is_negative_delta():
    hw = _TurnFakeHW()
    result = _turn_skill().execute({"direction": "right", "angle": 30}, _ctx(base=hw))
    assert result.success
    assert hw.calls[0][0] == pytest.approx(-math.radians(30))


# ---------------------------------------------------------------------------
# (2) HONEST REVERSE HINT — backward + zero displacement + NOT latched
# ---------------------------------------------------------------------------


def test_stalled_hint_backward_not_latched_names_reverse_drive_issue():
    """Direction=backward, ~0 displacement, NOT latched: the local planner is
    known to refuse reverse-driving. The hint must say so and suggest the
    掉头+前进 workaround — NOT send the model resume-hunting."""
    from zeno.vcli.worlds.go2w_real_diag import _stalled_hint

    hint = _stalled_hint((1.0, 1.0), (1.0, 1.0), direction="backward",
                         latched=False)
    low = hint.lower()
    assert "reverse" in low or "掉头" in hint, (
        "backward stall (unlatched) must name the reverse-drive refusal")
    assert "掉头" in hint and "前进" in hint, (
        "must suggest the 掉头+前进 workaround")
    assert "resume" not in low, (
        "unlatched reverse stall must NOT send the model on a resume goose-chase")


def test_stalled_hint_forward_zero_still_latched_hint():
    """Forward (or unknown direction) zero-displacement keeps the latch hint —
    the reverse-drive branch must be backward-specific, not a blanket change."""
    from zeno.vcli.worlds.go2w_real_diag import _stalled_hint

    hint = _stalled_hint((0.0, 0.0), (0.0, 0.0), direction="forward",
                         latched=False)
    assert "resume" in hint.lower(), "forward stall keeps the latch/resume hint"
    assert "掉头" not in hint


def test_stalled_hint_backward_but_latched_keeps_resume():
    """If the guard IS latched, resume is the correct fix even for backward —
    the reverse-drive hint only applies when NOT latched."""
    from zeno.vcli.worlds.go2w_real_diag import _stalled_hint

    hint = _stalled_hint((0.0, 0.0), (0.0, 0.0), direction="backward",
                         latched=True)
    assert "resume" in hint.lower()


def test_stalled_hint_backward_with_displacement_is_empty():
    """Real movement (displacement above the floor) => no stall hint at all,
    regardless of direction."""
    from zeno.vcli.worlds.go2w_real_diag import _stalled_hint

    assert _stalled_hint((0.0, 0.0), (2.0, 0.0), direction="backward",
                         latched=False) == ""


def test_stalled_hint_backward_default_args_backward_compatible():
    """Old 2-arg callers (RealNavigate — absolute nav, no direction) still get
    the latch hint; the new params are additive with defaults (Invariant 7)."""
    from zeno.vcli.worlds.go2w_real_diag import _stalled_hint

    hint = _stalled_hint((0.0, 0.0), (0.0, 0.0))
    assert "resume" in hint.lower()


def test_move_relative_backward_stall_emits_reverse_hint():
    """End-to-end: move_relative backward that doesn't move (unlatched) must
    surface the reverse-drive workaround in its error_message."""
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    class _StuckHW:
        estop_latched = False

        def get_position(self):
            return (0.0, 0.0)

        def get_heading(self):
            return 0.0

        def navigate_to(self, x, y, timeout=None):
            return False  # planner refuses reverse-driving -> no motion

    result = RealMoveRelativeSkill().execute(
        {"direction": "backward", "distance": 1.0}, _ctx(base=_StuckHW()))
    assert not result.success
    msg = (result.error_message or "")
    assert "掉头" in msg and "前进" in msg, (
        "backward stall must suggest 掉头+前进, not a resume goose-chase")
    assert "resume" not in msg.lower()


# ---------------------------------------------------------------------------
# (3) VOCAB — '后退1米' -> ONE move_relative step {backward, 1}, verify at(...)
# ---------------------------------------------------------------------------


def _examples() -> str:
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES

    return REAL_DECOMPOSE_EXAMPLES


def _segment(marker: str, span: int = 900) -> str:
    text = _examples()
    assert marker in text, f"few-shot {marker!r} missing from the vocab"
    after = text.split(marker, 1)[1]
    nxt = after.find("Task:")
    return after[: nxt if 0 <= nxt <= span else span]


def test_backward_fewshot_is_one_move_relative_step():
    seg = _segment('Task: "后退1米"')
    assert "move_relative_skill" in seg
    assert seg.count('"strategy"') == 1, "后退1米 is a single relative move"
    assert "bringup_skill" not in seg, "motion never needs bringup"


def test_backward_fewshot_params_backward_one_meter():
    seg = _segment('Task: "后退1米"')
    assert '"direction": "backward"' in seg
    assert '"distance": 1' in seg


def test_backward_fewshot_verifies_with_at():
    seg = _segment('Task: "后退1米"')
    assert "at(" in seg, "the backward move verifies its arrival with at(...)"


def test_examples_within_char_budget():
    assert len(_examples()) <= 6000, "REAL_DECOMPOSE_EXAMPLES over the ~6000 budget"
