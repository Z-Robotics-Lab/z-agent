# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Engine-level regression — an arm VGG scan plan retries without falling to 'unmatched'.

Companion to ``test_arm_retry_unmatched_repro`` (which pins the bug at the harness
unit level). This drives the SAME failure through the REAL engine wiring that
``run_turn_unified`` -> ``_unified_plan_turn`` uses: ``VectorEngine.init_vgg``
constructs the ``StrategySelector`` with the arm skill registry and
``has_base=False`` (derived from a baseless arm agent), builds the ``VGGHarness``
over it, and ``vgg_execute`` runs the harness loop (with its per-step retries).

Live symptom reproduced here end-to-end: a 1-step plan whose step carries the
VALID explicit strategy ``scan_skill`` but whose verify FAILS (forcing the retry
path) must keep routing to the real ``scan`` skill and surface the honest failure
— never the opaque ``no strategy matched for 'unmatched'`` that the old
retry-clears-strategy behaviour produced on a baseless arm world.

Hermetic: a mock backend (never called — the plan is built directly), no mujoco,
no live LLM. The arm agent is a duck-typed stub: ``_base=None`` (baseless),
``_arm`` present (robot-world ready), and a real-ish ``_skill_registry`` exposing
``scan``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from zeno.vcli.cognitive.types import GoalTree, SubGoal
from zeno.vcli.engine import VectorEngine
from zeno.vcli.permissions import PermissionContext
from zeno.vcli.tools.base import CategorizedToolRegistry
from zeno.vcli.worlds.robot import RobotWorld


# ---------------------------------------------------------------------------
# Baseless arm stubs (duck-typed to what the engine + selector read)
# ---------------------------------------------------------------------------


class _SkillResult:
    def __init__(self, success: bool) -> None:
        self.success = success
        self.result_data = {"scanned": True}
        self.error_message = ""


class _ScanSkill:
    name = "scan"
    parameters: dict = {}

    def execute(self, params: dict, context: Any = None) -> _SkillResult:
        # The skill itself succeeds; the only failure is the verify miss, exactly
        # like a fresh-world predicate returning False on attempt 0.
        return _SkillResult(success=True)


class _ArmRegistry:
    def __init__(self) -> None:
        self._skills = {"scan": _ScanSkill()}

    def list_skills(self) -> list[str]:
        return ["scan"]

    def get(self, name: str) -> _ScanSkill | None:
        return self._skills.get(name)

    def match(self, _description: str) -> None:
        return None

    def to_schemas(self) -> list[dict[str, Any]]:
        return [{"name": "scan", "description": "sweep the workspace", "parameters": {}}]


class _ArmAgent:
    """Baseless arm agent: no mobile base, an arm present, a scan-only registry."""

    def __init__(self) -> None:
        self._base = None
        self._arm = object()
        self._gripper = None
        self._perception = None
        self._spatial_memory = None
        self._vlm = None
        self._world_model = None
        self._calibration = None
        self._config: dict = {}
        self._skill_registry = _ArmRegistry()


class _MockBackend:
    """Never invoked here — the plan tree is built directly."""

    def call(self, *_: Any, **__: Any) -> Any:
        class _R:
            text = "{}"

        return _R()


def _arm_engine(tmp_path: Path) -> VectorEngine:
    engine = VectorEngine(
        backend=_MockBackend(),
        registry=CategorizedToolRegistry(),
        permissions=PermissionContext(),
    )
    agent = _ArmAgent()
    engine.init_vgg(
        agent=agent,
        skill_registry=agent._skill_registry,
        world=RobotWorld(),
        persist_dir=None,  # in-memory only — never touch the home dir
    )
    assert engine._vgg_enabled is True
    # Sanity: the engine built the selector for a BASELESS arm world.
    assert engine._vgg_harness._selector._has_base is False
    return engine


def _scan_plan(verify: str) -> GoalTree:
    """A 1-step plan exactly like vgg_decompose's fast path emits for a scan."""
    return GoalTree(
        goal="扫一眼看看",
        sub_goals=(
            SubGoal(
                name="scan_goal",
                description="扫一眼看看工作台",
                verify=verify,
                strategy="scan_skill",  # VALID — 'scan' is a registered arm skill
            ),
        ),
    )


# ---------------------------------------------------------------------------
# The regression: a failing scan plan retries to the REAL skill, not 'unmatched'.
# ---------------------------------------------------------------------------


def test_arm_scan_plan_retry_routes_to_real_skill_not_unmatched(tmp_path: Path) -> None:
    engine = _arm_engine(tmp_path)

    # verify=False forces the retry path (every attempt's verify misses).
    trace = engine.vgg_execute(_scan_plan("False"))

    assert trace.success is False  # honest failure: the verify never passes
    step = trace.steps[0]
    # The bug: the retry cleared the valid strategy and fell to 'unmatched' on the
    # baseless arm world. Fixed: it keeps routing to the real 'scan' skill and
    # surfaces the honest failure.
    assert step.strategy == "scan"
    assert step.strategy != "unmatched"
    assert "unmatched" not in step.error


def test_arm_scan_plan_succeeds_when_verify_passes(tmp_path: Path) -> None:
    """Control: a passing-verify scan plan runs the real skill and succeeds (no
    retry, byte-identical happy path)."""
    engine = _arm_engine(tmp_path)

    trace = engine.vgg_execute(_scan_plan("True"))

    assert trace.success is True
    step = trace.steps[0]
    assert step.strategy == "scan"
    assert step.success is True


# ---------------------------------------------------------------------------
# Fail-loud is NOT regressed at the engine level: an UNKNOWN '<x>_skill' still
# surfaces a clear 'invalid' error through the same wiring, never 'unmatched'.
# ---------------------------------------------------------------------------


def test_arm_unknown_skill_plan_fails_loud_through_engine(tmp_path: Path) -> None:
    engine = _arm_engine(tmp_path)

    tree = GoalTree(
        goal="do a bogus thing",
        sub_goals=(
            SubGoal(
                name="bogus_goal",
                description="扫一眼看看工作台",
                verify="False",
                strategy="bogus_skill",  # NOT a registered arm skill
            ),
        ),
    )
    trace = engine.vgg_execute(tree)

    assert trace.success is False
    step = trace.steps[0]
    assert "unmatched" not in step.error
    assert "bogus_skill" in step.error
    assert "scan" in step.error  # valid set surfaced
