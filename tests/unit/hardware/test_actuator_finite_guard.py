# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""E188 regression: the actuator-command boundary must reject non-finite targets.

A NaN/±inf joint target is currently written straight into the MuJoCo ``ctrl``
array (``self._data.ctrl[act_id] = ...``) and stepped, while ``move_joints``
returns ``True`` — a silent fail-open that poisons the sim state and every
downstream Inv-1 verify. It is REACHABLE from untrusted numeric input:
``config.skills.<name>.joint_values`` (a BYO-skill config surface read by
home/wave/handover/place) and the ROS2 ``hardware_bridge`` (``move_joints(ordered)``
from a JointState message). The global security floor mandates rejecting
NaN/inf before acting on an actuator. Same class as E187 (bare numeric coercion
of untrusted input) but at the actuator layer, not the manifest loader.

Sim-free by design: the pure validator is tested directly (the sim slot is a
single global resource, and E187 likewise tested its config parser directly).
A source-level wiring guard proves every concrete ``move_joints`` calls it, so
the guard cannot silently regress out of a driver.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from zeno.hardware.arm import ensure_finite_joint_targets

_HW = Path(__file__).resolve().parents[3] / "zeno" / "hardware"


class TestEnsureFiniteJointTargets:
    def test_accepts_finite(self) -> None:
        # A range of legitimate radian targets, incl. negatives and zero.
        ensure_finite_joint_targets([0.0, -1.2, 0.5, 3.14159, -0.001])

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nonfinite(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            ensure_finite_joint_targets([0.0, bad, 0.0])

    def test_error_is_index_scoped(self) -> None:
        with pytest.raises(ValueError, match=r"\[2\]"):
            ensure_finite_joint_targets([0.0, 0.1, float("nan"), 0.3])

    def test_context_label_in_message(self) -> None:
        with pytest.raises(ValueError, match="MuJoCoPiper.move_joints"):
            ensure_finite_joint_targets([float("inf")], ctx="MuJoCoPiper.move_joints")

    def test_empty_is_noop(self) -> None:
        # Length is a separate, pre-existing contract (dof mismatch); the
        # finiteness gate must not conflate the two.
        ensure_finite_joint_targets([])


def _move_joints_impls() -> list[Path]:
    """Every concrete driver file that defines a real ``move_joints`` body."""
    out: list[Path] = []
    for p in _HW.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        if "def move_joints(" not in src:
            continue
        # Skip the pure Protocol interface (arm.py) — it has only ``...`` bodies.
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "move_joints":
                body = [n for n in node.body if not isinstance(n, ast.Expr)]
                if body:  # a real implementation, not just a docstring + ellipsis
                    out.append(p)
                    break
    return out


class TestEveryDriverGuardsItsActuator:
    def test_impls_discovered(self) -> None:
        impls = _move_joints_impls()
        assert len(impls) >= 4, f"expected multiple move_joints drivers, found {impls}"

    @pytest.mark.parametrize("path", _move_joints_impls(), ids=lambda p: p.name)
    def test_move_joints_calls_finite_guard(self, path: Path) -> None:
        src = path.read_text(encoding="utf-8")
        assert "ensure_finite_joint_targets(" in src, (
            f"{path.name}: move_joints does not call ensure_finite_joint_targets — "
            "a non-finite actuator command would be accepted silently (E188)"
        )
