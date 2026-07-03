# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Deterministic describe<->look alias routing on go2 (R249 alias-collision fix).

R248 wired Go2GraspPerception.caption/visual_query -> describe_scene so the
generic DescribeSkill (context.perception) no longer dead-ends on go2.  But
describe NL did NOT reach that fixed path on the bare face: the go2 LookSkill
ALSO claimed the "describe" / "what do you see" aliases, so a go2 session (which
registers the default skills FIRST, then the go2 skills) had LookSkill overwrite
those two entries in the alias_map (dict last-writer-wins, core/skill.py) and the
deterministic router sent describe-intent to LookSkill.

Intent separation (the fix): look / 看 = survey-and-move (LookSkill); describe /
看到什么 = static scene description of what is currently in front of the camera
(the generic DescribeSkill, whose context.perception path R248 fixed).  LookSkill
no longer claims the describe aliases, so the deterministic alias_map resolves
describe-intent to the generic DescribeSkill on a real go2 skill set.

Pure registry test — no MuJoCo, no GPU, no network.
"""
from __future__ import annotations

from vector_os_nano.core.skill import SkillRegistry
from vector_os_nano.skills import get_default_skills
from vector_os_nano.skills.go2 import get_go2_skills


def _go2_registry() -> SkillRegistry:
    """Registry mirroring a real go2 session: default skills THEN go2 skills.

    This is the exact registration order core/agent.py + sim_tool.py produce:
    Agent.__init__ registers get_default_skills() (incl. the generic
    DescribeSkill), then SimStartTool._start_go2 registers get_go2_skills()
    (incl. LookSkill), so any alias claimed by both resolves to whichever
    registered LAST.
    """
    reg = SkillRegistry()
    for skill in get_default_skills():
        reg.register(skill)
    for skill in get_go2_skills():
        reg.register(skill)
    return reg


def test_describe_alias_routes_to_describe_skill_not_look() -> None:
    """Exact 'describe' resolves to the generic DescribeSkill, not go2 look."""
    reg = _go2_registry()
    match = reg.match("describe")
    assert match is not None, "'describe' must route to a skill"
    assert match.skill_name == "describe", (
        f"'describe' routed to {match.skill_name!r}; the go2 LookSkill must "
        "not shadow the generic DescribeSkill (R248 fix lives on describe)"
    )


def test_what_do_you_see_routes_to_describe_skill_not_look() -> None:
    """'what do you see' resolves to the generic DescribeSkill, not go2 look."""
    reg = _go2_registry()
    match = reg.match("what do you see")
    assert match is not None, "'what do you see' must route to a skill"
    assert match.skill_name == "describe", (
        f"'what do you see' routed to {match.skill_name!r}; must reach the "
        "generic DescribeSkill, not the go2 LookSkill"
    )


def test_kandaoshenme_prefix_routes_to_describe_skill() -> None:
    """'看到什么...' (longest-prefix) resolves to the generic DescribeSkill."""
    reg = _go2_registry()
    match = reg.match("看到什么？请描述一下你面前的场景")
    assert match is not None, "describe-intent Chinese NL must route to a skill"
    assert match.skill_name == "describe", (
        f"'看到什么...' routed to {match.skill_name!r}; the longest-prefix "
        "alias 看到什么 belongs to the generic DescribeSkill"
    )


def test_look_alias_still_routes_to_look_skill() -> None:
    """'look' / '看' still reach the go2 LookSkill (survey-and-move intent)."""
    reg = _go2_registry()
    for phrase, why in (("look", "English survey"), ("看", "Chinese survey")):
        match = reg.match(phrase)
        assert match is not None, f"{phrase!r} ({why}) must route to a skill"
        assert match.skill_name == "look", (
            f"{phrase!r} routed to {match.skill_name!r}; survey-and-move intent "
            "must stay on the go2 LookSkill"
        )
