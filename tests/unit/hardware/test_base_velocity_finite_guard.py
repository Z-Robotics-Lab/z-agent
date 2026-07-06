# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""E189 regression: the base-velocity command boundary must reject non-finite input.

``set_velocity(vx, vy, vyaw)`` is the streaming actuator boundary for every mobile
base — driven by the Nav2 ``/cmd_vel_nav`` bridge, a BYO skill's walk/turn args, and
NL-parsed velocity values. Before this gate:

  * ``MuJoCoG1.set_velocity`` did ``float(vx)`` with NO clip and NO finiteness check,
    so NaN/±inf flowed straight into the actuator command array ``self._cmd`` AND into
    ``_cmd_motion`` (the R2b actor-causation honest-verify signal the Inv-1 spine reads).
  * ``MuJoCoGo2.set_velocity`` clips with ``np.clip`` — which clamps ±inf but PROPAGATES
    NaN (``np.clip(nan, lo, hi) == nan``), so a NaN command still poisoned ``_cmd_vel``
    and ``_cmd_motion``.
  * ``Go2ROS2Proxy.set_velocity`` published ``float(vx)`` onto ``/cmd_vel_nav`` with no
    check, forwarding NaN/inf to the real nav bridge.

A NaN in ``_cmd_motion`` silently breaks grading (``nan > MOTION_EPS`` is False, so a
real motion registers as no motion) while the command still reaches the actuator. The
global security floor (rules/common/security.md) mandates rejecting NaN/inf before
acting. Same class as E188 (actuator move_joints) but at the BASE velocity boundary.

Sim-free by design: the pure validator is tested directly (the sim slot is a single
global resource; E187/E188 likewise tested their validators directly). A source-level
wiring guard proves every concrete ``set_velocity`` calls it, so the guard cannot
silently regress out of a driver.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from zeno.hardware.base import ensure_finite_base_velocity

_HW = Path(__file__).resolve().parents[3] / "zeno" / "hardware"


class TestEnsureFiniteBaseVelocity:
    def test_accepts_finite(self) -> None:
        # Legitimate body velocities incl. negatives and zero (m/s, rad/s).
        ensure_finite_base_velocity(0.0, -0.5, 0.0)
        ensure_finite_base_velocity(1.2, 0.0, -3.14159)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nonfinite_vx(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            ensure_finite_base_velocity(bad, 0.0, 0.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nonfinite_vy(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            ensure_finite_base_velocity(0.0, bad, 0.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nonfinite_vyaw(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            ensure_finite_base_velocity(0.0, 0.0, bad)

    def test_error_names_the_bad_axis(self) -> None:
        with pytest.raises(ValueError, match="vyaw"):
            ensure_finite_base_velocity(0.1, 0.2, float("nan"))

    def test_context_label_in_message(self) -> None:
        with pytest.raises(ValueError, match="MuJoCoGo2.set_velocity"):
            ensure_finite_base_velocity(
                float("inf"), 0.0, 0.0, ctx="MuJoCoGo2.set_velocity"
            )


def _set_velocity_impls() -> list[Path]:
    """Every concrete driver file that defines a real ``set_velocity`` body."""
    out: list[Path] = []
    for p in _HW.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        if "def set_velocity(" not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "set_velocity":
                # Skip the pure Protocol interface (base.py) — docstring + ellipsis only.
                body = [n for n in node.body if not isinstance(n, ast.Expr)]
                if body:
                    out.append(p)
                    break
    return out


class TestEveryDriverGuardsItsBase:
    def test_impls_discovered(self) -> None:
        impls = _set_velocity_impls()
        assert len(impls) >= 3, f"expected multiple set_velocity drivers, found {impls}"

    @pytest.mark.parametrize("path", _set_velocity_impls(), ids=lambda p: p.name)
    def test_set_velocity_calls_finite_guard(self, path: Path) -> None:
        src = path.read_text(encoding="utf-8")
        assert "ensure_finite_base_velocity(" in src, (
            f"{path.name}: set_velocity does not call ensure_finite_base_velocity — "
            "a non-finite base command would be accepted silently (E189)"
        )
