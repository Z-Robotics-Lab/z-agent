# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Plug-and-play auto-``home`` drop guard completeness (R386/E175, self-fixed strictly safe).

``Agent.execute_skill`` builds a plan for a dispatched skill and APPENDS a ``home`` step at the
end (HomeSkill unconditionally OPENS the gripper — ``skills/home.py``). It suppresses that
append for a skill that must keep its end-state gripper — but it recognized "does this skill end
holding an object?" by a HARDCODED name/param list: ``pick`` with ``mode='hold'`` plus
``gripper_close`` / ``gripper_open`` / ``home``.

Like E173's manip gate and E174's post-place guard, this classifier fails for the North-Star
plug-and-play path ("bring a skill — no kernel edit"): a BYO grasp-and-hold skill (novel name,
effect ``gripper_state: holding``) is NOT in the list, so ``home`` is appended, the gripper
opens, and the just-grasped object is silently DROPPED — the exact '掉了' hazard the E60
post-place guard prevents, here on the GRASP side.

It is ALSO incomplete for SHIPPED skills: ``pick_top_down`` / ``mobile_pick`` /
``perception_grasp`` all declare ``gripper_state: holding`` yet are absent from the list, so a
direct dispatch of any of them appends ``home`` and drops what they just grasped — a latent gap
(no shipped path dispatches them directly today, so it is unexercised, not observed).

FIX (strictly safe; ``core/agent.py`` is NOT a spine path — check.sh SPINE regex; no interface /
flag change -> self-crossed): UNION the name/param list with the skill's OWN structured
end-holding effect (``_skill_ends_holding``: effect ``gripper_state == 'holding'`` OR a non-None
``held_object`` effect). The delta over EVERY shipped skill class is EXACTLY
{pick_top_down, mobile_pick, perception_grasp} — all grasp-and-hold skills whose declared intent
is to end holding; suppressing ``home`` for them matches the established ``pick(mode='hold')``
contract (a correct completeness fix, stated honestly — NOT zero-delta). ``pick`` (effect
``gripper_state: open``, the NL fetch/pick executor) is UNAFFECTED, so every confirmed fetch/
place BOARD row is untouched. More preservation of a grasped object = safe in the same direction
as E174.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import zeno.skills
from zeno.core.agent import Agent, _skill_ends_holding


def _all_shipped_skill_classes() -> dict[str, type]:
    """Every shipped skill CLASS keyed by its ``name`` (a superset of ``get_default_skills``,
    which instantiates only the embodiment-agnostic subset — the grasp/place variants are
    embodiment-registered via ``register_manipulation_skills``)."""
    seen: dict[str, type] = {}
    for mod in pkgutil.walk_packages(
        zeno.skills.__path__, "zeno.skills."
    ):
        try:
            module = importlib.import_module(mod.name)
        except Exception:  # noqa: BLE001 - a skill module needing hardware imports is skipped
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            cn = getattr(obj, "name", None)
            if isinstance(cn, str) and cn not in seen and hasattr(obj, "effects"):
                seen[cn] = obj
    return seen


def _skill_named(name: str) -> Any:
    cls = _all_shipped_skill_classes().get(name)
    if cls is None:
        raise AssertionError(f"shipped skill {name!r} not found")
    return cls


class _ByoClamp:
    """A BYO grasp-and-hold skill (no kernel edit): novel name, its structured effect declares
    it ends holding the grasped object — exactly a real grasp-hold would."""
    name = "clamp"
    description = "Clamp onto an object and hold it."
    parameters = {"object": {"type": "string"}}
    preconditions = ["gripper_empty"]
    postconditions = ["gripper_holding_any"]
    effects = {"gripper_state": "holding"}
    __skill_auto_steps__: list = []


class _ByoHeldObject:
    """A BYO skill that expresses end-holding via a non-None ``held_object`` effect instead of
    ``gripper_state`` — the classifier must catch this shape too."""
    name = "grab_named"
    description = "Grab and retain a named object."
    parameters: dict = {}
    preconditions = ["gripper_empty"]
    effects = {"held_object": "widget"}


