# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real turn skill + turned() verify — in-place rotation (v2, RED first).

Field trace 2026-07-10 evening: '左转90度' — the world had NO rotation
capability at all (not a skill, not a strategy, not a verify oracle). Pinned
here:

* RealTurnSkill ('turn'): direction(left|right) + degrees (default 90;
  掉头=180) → signed delta → driver.rotate(delta, yaw_rate=0.5); estop-latch
  fail-fast like every other motion skill; verify hint names turned(min_deg).
* turned(min_deg=30) verify predicate: grades the wrapped |heading delta|
  between live odometry yaw and the DRIVER's rotate_anchor_yaw (sampled by
  rotate() at command start) — call-order independent, True on the FIRST
  check after a completed turn, fail-safe False. Field trace 2026-07-13:
  the original first-verify-call origin capture sampled the POST-turn
  heading (verify runs AFTER the skill), graded False, and the model re-ran
  the turn — 90° of physical rotation for a 45° ask.
* Wiring at the v2 extension markers: skill registered in the embodiment,
  turned in the verify namespace, turn_skill in the decompose vocab
  (strategies == strategy_descriptions set-equality holds).

Hermetic: fake driver, no ROS env, no LLM.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _redirect_oplog(tmp_path):
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "test_agent.log"))
    yield
    d.set_oplog_path(old)


class _TurnFakeHW:
    """Fake driver: records rotate() calls; optionally actually 'turns'.

    Mirrors the real driver contract: rotate() samples the odometry heading
    into ``rotate_anchor_yaw`` at command start (the turned() oracle anchor),
    even when the guard eats the commands (turns=False — anchor set, yaw
    unchanged, so turned() honestly grades False)."""

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


def _skill():
    from zeno.vcli.worlds.go2w_real_turn_skills import RealTurnSkill

    return RealTurnSkill()


# ---------------------------------------------------------------------------
# Direction / degrees → signed delta (left = +yaw/CCW, right = -yaw/CW)
# ---------------------------------------------------------------------------


def test_turn_left_defaults_to_90_degrees():
    hw = _TurnFakeHW()
    result = _skill().execute({"direction": "left"}, _ctx(base=hw))
    assert result.success, result.error_message
    delta, rate = hw.calls[0]
    assert delta == pytest.approx(math.pi / 2)
    assert rate == pytest.approx(0.5)


def test_turn_right_with_degrees_param_is_negative_delta():
    hw = _TurnFakeHW()
    result = _skill().execute({"direction": "right", "degrees": 45}, _ctx(base=hw))
    assert result.success
    assert hw.calls[0][0] == pytest.approx(-math.pi / 4)


def test_turn_parses_chinese_instruction_left_90():
    hw = _TurnFakeHW()
    result = _skill().execute({}, _ctx(base=hw, instruction="左转90度"))
    assert result.success
    assert hw.calls[0][0] == pytest.approx(math.pi / 2)


def test_turn_parses_chinese_instruction_right_45():
    hw = _TurnFakeHW()
    result = _skill().execute({}, _ctx(base=hw, instruction="右转45度"))
    assert result.success
    assert hw.calls[0][0] == pytest.approx(-math.pi / 4)


def test_uturn_defaults_to_180_degrees():
    hw = _TurnFakeHW()
    result = _skill().execute({}, _ctx(base=hw, instruction="掉头"))
    assert result.success
    assert abs(hw.calls[0][0]) == pytest.approx(math.pi)


def test_turn_result_names_the_turned_verify_hint():
    hw = _TurnFakeHW()
    result = _skill().execute({"direction": "left", "degrees": 90}, _ctx(base=hw))
    assert "turned(" in str(result.result_data or {})


# ---------------------------------------------------------------------------
# Safety + honest failure
# ---------------------------------------------------------------------------


def test_turn_fails_fast_when_estop_latched():
    hw = _TurnFakeHW(latched=True)
    result = _skill().execute({"direction": "left"}, _ctx(base=hw))
    assert not result.success
    assert result.diagnosis_code == "estop_latched"
    assert "resume" in (result.error_message or "").lower()
    assert hw.calls == [], "fail fast — never command a latched guard"


def test_turn_without_base_fails_honestly():
    result = _skill().execute({"direction": "left"}, _ctx(base=None))
    assert not result.success
    assert result.diagnosis_code == "no_base"


@pytest.mark.parametrize("degrees", [0, -90, 361, float("nan")])
def test_turn_rejects_out_of_range_degrees(degrees):
    hw = _TurnFakeHW()
    result = _skill().execute({"degrees": degrees}, _ctx(base=hw))
    assert not result.success
    assert hw.calls == []


def test_turn_zero_rotation_hints_latched_guard():
    """rotate() ran but odometry saw ~no rotation → steer to resume_skill
    (the silent-latch failure mode, twin of _stalled_hint on navigate)."""
    hw = _TurnFakeHW(turns=False)
    result = _skill().execute({"direction": "left"}, _ctx(base=hw))
    assert not result.success
    assert "resume" in (result.error_message or "").lower()


