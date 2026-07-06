# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Routing: bare-NL '抓前面的东西' must reach PerceptionGraspSkill.

PerceptionGraspSkill and PickTopDownSkill share the 抓/grab/grasp aliases. On the
bare-cli honest path the world model is empty, so the PERCEPTION grasp (which
finds the object itself) must win — guaranteed by registering it LAST (the alias
map is last-write-wins per alias). This pins that precedence.
"""
from __future__ import annotations

from zeno.core.skill import SkillRegistry
from zeno.skills.perception_grasp import PerceptionGraspSkill
from zeno.skills.pick_top_down import PickTopDownSkill


def _registry_in_sim_order() -> SkillRegistry:
    """Mirror sim_tool _start_go2: PickTopDown first, PerceptionGrasp LAST."""
    reg = SkillRegistry()
    reg.register(PickTopDownSkill())
    reg.register(PerceptionGraspSkill())
    return reg


def test_chinese_grasp_routes_to_perception():
    m = _registry_in_sim_order().match("抓前面的东西")
    assert m is not None
    assert m.skill_name == "perception_grasp"
    assert m.extracted_arg == "前面的东西"


def test_english_grab_routes_to_perception():
    m = _registry_in_sim_order().match("grab the banana")
    assert m is not None
    assert m.skill_name == "perception_grasp"


def test_perception_grasp_has_holding_object_verify_hint():
    schemas = {s["name"]: s for s in _registry_in_sim_order().to_schemas()}
    assert "perception_grasp" in schemas
    assert "holding_object" in schemas["perception_grasp"]["verify_hint"]
