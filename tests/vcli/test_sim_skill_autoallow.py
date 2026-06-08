# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2-5: motor skills in simulation must be auto-allowed without a confirmation prompt.

All tests use deterministic stubs — no real hardware or MuJoCo is required.
Stub hardware classes whose __module__ is manipulated to match sim / real paths,
matching the detection logic in SkillWrapperTool._robot_is_simulated().
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from vector_os_nano.vcli.tools.skill_wrapper import SkillWrapperTool


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


def _make_skill(name: str = "scan", motor: bool = True) -> Any:
    """Build a minimal Skill-protocol stub.

    A motor skill gets a description containing the keyword 'arm' so
    SkillWrapperTool._detect_motor() classifies it correctly.
    """
    description = "Move the arm to scan for objects" if motor else "Query sensor readings"
    return SimpleNamespace(
        name=name,
        description=description,
        parameters={},
        preconditions=["arm ready"] if motor else [],
        effects={"arm_moved": True} if motor else {},
    )


def _make_sim_hw() -> Any:
    """Return a stub hardware object whose module path is a sim path (R2-5 trigger)."""

    class _SimArm:
        pass

    _SimArm.__module__ = "vector_os_nano.hardware.sim.mujoco_arm"
    return _SimArm()


def _make_real_hw() -> Any:
    """Return a stub hardware object whose module path is a real-hardware path."""

    class _RealArm:
        pass

    _RealArm.__module__ = "vector_os_nano.hardware.real_arm"
    return _RealArm()


def _make_agent(arm: Any = None, base: Any = None, gripper: Any = None) -> Any:
    """Assemble a minimal agent stub with _arm / _base / _gripper attributes."""
    return SimpleNamespace(_arm=arm, _base=base, _gripper=gripper)


def _wrap(skill: Any, agent: Any) -> SkillWrapperTool:
    return SkillWrapperTool(skill, agent)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSimAutoAllow:
    """R2-5: motor skill + sim hardware -> auto-allow."""

    def test_motor_skill_sim_arm_is_allowed(self) -> None:
        """Motor skill with a sim _arm should return 'allow', not 'ask'."""
        tool = _wrap(_make_skill(motor=True), _make_agent(arm=_make_sim_hw()))
        assert tool._is_motor  # verify the skill is classified as motor
        result = tool.check_permissions({}, None)
        assert result.behavior == "allow", (
            "motor skill on sim hardware must be auto-allowed (R2-5)"
        )

    def test_motor_skill_sim_base_is_allowed(self) -> None:
        """Motor skill with a sim _base (no arm) should also return 'allow'."""

        class _SimBase:
            pass

        _SimBase.__module__ = "vector_os_nano.hardware.sim.mujoco_go2"
        tool = _wrap(_make_skill(motor=True), _make_agent(base=_SimBase()))
        result = tool.check_permissions({}, None)
        assert result.behavior == "allow"

    def test_motor_skill_sim_gripper_is_allowed(self) -> None:
        """Motor skill with a sim _gripper (no arm/base) should return 'allow'."""

        class _SimGripper:
            pass

        _SimGripper.__module__ = "vector_os_nano.hardware.sim.mujoco_gripper"
        tool = _wrap(_make_skill(motor=True), _make_agent(gripper=_SimGripper()))
        result = tool.check_permissions({}, None)
        assert result.behavior == "allow"


class TestRealHardwareRequiresConfirm:
    """Motor skill + real hardware -> must still require confirmation (safety rail)."""

    def test_motor_skill_real_arm_asks(self) -> None:
        """Motor skill with a real-hardware _arm must return 'ask' — safety rail must hold."""
        tool = _wrap(_make_skill(motor=True), _make_agent(arm=_make_real_hw()))
        result = tool.check_permissions({}, None)
        assert result.behavior == "ask", (
            "motor skill on real hardware must still require confirmation"
        )

    def test_motor_skill_non_sim_module_asks(self) -> None:
        """A module path that merely contains 'sim' as a substring but is not under
        vector_os_nano.hardware.sim must NOT be treated as simulated."""

        class _FakeSimArm:
            pass

        # 'simulation_hardware' — contains 'sim' but not the exact prefix
        _FakeSimArm.__module__ = "some_simulation_hardware.arm"
        tool = _wrap(_make_skill(motor=True), _make_agent(arm=_FakeSimArm()))
        result = tool.check_permissions({}, None)
        assert result.behavior == "ask"