# ---------------------------------------------------------------------------
# turned() verify predicate — driver-anchored (LAST rotate command), wrap-aware
#
# Field trace 2026-07-13, '左转45度' ran TWICE: verify runs AFTER the skill,
# so the first-verify-call origin capture sampled the POST-turn heading,
# graded False, the model threshold-shopped (turned(45)/(40)/(45.9), all
# False) and then RE-RAN the turn — 90° of physical rotation for a 45° ask.
# The oracle now anchors on rotate_anchor_yaw, which the DRIVER samples from
# odometry at command start: call-order independent, no per-call state.
# ---------------------------------------------------------------------------


def _turned(yaw: float = 0.0):
    from zeno.vcli.worlds.go2w_real_verify import make_turned

    agent = SimpleNamespace(_base=_TurnFakeHW(yaw=yaw))
    return make_turned(agent), agent._base


def test_turned_grades_true_on_first_check_after_completed_turn():
    """THE 2026-07-13 regression: one 45° turn, ONE verify call — True."""
    from zeno.vcli.worlds.go2w_real_verify import make_turned

    hw = _TurnFakeHW(yaw=0.0)
    result = _skill().execute({"direction": "left", "degrees": 45}, _ctx(base=hw))
    assert result.success, result.error_message
    turned = make_turned(SimpleNamespace(_base=hw))
    assert turned(27) is True, (
        "first verify call after a completed turn must grade True — grading "
        "False here is what made the model re-run the turn (double rotation)")


def test_turned_false_when_no_rotation_ever_commanded():
    turned, hw = _turned(yaw=0.0)
    assert turned(30) is False
    hw._yaw = math.radians(100.0)  # heading changed, but NOT via a turn command
    assert turned(30) is False, "no anchor -> False (fail-safe; no origin capture)"


def test_turned_is_stable_across_repeated_checks():
    """Threshold-shopping (the trace probed 45/40/45.9) must get consistent
    answers — the predicate holds no per-call state to corrupt."""
    turned, hw = _turned(yaw=0.0)
    hw.rotate(math.radians(45.0))
    assert turned(27) is True
    assert turned(46) is False
    assert turned(27) is True
    assert turned() is True  # default 30 <= 45


def test_turned_default_min_deg_is_30():
    turned, hw = _turned(yaw=0.0)
    hw.rotate(math.radians(31.0))
    assert turned() is True
    turned2, hw2 = _turned(yaw=0.0)
    hw2.rotate(math.radians(29.0))
    assert turned2() is False


def test_turned_measures_only_the_last_turn_command():
    """Each rotate() re-anchors: a second command grades on ITS OWN delta."""
    turned, hw = _turned(yaw=0.0)
    hw.rotate(math.radians(90.0))
    hw.rotate(math.radians(45.0))
    assert turned(60) is False, "only the LAST command's rotation counts"
    assert turned(40) is True


def test_turned_handles_wrap_around_across_pi():
    """An 0.2 rad (~11.5°) turn across +pi must NOT grade as ~348°."""
    turned, hw = _turned(yaw=math.pi - 0.1)
    hw.rotate(0.2)  # crosses +pi -> heading wraps to -pi+0.1
    assert turned(30) is False, "wrap-around must not inflate the delta"
    assert turned(10) is True


def test_turned_false_when_commands_eaten_by_latched_guard():
    """rotate() commanded but odometry never moved (silent guard latch):
    anchor is set, delta stays 0 -> honest False."""
    from zeno.vcli.worlds.go2w_real_verify import make_turned

    hw = _TurnFakeHW(turns=False)
    hw.rotate(math.radians(45.0))
    assert make_turned(SimpleNamespace(_base=hw))(27) is False


def test_turned_is_fail_safe():
    from zeno.vcli.worlds.go2w_real_verify import make_turned

    assert make_turned(None)(30) is False
    assert make_turned(SimpleNamespace(_base=None))(30) is False
    # A base without the anchor attribute (foreign/older driver) -> False.
    assert make_turned(SimpleNamespace(_base=object()))(30) is False


# ---------------------------------------------------------------------------
# Wiring — embodiment skill registry, verify namespace, decompose vocab
# ---------------------------------------------------------------------------


def _world():
    from zeno.vcli.worlds import resolve_world_named

    return resolve_world_named("go2w_real")


def test_turn_skill_registered_in_embodiment():
    emb = _world().build_embodiment()
    assert "turn" in set(emb._skill_registry.list_skills())


def test_verify_namespace_serves_turned():
    ns = _world().build_verify_namespace(SimpleNamespace(_base=_TurnFakeHW()))
    assert callable(ns.get("turned"))


def test_vocab_teaches_turn_skill_and_turned():
    vocab = _world().decompose_vocab()
    assert "turn_skill" in vocab.strategies
    assert "turn_skill" in vocab.strategy_descriptions
    assert "turned" in vocab.verify_functions
    assert "turned" in vocab.verify_fn_signatures
    assert "turn_skill" in vocab.strategy_params_help
    # set-equality invariant (pinned globally too, re-asserted here on purpose)
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)


def test_capability_md_documents_turning():
    from pathlib import Path

    import zeno.vcli.worlds.go2w_real as w

    text = Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")
    assert "turned(" in text, "capability card must teach the turned() oracle"
    assert "掉头" in text or "turn" in text.lower()
