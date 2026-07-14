# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""clear_goals — the operator's clean slate (CEO 2026-07-14).

Stale goals hide in four caches (in-flight drive, latched waypoint,
far_planner route goal, operator RViz record) and any survivor keeps
steering the robot (the home-ghost fight, field 2026-07-14 evening). Pins:
the skill sweeps ALL of them via driver.clear_all_goals + resets the course
intent; E-stop latch untouched; wired as a strategy. Hermetic.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


class _SweepFakeHW:
    def __init__(self) -> None:
        from zeno.vcli.worlds.go2w_real_course import CourseTracker

        self.estop_latched = True  # must stay latched — clear never releases
        self.calls: list[str] = []
        self.course_tracker = CourseTracker()
        self.course_tracker.ensure(0.5)

    def clear_all_goals(self) -> None:
        self.calls.append("clear_all_goals")

    def cancel_navigation(self) -> None:
        self.calls.append("cancel_navigation")


def _ctx(base):
    return SimpleNamespace(base=base, services={}, instruction="")


def _skill():
    from zeno.vcli.worlds.go2w_real_lifecycle import RealClearGoalsSkill

    return RealClearGoalsSkill()


def test_clear_goals_sweeps_via_driver_and_resets_course():
    hw = _SweepFakeHW()
    result = _skill().execute({}, _ctx(hw))
    assert result.success, result.error_message
    assert hw.calls == ["clear_all_goals"]
    assert hw.course_tracker.course_yaw is None, "course intent must reset"
    assert "清除" in str(result.result_data)


def test_clear_goals_never_touches_the_estop_latch():
    hw = _SweepFakeHW()
    _skill().execute({}, _ctx(hw))
    assert hw.estop_latched is True, "E-stop release stays an explicit action"


def test_clear_goals_falls_back_on_older_driver():
    hw = _SweepFakeHW()
    hw.clear_all_goals = None  # not callable -> fallback path
    result = _skill().execute({}, _ctx(hw))
    assert result.success
    assert "cancel_navigation" in hw.calls


def test_clear_goals_without_base_fails_honestly():
    result = _skill().execute({}, _ctx(None))
    assert not result.success
    assert result.diagnosis_code == "no_base"


def test_clear_goals_registered_and_taught():
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    emb = world.build_embodiment()
    assert "clear_goals" in set(emb._skill_registry.list_skills())
    vocab = world.decompose_vocab()
    assert "clear_goals_skill" in vocab.strategies
    assert set(vocab.strategy_descriptions) == set(vocab.strategies)
