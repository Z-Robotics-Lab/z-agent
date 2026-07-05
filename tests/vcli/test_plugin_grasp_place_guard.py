# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Plug-and-play post-place re-grasp guard completeness (R385/E174, self-fixed strictly-stricter).

The E60 post-place guard (``native_loop.dispatch_skill``) prevents the '掉了' misread that
UNDOES a placement: after a successful PLACE the gripper is legitimately empty, so a brain that
re-reads that as an accidental drop and RE-GRASPS lifts the just-placed object back off the
receptacle. The guard ARMS after a place and REFUSES a re-grasp until one verify closes it.

But it recognized "is this a place?" / "is this a grasp?" by HARDCODED name-lists
(``_PLACE_SKILLS`` / ``_GRASP_SKILLS``). Like E173's manip gate, this fails OPEN for the
North-Star plug-and-play path ("bring a skill — no kernel edit"):
  * a BYO place skill (novel name) never ARMS the guard -> an errant re-grasp is NOT refused ->
    the placement is silently undone, the exact defect the guard exists to prevent;
  * a BYO grasp skill (novel name) is never REFUSED even when the guard is armed.
It is ALSO incomplete for a SHIPPED skill: ``handover`` empties the gripper (same '掉了' risk)
yet is absent from ``_PLACE_SKILLS`` — a latent shipped gap.

FIX (strictly stricter, Invariant-1 — the sandbox only gets STRICTER; non-spine native_loop +
skill_wrapper; no interface / flag change -> self-crossed): classify by the skill's OWN
structured metadata, UNIONed with the retained name-lists —
  * grasp  <- precondition declares ``gripper_empty``      (``SkillWrapperTool._is_grasp``);
  * place  <- precondition ``gripper_holding_any`` AND the effect EMPTIES the gripper
              (``SkillWrapperTool._releases_object``).
Grasp classification is byte-IDENTICAL to the shipped name-list (the 4 grasp skills are exactly
the ``gripper_empty``-precondition skills). Place classification is a strict SUPERSET: it ADDS
the shipped ``handover`` (a correct completeness fix) plus any BYO release skill; it never drops
a shipped place. More arming + more refusal = strictly stricter, and the guard stays bounded by
``_MAX_VERIFY_NUDGES`` so it can never wedge.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import vector_os_nano.skills
from vector_os_nano.vcli.native_loop import (
    _GRASP_SKILLS,
    _PLACE_SKILLS,
    _skill_is_grasp,
    _skill_is_place,
)
from vector_os_nano.vcli.tools.skill_wrapper import SkillWrapperTool


def _all_shipped_skill_classes() -> dict[str, type]:
    """Every shipped skill CLASS keyed by its ``name`` (a superset of ``get_default_skills``,
    which instantiates only the embodiment-agnostic subset — the grasp/place variants in the
    name-lists are embodiment-registered)."""
    seen: dict[str, type] = {}
    for mod in pkgutil.walk_packages(
        vector_os_nano.skills.__path__, "vector_os_nano.skills."
    ):
        try:
            module = importlib.import_module(mod.name)
        except Exception:  # noqa: BLE001 - a skill module needing hardware imports is skipped
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            cn = getattr(obj, "name", None)
            if isinstance(cn, str) and cn not in seen and hasattr(obj, "preconditions"):
                seen[cn] = obj
    return seen


def _wrap(skill: Any) -> SkillWrapperTool:
    return SkillWrapperTool(skill, agent=object())


class _ByoDropoff:
    """A BYO place skill (no kernel edit): novel name, structured metadata declares it
    consumes a held object and empties the gripper — exactly a real place would."""
    name = "dropoff"
    description = "Set the carried object down at the target."
    parameters = {"target": {"type": "string"}}
    preconditions = ["gripper_holding_any"]
    postconditions = ["gripper_empty"]
    effects = {"gripper_state": "open", "held_object": None}


class _ByoSnatch:
    """A BYO grasp skill: novel name, precondition requires an empty gripper (it grabs)."""
    name = "snatch"
    description = "Snatch an object off the shelf."
    parameters = {"object": {"type": "string"}}
    preconditions = ["gripper_empty"]
    postconditions = ["gripper_holding_any"]
    effects = {"gripper_state": "holding"}


class _ByoTune:
    """A BYO non-manipulation skill: no gripper preconditions. Must classify as neither."""
    name = "tune"
    description = "Play a tune."
    parameters: dict = {}
    preconditions: list = []
    effects = {"audio": "played"}


def _skill_named(name: str) -> Any:
    cls = _all_shipped_skill_classes().get(name)
    if cls is None:
        raise AssertionError(f"shipped skill {name!r} not found")
    return cls


# --- The plug-and-play gap the fix closes -------------------------------------------------

def test_byo_place_skill_arms_guard_via_metadata():
    """A BYO place skill (novel name) is recognized as a place through its structured
    metadata, so its success ARMS the post-place guard (was silently un-armed)."""
    assert _skill_is_place(_wrap(_ByoDropoff())) is True


