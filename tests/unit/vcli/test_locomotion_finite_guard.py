# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Finiteness gate on the BLOCKING locomotion primitives (walk_forward / turn).

The E187→E190 external-input-finiteness vein guards the *actuator* command
boundary (arm move_joints, base set_velocity, nav goal). walk_forward/turn are a
DIFFERENT, un-gated boundary: their numeric argument is a loop-TERMINATION
threshold that is never passed to set_velocity, so the hardware/base.py velocity
gate (E189) structurally cannot catch it.

With ``distance_m=NaN``: ``covered >= abs(nan)`` is always False, so the robot
moves at the default speed for the ENTIRE 30 s timeout on a poisoned command,
then returns False — real motion executed on an unvalidated input, invisible to
the honest-verify spine. Reachable via the untrusted LLM plan JSON
(``{"distance": NaN}`` → json.loads → float('nan') → strategy_selector →
walk_forward). Security-floor violation: "reject NaN/inf before acting".
"""
from __future__ import annotations

import inspect
import math

import pytest

from zeno.vcli.primitives import PrimitiveContext, locomotion


# --------------------------------------------------------------------------- #
# Pure validator
# --------------------------------------------------------------------------- #
def test_ensure_finite_travel_passes_finite():
    assert locomotion.ensure_finite_travel(1.5, "distance_m") == 1.5
    assert locomotion.ensure_finite_travel(-0.0, "distance_m") == -0.0
    assert locomotion.ensure_finite_travel(1e6, "angle_rad") == 1e6


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_ensure_finite_travel_rejects_nonfinite(bad):
    with pytest.raises(ValueError) as exc:
        locomotion.ensure_finite_travel(bad, "distance_m")
    # axis-scoped, loud
    assert "distance_m" in str(exc.value)


# --------------------------------------------------------------------------- #
# Behavioral: a NaN/inf target must RAISE before any motion is commanded
# --------------------------------------------------------------------------- #
class _RecordingBase:
    """Fake base that FAILS if set_velocity is ever called, proving the guard
    fires before the robot is commanded to move. Each get_* call advances one
    step through a fixed sequence so a legit call reaches its target at once."""

    def __init__(self, positions=None, headings=None):
        self.set_velocity_calls: list[tuple] = []
        self._positions = list(positions or [(0.0, 0.0, 0.0), (99.0, 0.0, 0.0)])
        self._headings = list(headings or [0.0, 9.0])
        self._pos_n = 0
        self._head_n = 0

    def get_position(self):
        i = min(len(self._positions) - 1, self._pos_n)
        self._pos_n += 1
        return self._positions[i]

    def get_heading(self):
        i = min(len(self._headings) - 1, self._head_n)
        self._head_n += 1
        return self._headings[i]

    def set_velocity(self, vx, vy, vyaw):
        self.set_velocity_calls.append((vx, vy, vyaw))

    def stop(self):
        pass


@pytest.fixture
def wired_base():
    base = _RecordingBase()
    prev = locomotion._ctx
    locomotion._ctx = PrimitiveContext(base=base)
    try:
        yield base
    finally:
        locomotion._ctx = prev


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_walk_forward_rejects_nonfinite_distance(wired_base, bad):
    with pytest.raises(ValueError):
        locomotion.walk_forward(bad)
    # guard fired BEFORE any velocity command reached the actuator
    assert wired_base.set_velocity_calls == []


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_turn_rejects_nonfinite_angle(wired_base, bad):
    with pytest.raises(ValueError):
        locomotion.turn(bad)
    assert wired_base.set_velocity_calls == []


def test_walk_forward_accepts_finite_no_false_reject(wired_base):
    # start=(0,0,0) then pos=(99,0,0) => covered=99 >= 1 on the first loop pass
    assert locomotion.walk_forward(1.0) is True


def test_turn_accepts_finite_no_false_reject(wired_base):
    # start_heading=0 then current=9 => delta wrapped >= abs(1.0) immediately
    assert locomotion.turn(1.0) is True


# --------------------------------------------------------------------------- #
# Mirror-safety: every blocking locomotion primitive validates its threshold
# --------------------------------------------------------------------------- #
def test_blocking_primitives_call_the_guard():
    for name in ("walk_forward", "turn"):
        src = inspect.getsource(getattr(locomotion, name))
        assert "ensure_finite_travel" in src, (
            f"{name} does not validate its numeric threshold with "
            f"ensure_finite_travel — a NaN/inf target would drive motion for the "
            f"full timeout window (E191 finiteness vein)."
        )
