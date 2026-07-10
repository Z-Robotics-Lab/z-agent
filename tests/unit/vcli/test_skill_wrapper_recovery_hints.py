# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Recovery hints must be world-honest (sim-to-real migration, secondary audit #1).

Field forensics (2026-07-10, real-robot REPL audit): on a skill FAILURE the wrapper
appends a sim-era recovery hint to the model-facing error text keyed on the skill's
``diagnosis_code``. The kernel defaults name tools/worlds go2w_real does NOT have —
``no_base`` -> "Use start_simulation tool first"; ``navigation_failed`` -> "nav_state
tool"; ``no_vlm`` -> "Ollama"; ``camera_failed`` -> "robot_status tool". go2w_real's
sim/diag/system categories are DISABLED and bringup is ``go2w_real_bringup`` — so the
model is steered toward a sim tool that does not exist, away from the real recovery.

Reachability is CONFIRMED: ``go2w_real_skills.py`` and ``go2w_real_lifecycle.py`` both
emit ``diagnosis_code='no_base'`` when the base is not yet connected — a routine real
first-contact state.

Fix (additive, worlds-untouched-stay-identical):
1. The kernel ``no_base`` default becomes WORLD-NEUTRAL (no "start_simulation").
2. Hints are WORLD-OVERRIDABLE: the wrapper merges an optional agent-provided
   ``recovery_hints()`` map OVER the kernel defaults. An agent that omits the method is
   byte-identical (kernel defaults only). go2w_real's embodiment provides hardware
   hints (bringup + resume), so a real ``no_base`` failure steers to go2w_real_bringup.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from zeno.vcli.tools.base import ToolContext


class _Ctx(ToolContext):
    pass


def _context(agent: Any) -> ToolContext:
    return ToolContext(
        agent=agent,
        cwd=Path("/tmp"),
        session=None,
        permissions=None,
        abort=threading.Event(),
    )


class _FailingSkill:
    """A motor skill that fails with a given diagnosis_code (no recovery text)."""

    def __init__(self, diag: str) -> None:
        self.name = "navigate"
        self.description = "navigate the base"
        self.parameters: dict = {}
        self.preconditions: list = []
        self.effects = {"base_state": "moved"}
        self._diag = diag

    def execute(self, params: dict, context: Any) -> Any:
        from zeno.core.types import SkillResult

        return SkillResult(success=False, diagnosis_code=self._diag)


class _AgentNoHints:
    """Baseline agent WITHOUT a recovery_hints() method (dev/sim shape)."""

    def _build_context(self) -> Any:
        return object()

    def _sync_robot_state(self) -> None:
        return None

    # No _base attribute -> _get_post_state returns None (no state tail noise).
    _base = None


class _AgentWithHints(_AgentNoHints):
    """A hardware agent that overrides the sim hints with world-honest ones."""

    def recovery_hints(self) -> dict[str, str]:
        return {
            "no_base": (
                "No robot connected. Bring up the nav stack with "
                "go2w_real_bringup(action='start')."
            ),
            "estop_latched": "E-stop latched. Call resume_skill before any motion.",
        }


# ---------------------------------------------------------------------------
# 1. Kernel default no_base hint is world-NEUTRAL (no sim tool name)
# ---------------------------------------------------------------------------


def test_kernel_no_base_hint_names_no_sim_tool() -> None:
    from zeno.vcli.tools.skill_wrapper import _RECOVERY_HINTS

    hint = _RECOVERY_HINTS["no_base"]
    assert "start_simulation" not in hint, (
        "the kernel no_base hint must not name start_simulation — that tool does "
        "not exist on go2w_real (sim/diag/system are disabled there)"
    )


def test_no_base_failure_without_override_has_no_sim_tool() -> None:
    """A skill failing no_base on a hookless agent must not surface a sim tool name."""
    from zeno.vcli.tools.skill_wrapper import SkillWrapperTool

    agent = _AgentNoHints()
    wrapper = SkillWrapperTool(_FailingSkill("no_base"), agent)
    result = wrapper.execute({}, _context(agent))
    assert result.is_error is True
    assert "start_simulation" not in result.content


# ---------------------------------------------------------------------------
# 2. World-overridable: agent.recovery_hints() wins over the kernel default
# ---------------------------------------------------------------------------


def test_agent_recovery_hints_override_kernel_default() -> None:
    from zeno.vcli.tools.skill_wrapper import SkillWrapperTool

    agent = _AgentWithHints()
    wrapper = SkillWrapperTool(_FailingSkill("no_base"), agent)
    result = wrapper.execute({}, _context(agent))
    assert result.is_error is True
    assert "go2w_real_bringup" in result.content, (
        "the agent-provided no_base hint must replace the kernel default"
    )


def test_agent_recovery_hints_extend_new_codes() -> None:
    """A world can add a hint for a diagnosis code the kernel never had."""
    from zeno.vcli.tools.skill_wrapper import SkillWrapperTool

    agent = _AgentWithHints()
    wrapper = SkillWrapperTool(_FailingSkill("estop_latched"), agent)
    result = wrapper.execute({}, _context(agent))
    assert "resume_skill" in result.content


def test_hookless_agent_is_byte_identical_for_known_code() -> None:
    """An agent without recovery_hints() gets EXACTLY the kernel default hint."""
    from zeno.vcli.tools.skill_wrapper import SkillWrapperTool, _RECOVERY_HINTS

    agent = _AgentNoHints()
    wrapper = SkillWrapperTool(_FailingSkill("unknown_room"), agent)
    result = wrapper.execute({}, _context(agent))
    assert _RECOVERY_HINTS["unknown_room"] in result.content


def test_recovery_hints_raising_does_not_break_failure_path() -> None:
    """A world whose recovery_hints() raises must not crash the wrapper."""
    from zeno.vcli.tools.skill_wrapper import SkillWrapperTool

    class _AngryAgent(_AgentNoHints):
        def recovery_hints(self) -> dict[str, str]:
            raise RuntimeError("boom")

    agent = _AngryAgent()
    wrapper = SkillWrapperTool(_FailingSkill("no_base"), agent)
    result = wrapper.execute({}, _context(agent))
    # Degrades to the kernel default; still a clean is_error result.
    assert result.is_error is True
    assert "start_simulation" not in result.content


# ---------------------------------------------------------------------------
# 3. go2w_real embodiment actually provides hardware hints
# ---------------------------------------------------------------------------


def test_go2w_real_embodiment_provides_hardware_recovery_hints() -> None:
    from zeno.vcli.worlds.go2w_real import Go2WRealEmbodiment

    emb = Go2WRealEmbodiment()
    assert hasattr(emb, "recovery_hints"), (
        "the go2w_real embodiment must expose recovery_hints() for the wrapper"
    )
    hints = emb.recovery_hints()
    assert "no_base" in hints
    assert "start_simulation" not in hints["no_base"]
    assert "go2w_real_bringup" in hints["no_base"]
