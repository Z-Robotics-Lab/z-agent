# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""fetch_and_place composite skill — hermetic stage-executor suite.

Covers the stage chain (bringup-check → goto → approach → [gated] grasp → goto
basket → [gated] place): stage progression, FAIL-STOP with honest reporting, the
arm gate (default OFF → skip; ON → dry-run plan only, never CAN/piper), and the
whole-chain dry-run (ZERO sub-skill execute = zero ROS publishes). The verify
aggregation is checked to be a CONJUNCTION of EXISTING oracle expressions the
skill only PROPOSES (Inv-1: it never computes ``verified``).

Hermetic: injected fake sub-skills record every call and script SkillResults; no
ROS env, no network, no sim. Nothing here touches CAN / piper / any arm.
"""

from __future__ import annotations

from typing import Any

import pytest

from zeno.core.skill import SkillContext
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_fetch_skills import (
    ARM_ENABLE_ENV,
    RealFetchAndPlaceSkill,
    arm_enabled,
)


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class _FakeBase:
    """Minimal base — presence is all the composite's bringup-check needs."""

    def __init__(self) -> None:
        self.manip_active = False


class _FakeBridge:
    """Stand-in manip bridge: connected flag only (bringup-check reads it)."""

    def __init__(self, connected: bool = True) -> None:
        self.is_connected = connected

    def connect(self) -> None:
        self.is_connected = True


class _FakeSkill:
    """Records execute() calls and returns scripted SkillResults in order."""

    def __init__(self, results: list[SkillResult]) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        self.calls.append(dict(params or {}))
        return self._results.pop(0) if self._results else SkillResult(success=True)


def _ok_goto(name: str) -> SkillResult:
    # Real goto_place returns an odometry at() hint; the double mirrors the shape.
    return SkillResult(success=True, result_data={
        "verify_hint": f"at_place({name})", "name": name})


def _ctx(base: Any = None, bridge: Any = None) -> SkillContext:
    base = base if base is not None else _FakeBase()
    services = {"manip": bridge} if bridge is not None else {}
    if bridge is not None:
        base.manip_bridge = bridge  # driver-ride seam _manip_of also reads
    return SkillContext(bases={"go2w": base}, services=services)


def _skill(goto_results: list[SkillResult] | None = None,
           approach_result: SkillResult | None = None
           ) -> tuple[RealFetchAndPlaceSkill, _FakeSkill, _FakeSkill]:
    goto = _FakeSkill(goto_results or [])
    approach = _FakeSkill([approach_result] if approach_result is not None else [])
    return RealFetchAndPlaceSkill(goto=goto, approach=approach), goto, approach


# ---------------------------------------------------------------------------
# dry-run — the acceptance path: ZERO ROS publishes
# ---------------------------------------------------------------------------


def test_dry_run_issues_no_subskill_calls() -> None:
    skill, goto, approach = _skill()
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房",
                         "basket": "篮子", "dry_run": True}, _ctx(bridge=_FakeBridge()))
    assert res.success is True
    # The rehearsal must not execute ANY sub-skill — no nav goal, no manip task.
    assert goto.calls == []
    assert approach.calls == []
    assert res.result_data["dry_run"] is True
    # A rehearsal makes no physical claim → trivially-true verify (Inv-1 safe).
    assert res.result_data["verify_hint"] == "True"


def test_dry_run_plan_lists_every_stage_in_order() -> None:
    skill, _, _ = _skill()
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房",
                         "dry_run": True}, _ctx())
    keys = [s["stage"] for s in res.result_data["stages"]]
    assert keys == ["bringup_check", "goto_target", "approach",
                    "grasp", "goto_basket", "place"]


def test_dry_run_via_utterance_keyword() -> None:
    skill, goto, approach = _skill()
    res = skill.execute({"target": "水瓶", "_text": "去厨房拿水瓶(演练)"}, _ctx())
    assert res.result_data["dry_run"] is True
    assert goto.calls == [] and approach.calls == []


def test_dry_run_without_target_place_skips_goto_target() -> None:
    skill, _, _ = _skill()
    res = skill.execute({"target": "水瓶", "dry_run": True}, _ctx())
    keys = [s["stage"] for s in res.result_data["stages"]]
    assert "goto_target" not in keys
    assert keys[0] == "bringup_check" and keys[1] == "approach"


# ---------------------------------------------------------------------------
# real chain — stage progression + verify aggregation (arm gate OFF)
# ---------------------------------------------------------------------------


