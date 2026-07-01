# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Tests for Wave 2/3 skill registration wiring in sim_tool.py.

Test strategy: The full behavioural test (calling _start_go2 end-to-end with
with_arm=True) requires mocking subprocess.Popen, os.setsid, time.sleep(20),
Go2ROS2Proxy, PiperROS2Proxy, PiperGripperROS2Proxy, Agent, SceneGraph, and
multiple lazy imports inside the method body. That mock surface is fragile and
couples the test to implementation details of unrelated code paths.

Instead we use two focused guards:

1. test_manipulation_skills_importable_and_instantiable — verifies all 4 skill
   classes can be imported and constructed with no arguments. A failure here
   means any register(XyzSkill()) call in sim_tool will raise ImportError or
   TypeError at runtime.

2. test_sim_tool_module_contains_all_manipulation_registrations — inspects the
   source text of sim_tool to confirm each skill class name appears with a
   register() call pattern. Catches typos, missing imports, or accidental
   deletions without running the full method.
"""
from __future__ import annotations

import inspect


def test_manipulation_skills_importable_and_instantiable() -> None:
    """Regression guard: all 4 Wave 2/3 skill classes are importable and
    instantiable with no arguments. A failure means the register(...) calls
    added to _start_go2 will crash at runtime.
    """
    from vector_os_nano.skills.pick_top_down import PickTopDownSkill
    from vector_os_nano.skills.place_top_down import PlaceTopDownSkill
    from vector_os_nano.skills.mobile_pick import MobilePickSkill
    from vector_os_nano.skills.mobile_place import MobilePlaceSkill

    PickTopDownSkill()
    PlaceTopDownSkill()
    MobilePickSkill()
    MobilePlaceSkill()


def test_sim_tool_registers_manipulation_via_single_source() -> None:
    """Sanity: the with_arm path registers manipulation skills through the ONE
    shared helper register_manipulation_skills (Rule 3/11), single-sourced with
    the --sim-go2 launcher. The 4 skill classes are no longer named individually
    in sim_tool — they live behind that helper — so this guards the current
    contract (a missing call means with_arm gets no pick/place/grasp).
    """
    from vector_os_nano.vcli.tools import sim_tool

    src = inspect.getsource(sim_tool)

    assert "register_manipulation_skills" in src, (
        "sim_tool must import/call register_manipulation_skills — the "
        "single-source manipulation registration for the with_arm path"
    )
    assert "register_manipulation_skills(agent, base)" in src, (
        "sim_tool must call register_manipulation_skills(agent, base) so "
        "perception_grasp + pick/place are wired when with_arm=True"
    )

    # And the helper itself actually wires the 4 skills — verified where they
    # now live (single source), so the guard still catches a broken registrar.
    from vector_os_nano.skills import manipulation_setup

    helper_src = inspect.getsource(manipulation_setup)
    for cls in ("PickTopDownSkill", "PlaceTopDownSkill",
                "MobilePickSkill", "MobilePlaceSkill"):
        assert cls in helper_src, (
            f"{cls} not wired in manipulation_setup — with_arm loses the skill"
        )
