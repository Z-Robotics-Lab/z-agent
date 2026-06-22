# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R38 — NavigateSkill coordinate-goal path (unit, mocked base).

The producer's nav step for "去桌子那里" targets the table by COORDINATE, not a
named room (the SceneGraph has no "table" room). NavigateSkill must accept
``strategy_params={"x": ..., "y": ...}`` (or ``target=[x, y]``) and drive the base
via ``base.navigate_to(x, y)`` — the FAR planner path — WITHOUT requiring a
SceneGraph room. The existing named-room path is unchanged.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from vector_os_nano.core.skill import SkillContext
from vector_os_nano.core.world_model import WorldModel
from vector_os_nano.skills.navigate import NavigateSkill


def _ctx(arrived=True, pos=(10.75, 3.05, 0.35)):
    base = MagicMock()
    base.get_position.return_value = list(pos)
    base.get_heading.return_value = 0.0
    base.navigate_to = MagicMock(return_value=arrived)
    # No spatial_memory needed for a coordinate goal.
    return SkillContext(bases={"go2": base}, world_model=WorldModel(), services={})


def test_navigate_xy_drives_navigate_to_without_room():
    """{x, y} params -> base.navigate_to(x, y); no SceneGraph room required."""
    ctx = _ctx(arrived=True)
    res = NavigateSkill().execute({"x": 10.5, "y": 3.0}, ctx)
    assert res.success is True
    ctx.base.navigate_to.assert_called_once()
    args, kwargs = ctx.base.navigate_to.call_args
    assert float(args[0]) == 10.5
    assert float(args[1]) == 3.0
    assert res.result_data["target"] == [10.5, 3.0]
    assert res.result_data["mode"] == "proxy_coord"


def test_navigate_target_list_form():
    """target=[x, y] is accepted equivalently to {x, y}."""
    ctx = _ctx(arrived=True)
    res = NavigateSkill().execute({"target": [10.5, 3.0]}, ctx)
    assert res.success is True
    args, _ = ctx.base.navigate_to.call_args
    assert (float(args[0]), float(args[1])) == (10.5, 3.0)


def test_navigate_xy_no_base_fails_loud():
    ctx = SkillContext(world_model=WorldModel(), services={})
    res = NavigateSkill().execute({"x": 10.5, "y": 3.0}, ctx)
    assert res.success is False
    assert res.diagnosis_code == "no_base"


def test_navigate_xy_reports_arrival_even_when_far_returns_false():
    """FAR returning False (no arrival confirm) still reports honestly; the step
    success is the planner's verdict, and the actual position is surfaced so the
    at_position verify oracle (RAN) is the source of truth."""
    ctx = _ctx(arrived=False, pos=(12.0, 3.0, 0.35))
    res = NavigateSkill().execute({"x": 10.5, "y": 3.0}, ctx)
    # navigate_to was called and the position is reported regardless of verdict.
    ctx.base.navigate_to.assert_called_once()
    assert res.result_data["position"] == [12.0, 3.0]


def test_named_room_path_unchanged_when_no_coordinates():
    """With no x/y/target and no usable SceneGraph, the room path still runs
    (and fails loud about an unknown/unexplored room) — coordinate path is additive."""
    base = MagicMock()
    base.get_position.return_value = [10.0, 3.0, 0.35]
    base.navigate_to = MagicMock(return_value=True)
    ctx = SkillContext(bases={"go2": base}, world_model=WorldModel(), services={})
    res = NavigateSkill().execute({"room": "nonexistent_room"}, ctx)
    assert res.success is False
    # It did NOT take the coordinate path (no navigate_to call on a bare room name).
    base.navigate_to.assert_not_called()
