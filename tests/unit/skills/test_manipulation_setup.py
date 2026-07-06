# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit tests for the single-source go2+arm manipulation wiring helper.

``register_manipulation_skills`` is the ONE place both go2+arm launch paths
(the in-process ``--sim-go2`` flag path in ``cli.py`` and the ROS2 NL path in
``sim_tool``) register the Piper manipulation skill set + perception-grasp, so the
two can never drift (Rule 3 single-source / Rule 11 no per-embodiment forks). These
tests pin the contract WITHOUT a real sim (Go2GraspPerception construction is lazy).
"""
from __future__ import annotations

import pytest

from zeno.core.agent import Agent
from zeno.skills.manipulation_setup import register_manipulation_skills


class _StubBase:
    """A no-op base — Go2GraspPerception only stores it (construction is lazy)."""


def _agent() -> Agent:
    # arm/gripper truthy stubs so the helper treats the arm as present.
    return Agent(base=_StubBase(), arm=object(), gripper=object(), config={})


def test_registers_perception_grasp_and_manip_skills() -> None:
    agent = _agent()
    ok = register_manipulation_skills(agent, _StubBase())
    assert ok is True
    names = set(agent._skill_registry.list_skills())
    for expected in (
        "perception_grasp", "pick_top_down", "place_top_down",
        "mobile_pick", "mobile_place",
    ):
        assert expected in names, f"{expected} not registered: {names}"


def test_sets_grasp_perception() -> None:
    agent = _agent()
    register_manipulation_skills(agent, _StubBase())
    from zeno.perception.go2_grasp_perception import Go2GraspPerception
    assert isinstance(agent._perception, Go2GraspPerception)


def test_perception_grasp_wins_grab_alias() -> None:
    """perception_grasp must register LAST so it wins the shared 抓/grab aliases."""
    agent = _agent()
    register_manipulation_skills(agent, _StubBase())
    m = agent._skill_registry.match("抓绿色的瓶子")
    assert m is not None
    assert m.skill_name == "perception_grasp", m.skill_name


def test_env_disable_skips_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_ENABLE_MANIPULATION", "0")
    agent = _agent()
    ok = register_manipulation_skills(agent, _StubBase())
    assert ok is False
    assert "perception_grasp" not in set(agent._skill_registry.list_skills())