class _ByoWipe:
    """A BYO skill that ends with the gripper EMPTY (a wipe/release): must NOT be classified as
    end-holding, so ``home`` is still appended."""
    name = "wipe"
    description = "Wipe a surface, gripper ends empty."
    parameters: dict = {}
    preconditions: list = []
    effects = {"gripper_state": "open", "held_object": None}


# --- The plug-and-play gap the fix closes -------------------------------------------------

def test_byo_hold_skill_ends_holding_via_metadata():
    """A BYO grasp-and-hold skill (novel name) is recognized as end-holding through its
    structured effect, so the auto-``home`` append is suppressed (was silently dropped)."""
    assert _skill_ends_holding(_ByoClamp()) is True


def test_byo_held_object_effect_ends_holding():
    """End-holding expressed via a non-None ``held_object`` effect is caught too."""
    assert _skill_ends_holding(_ByoHeldObject()) is True


def test_byo_empty_gripper_skill_not_ends_holding():
    """The fix must not OVER-classify: a skill whose effect empties the gripper is NOT
    end-holding, so ``home`` is still appended after it."""
    assert _skill_ends_holding(_ByoWipe()) is False


def test_malformed_effects_never_classified():
    """A skill with non-dict / absent effects must fail safe to False (no crash)."""
    class _Bad:
        name = "bad"
        effects = "not-a-dict"
    class _NoEffects:
        name = "noeff"
    assert _skill_ends_holding(_Bad()) is False
    assert _skill_ends_holding(_NoEffects()) is False


# --- The shipped latent gap the fix also closes -------------------------------------------

def test_shipped_holding_skills_classified_end_holding():
    """``pick_top_down`` / ``mobile_pick`` / ``perception_grasp`` all declare
    ``gripper_state: holding`` — the metadata half closes this shipped gap."""
    for name in ("pick_top_down", "mobile_pick", "perception_grasp"):
        assert _skill_ends_holding(_skill_named(name)) is True, name


def test_end_holding_delta_over_all_shipped_is_exact():
    """The ONLY shipped skills the metadata half classifies as end-holding are exactly the three
    grasp-and-hold skills — proving the union re-classifies no other shipped skill (``pick``,
    the NL fetch executor with effect ``gripper_state: open``, is NOT among them)."""
    by_metadata = {
        name for name, cls in _all_shipped_skill_classes().items()
        if _skill_ends_holding(cls)
    }
    assert by_metadata == {"pick_top_down", "mobile_pick", "perception_grasp"}, by_metadata


def test_shipped_pick_not_end_holding():
    """The NL fetch/pick executor (``pick``, effect ``gripper_state: open``) is UNAFFECTED — it
    must NOT be classified end-holding, so its default drop-at-home path is byte-identical."""
    assert _skill_ends_holding(_skill_named("pick")) is False


# --- Dispatch-level witness: no auto-home appended for a BYO hold skill --------------------

class _CapturingExecutor:
    """Records the plan it is asked to execute so the test can inspect the appended steps
    without running a sim; returns a benign success."""

    def __init__(self) -> None:
        self.captured: Any = None

    def execute(self, plan: Any, *args: Any, **kwargs: Any) -> Any:
        from zeno.core.types import ExecutionResult
        self.captured = plan
        return ExecutionResult(success=True, status="completed")


def _plan_step_names(agent: Agent, skill: Any, params: dict) -> list[str]:
    agent._skill_registry.register(skill)
    cap = _CapturingExecutor()
    agent._executor = cap
    agent.execute_skill(skill.name, params)
    return [s.skill_name for s in cap.captured.steps]


def test_byo_hold_dispatch_appends_no_home():
    """End-to-end at the plan-construction level: dispatching a BYO grasp-and-hold skill builds
    a plan that does NOT append ``home`` (which would open the gripper and drop the object)."""
    steps = _plan_step_names(Agent(), _ByoClamp(), {"object": "cube"})
    assert "home" not in steps, steps
    assert steps[-1] == "clamp", steps


def test_byo_empty_gripper_dispatch_still_appends_home():
    """A BYO skill that ends gripper-empty STILL gets the auto-``home`` append — the guard only
    suppresses it for end-holding skills, so unrelated skills are unchanged."""
    steps = _plan_step_names(Agent(), _ByoWipe(), {})
    assert steps[-1] == "home", steps