def test_byo_grasp_skill_refused_via_metadata():
    """A BYO grasp skill (novel name) is recognized as a grasp, so the armed guard REFUSES
    it (was silently allowed, undoing the placement)."""
    assert _skill_is_grasp(_wrap(_ByoSnatch())) is True


def test_byo_nonmanip_skill_is_neither():
    """The fix must not OVER-classify: a BYO skill with no gripper precondition is neither a
    grasp nor a place, so it never arms the guard nor gets refused."""
    tool = _wrap(_ByoTune())
    assert _skill_is_grasp(tool) is False
    assert _skill_is_place(tool) is False


# --- The shipped latent gap the fix also closes -------------------------------------------

def test_handover_now_classified_place():
    """``handover`` empties the gripper (same '掉了' re-grasp risk) yet was absent from the
    hardcoded ``_PLACE_SKILLS`` — the metadata half closes this shipped gap."""
    assert "handover" not in _PLACE_SKILLS  # was un-guarded by name
    assert _skill_is_place(_wrap(_skill_named("handover"))) is True


# --- Zero-regression witnesses (grasp side is byte-identical to the name-list) -------------

def test_shipped_grasp_skills_all_classified_grasp():
    for name in _GRASP_SKILLS:
        assert _skill_is_grasp(_wrap(_skill_named(name))) is True, name


def test_shipped_place_skills_all_classified_place():
    for name in _PLACE_SKILLS:
        assert _skill_is_place(_wrap(_skill_named(name))) is True, name


def test_grasp_metadata_matches_name_list_exactly_on_shipped():
    """ZERO shipped-behavior delta on the grasp side: across EVERY shipped skill class, the ones
    whose structured precondition is ``gripper_empty`` are EXACTLY ``_GRASP_SKILLS`` — the union
    adds nothing for shipped skills, only for BYO grasp skills."""
    by_metadata = {
        name for name, cls in _all_shipped_skill_classes().items()
        if getattr(_wrap(cls), "_is_grasp", False)
    }
    assert by_metadata == set(_GRASP_SKILLS), by_metadata


def test_place_metadata_delta_is_only_handover_on_shipped():
    """The place side's ONLY shipped delta is ``handover`` (a correct completeness fix): across
    EVERY shipped skill class the gripper-emptying releasers are ``_PLACE_SKILLS`` ∪ {handover},
    proving the union never re-classifies any other shipped skill."""
    by_metadata = {
        name for name, cls in _all_shipped_skill_classes().items()
        if getattr(_wrap(cls), "_releases_object", False)
    }
    assert by_metadata == set(_PLACE_SKILLS) | {"handover"}, by_metadata


class _ByoTool:
    """A duck-typed BYO motor tool carrying the metadata flags SkillWrapperTool would compute,
    so ``dispatch_skill`` reads them exactly as it does for a real wrapped BYO skill."""

    def __init__(self, name: str, *, is_grasp: bool = False, releases: bool = False) -> None:
        self.name = name
        self._is_grasp = is_grasp
        self._releases_object = releases

    def execute(self, params: Any, context: Any) -> Any:
        from vector_os_nano.vcli.tools.base import ToolResult
        return ToolResult(content=f"{self.name} ok")


def test_byo_place_then_grasp_refused_through_dispatch():
    """End-to-end at the loop level: a BYO place skill (novel name, metadata-only — NOT in any
    name-list) ARMS the guard, and a BYO grasp skill (novel name) is then REFUSED until a verify
    closes the place — the North-Star plug-and-play protection the name-lists could not give."""
    from types import SimpleNamespace

    from vector_os_nano.vcli.native_loop import NativeStepRunner

    tnl = importlib.import_module("tests.unit.vcli.test_native_loop")
    agent, _base = tnl._make_agent(0.0, 0.0)
    motor = {
        "dropoff": _ByoTool("dropoff", releases=True),
        "snatch": _ByoTool("snatch", is_grasp=True),
    }
    verifier = SimpleNamespace(verify=lambda expr: True)
    runner = NativeStepRunner(
        agent, verifier, frozenset({"resting_on_receptacle"}), motor, SimpleNamespace()
    )
    # (1) BYO place succeeds -> arms the guard (name-list never mentions "dropoff").
    assert runner.dispatch_skill("dropoff", {}).is_error is False
    # (2) an immediate BYO re-grasp is refused (was silently allowed pre-fix).
    blocked = runner.dispatch_skill("snatch", {"object": "cup"})
    assert blocked.is_error is True
    # (3) a verify closes the place -> the next grasp runs.
    runner.handle_verify("resting_on_receptacle() >= 1")
    assert runner.dispatch_skill("snatch", {"object": "cup"}).is_error is False


def test_navigation_and_perception_never_classified():
    """A base-only / perception skill must never arm the guard or be refused as a grasp."""
    for name in ("navigate", "detect", "describe"):
        try:
            tool = _wrap(_skill_named(name))
        except AssertionError:
            continue
        assert _skill_is_grasp(tool) is False, name
        assert _skill_is_place(tool) is False, name