class TestReadOnlyAlwaysAllowed:
    """Read-only (non-motor) skills must be auto-allowed in ALL cases."""

    def test_readonly_skill_sim_agent_allowed(self) -> None:
        tool = _wrap(_make_skill(motor=False), _make_agent(arm=_make_sim_hw()))
        assert not tool._is_motor
        result = tool.check_permissions({}, None)
        assert result.behavior == "allow"

    def test_readonly_skill_real_agent_allowed(self) -> None:
        tool = _wrap(_make_skill(motor=False), _make_agent(arm=_make_real_hw()))
        result = tool.check_permissions({}, None)
        assert result.behavior == "allow"

    def test_readonly_skill_no_agent_allowed(self) -> None:
        tool = _wrap(_make_skill(motor=False), None)
        result = tool.check_permissions({}, None)
        assert result.behavior == "allow"


class TestNoAgentFailSafe:
    """agent=None / no hardware attributes -> not simulated -> motor requires ask."""

    def test_motor_skill_none_agent_asks(self) -> None:
        """No agent means we cannot confirm sim context — fail safe to 'ask'."""
        tool = _wrap(_make_skill(motor=True), None)
        result = tool.check_permissions({}, None)
        assert result.behavior == "ask", (
            "no agent means unknown hardware — must not silently allow motor skill"
        )

    def test_motor_skill_agent_no_hw_attrs_asks(self) -> None:
        """Agent with no _arm/_base/_gripper attributes -> not detected as sim -> ask."""
        agent_no_hw = SimpleNamespace()  # no _arm, _base, _gripper
        tool = _wrap(_make_skill(motor=True), agent_no_hw)
        result = tool.check_permissions({}, None)
        assert result.behavior == "ask"

    def test_motor_skill_agent_all_none_hw_asks(self) -> None:
        """Agent with all hardware attributes set to None -> not sim -> ask."""
        tool = _wrap(_make_skill(motor=True), _make_agent(arm=None, base=None, gripper=None))
        result = tool.check_permissions({}, None)
        assert result.behavior == "ask"


class TestSimDetectionHelper:
    """Unit tests for the _robot_is_simulated helper directly."""

    def test_sim_arm_detected(self) -> None:
        tool = _wrap(_make_skill(), _make_agent(arm=_make_sim_hw()))
        assert tool._robot_is_simulated() is True

    def test_real_arm_not_sim(self) -> None:
        tool = _wrap(_make_skill(), _make_agent(arm=_make_real_hw()))
        assert tool._robot_is_simulated() is False

    def test_none_agent_not_sim(self) -> None:
        tool = _wrap(_make_skill(), None)
        assert tool._robot_is_simulated() is False

    def test_sim_module_prefix_boundary(self) -> None:
        """Module path must START WITH the exact prefix, not just contain it."""

        class _Arm:
            pass

        _Arm.__module__ = "vector_os_nano.hardware.sim"  # exact prefix match
        tool = _wrap(_make_skill(), _make_agent(arm=_Arm()))
        assert tool._robot_is_simulated() is True

    def test_sibling_package_with_sim_prefix_not_detected(self) -> None:
        """A sibling package whose name merely STARTS WITH 'sim' (e.g.
        'vector_os_nano.hardware.simulated_real.arm') must NOT be treated as
        simulated — the match is the exact package 'hardware.sim' or a '.'-delimited
        sub-module, never a raw string prefix."""

        class _Arm:
            pass

        _Arm.__module__ = "vector_os_nano.hardware.simulated_real.arm"
        tool = _wrap(_make_skill(), _make_agent(arm=_Arm()))
        assert tool._robot_is_simulated() is False

    def test_mixed_sim_and_real_hardware_not_simulated(self) -> None:
        """SAFETY: a mixed agent (sim _arm + REAL _base) must NOT be 'simulated' —
        any real component keeps the confirmation gate so we never auto-actuate
        real hardware. A motor skill on such an agent must return 'ask'."""
        agent = _make_agent(arm=_make_sim_hw(), base=_make_real_hw())
        tool = _wrap(_make_skill(motor=True), agent)
        assert tool._robot_is_simulated() is False
        assert tool.check_permissions({}, None).behavior == "ask"
