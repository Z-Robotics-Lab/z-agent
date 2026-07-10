# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""World-level operator-interrupt hook (Ctrl+C during a blocking turn)."""

from __future__ import annotations

from types import SimpleNamespace


class _HW:
    def __init__(self):
        self.cancelled = 0
        self.nav_cancels = 0

    def cancel_navigation(self):
        self.cancelled += 1

    def nav_cancel(self):
        self.nav_cancels += 1
        return True


def test_world_interrupt_hook_cancels_and_reports():
    from zeno.vcli.worlds import resolve_world_named
    world = resolve_world_named("go2w_real")
    hw = _HW()
    agent = SimpleNamespace(_base=hw)
    msg = world.on_operator_interrupt(agent)
    assert hw.cancelled >= 1
    assert isinstance(msg, str) and "stop" in msg.lower()


def test_world_interrupt_hook_safe_without_base():
    from zeno.vcli.worlds import resolve_world_named
    world = resolve_world_named("go2w_real")
    msg = world.on_operator_interrupt(SimpleNamespace(_base=None))
    assert isinstance(msg, str)  # never raises


def test_stop_skill_also_cancels_blocking_navigate():
    from zeno.vcli.worlds.go2w_real_skills import RealStopSkill
    hw = _HW()
    hw.estop = lambda: True
    ctx = SimpleNamespace(base=hw, services={})
    RealStopSkill().execute({}, ctx)
    assert hw.cancelled >= 1  # unwinds a concurrent navigate loop
