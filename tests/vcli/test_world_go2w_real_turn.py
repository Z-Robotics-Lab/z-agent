# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real turn skill + turned() verify — in-place rotation (v2, RED first).

Field trace 2026-07-10 evening: '左转90度' — the world had NO rotation
capability at all (not a skill, not a strategy, not a verify oracle). Pinned
here:

* RealTurnSkill ('turn'): direction(left|right) + degrees (default 90;
  掉头=180) → signed delta → driver.rotate(delta, yaw_rate=0.5); estop-latch
  fail-fast like every other motion skill; verify hint names turned(min_deg).
* turned(min_deg=30) verify predicate: captures the start heading on FIRST
  call (the moved() pattern), True once |wrapped heading delta| >= min_deg —
  odometry yaw the actor cannot author (Inv-1), fail-safe False.
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
    """Fake driver: records rotate() calls; optionally actually 'turns'."""

    def __init__(self, latched: bool = False, turns: bool = True,
                 yaw: float = 0.0) -> None:
        self.estop_latched = latched
        self._yaw = yaw
        self._turns = turns
        self.calls: list[tuple[float, float]] = []

    def get_heading(self) -> float:
        return self._yaw

    def rotate(self, delta_yaw_rad: float, yaw_rate: float = 0.5) -> bool:
        self.calls.append((float(delta_yaw_rad), float(yaw_rate)))
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
# turned() verify predicate — moved() pattern on odometry yaw, wrap-aware
# ---------------------------------------------------------------------------


def _turned(yaw: float = 0.0):
    from zeno.vcli.worlds.go2w_real_verify import make_turned

    agent = SimpleNamespace(_base=_TurnFakeHW(yaw=yaw))
    return make_turned(agent), agent._base


def test_turned_captures_start_on_first_call_then_grades():
    turned, hw = _turned(yaw=0.0)
    assert turned(30) is False  # first call captures the start heading
    hw._yaw = math.radians(100.0)
    assert turned(90) is True
    assert turned(120) is False


def test_turned_default_min_deg_is_30():
    turned, hw = _turned(yaw=0.0)
    assert turned() is False
    hw._yaw = math.radians(31.0)
    assert turned() is True


def test_turned_handles_wrap_around_across_pi():
    """+pi-0.1 → -pi+0.1 is an 0.2 rad (~11.5°) turn, NOT a ~348° one."""
    turned, hw = _turned(yaw=math.pi - 0.1)
    assert turned(5) is False  # capture
    hw._yaw = -math.pi + 0.1
    assert turned(30) is False, "wrap-around must not inflate the delta"
    assert turned(10) is True


def test_turned_is_fail_safe():
    from zeno.vcli.worlds.go2w_real_verify import make_turned

    assert make_turned(None)(30) is False
    assert make_turned(SimpleNamespace(_base=None))(30) is False


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