def test_full_chain_progresses_and_aggregates_verify(monkeypatch) -> None:
    monkeypatch.delenv(ARM_ENABLE_ENV, raising=False)
    skill, goto, approach = _skill(
        goto_results=[_ok_goto("公司厨房"), _ok_goto("篮子")],
        approach_result=SkillResult(success=True, result_data={
            "verify_hint": "approach_ready()"}))
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房",
                         "basket": "篮子"}, _ctx(bridge=_FakeBridge()))
    assert res.success is True
    # goto called twice (target place + basket), approach once.
    assert len(goto.calls) == 2 and len(approach.calls) == 1
    assert goto.calls[0]["name"] == "公司厨房"
    assert goto.calls[1]["name"] == "篮子"
    # Aggregate = conjunction of END-STATE-true oracles: approach latch + at(basket).
    assert res.result_data["verify_hint"] == "approach_ready() and at_place(篮子)"
    statuses = {s["stage"]: s["status"] for s in res.result_data["stages"]}
    assert statuses["goto_target"] == "ok"
    assert statuses["approach"] == "ok"
    assert statuses["goto_basket"] == "ok"


def test_arm_stages_skipped_when_gate_off(monkeypatch) -> None:
    monkeypatch.delenv(ARM_ENABLE_ENV, raising=False)
    assert arm_enabled() is False
    skill, _, _ = _skill(
        goto_results=[_ok_goto("公司厨房"), _ok_goto("篮子")],
        approach_result=SkillResult(success=True))
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房"},
                        _ctx(bridge=_FakeBridge()))
    statuses = {s["stage"]: s["status"] for s in res.result_data["stages"]}
    assert statuses["grasp"] == "skipped"
    assert statuses["place"] == "skipped"
    assert res.result_data["arm_enabled"] is False


def test_arm_stages_plan_only_when_gate_on(monkeypatch) -> None:
    monkeypatch.setenv(ARM_ENABLE_ENV, "1")
    assert arm_enabled() is True
    skill, _, _ = _skill(
        goto_results=[_ok_goto("公司厨房"), _ok_goto("篮子")],
        approach_result=SkillResult(success=True))
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房"},
                        _ctx(bridge=_FakeBridge()))
    statuses = {s["stage"]: s["status"] for s in res.result_data["stages"]}
    # Gate ON is still DRY-RUN plan only — never actuation.
    assert statuses["grasp"] == "planned(dry-run)"
    assert statuses["place"] == "planned(dry-run)"
    assert res.result_data["arm_enabled"] is True


# ---------------------------------------------------------------------------
# fail-stop — honest per-stage reporting, later stages do NOT run
# ---------------------------------------------------------------------------


def test_halt_at_approach_stops_the_chain() -> None:
    skill, goto, approach = _skill(
        goto_results=[_ok_goto("公司厨房"), _ok_goto("篮子")],
        approach_result=SkillResult(
            success=False, diagnosis_code="approach_timeout",
            error_message="approach did not reach the handoff"))
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房"},
                        _ctx(bridge=_FakeBridge()))
    assert res.success is False
    assert res.result_data["failed_stage"] == "approach"
    assert res.diagnosis_code == "approach_timeout"
    # FAIL-STOP: the basket goto must NOT have run (only the target-place goto did).
    assert len(goto.calls) == 1
    # No end-state reached → nothing for the spine to grade True.
    assert res.result_data["verify_hint"] == "False"
    assert "approach" in res.error_message


def test_halt_at_goto_target_never_reaches_approach() -> None:
    skill, goto, approach = _skill(
        goto_results=[SkillResult(success=False, diagnosis_code="unknown_place",
                                  error_message="无法解析地点")],
        approach_result=SkillResult(success=True))
    res = skill.execute({"target": "水瓶", "target_place": "不存在的地方"},
                        _ctx(bridge=_FakeBridge()))
    assert res.success is False
    assert res.result_data["failed_stage"] == "goto_target"
    assert approach.calls == []  # never reached the approach stage


def test_halt_at_bringup_check_when_bridge_absent() -> None:
    skill, goto, approach = _skill()
    # No manip bridge in the context → bringup-check fails closed.
    res = skill.execute({"target": "水瓶", "target_place": "公司厨房"},
                        _ctx(bridge=None))
    assert res.success is False
    assert res.result_data["failed_stage"] == "bringup_check"
    assert goto.calls == [] and approach.calls == []


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------


def test_missing_target_is_bad_params() -> None:
    skill, _, _ = _skill()
    res = skill.execute({"target_place": "公司厨房"}, _ctx())
    assert res.success is False
    assert res.diagnosis_code == "bad_params"


def test_registered_in_go2w_real_world() -> None:
    from zeno.vcli.worlds.go2w_real import Go2WRealEmbodiment

    emb = Go2WRealEmbodiment()
    assert "fetch_and_place" in emb._skill_registry.list_skills()
    match = emb._skill_registry.match("取放")
    assert match is not None and match.skill_name == "fetch_and_place"
