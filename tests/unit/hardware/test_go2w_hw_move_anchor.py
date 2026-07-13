# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WHardware move anchor — the moved() oracle anchors on the DRIVER (RED first).

Twin of the 2026-07-13 double-turn fix (``rotate_anchor_yaw``): verify runs
AFTER the skill, so make_moved()'s first-verify-call origin capture samples the
POST-motion pose and grades False — and the model re-runs the walk. moved() is
strictly worse than turned() was: its first call returns False BY CONSTRUCTION
(origin capture), and because the verifier namespace is built once per session,
every later check grades displacement from a session-old origin — a failed walk
can fake-pass off motion that happened steps earlier.

Contract pinned here (mirror of rotate_anchor_yaw):
* navigate_to() samples get_position() into ``move_anchor_xy`` at command
  start, AFTER the guards — a refused command (non-finite goal, not connected)
  never re-anchors. The actor can trigger a move but cannot author either side
  of the compare (Inv-1).
* walk() (direct teleop displacement) anchors the same way at command start.
* rotate() must NOT touch the move anchor — an in-place turn between a walk
  and its verify must not erase what the walk did.

ROS-free like test_go2w_hw.py: mocked node via _install_node_for_test, stubbed
ROS modules, deterministic fake clock (no real sleeps).
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw import _FakeClock, _ros_module_stubs


# ---------------------------------------------------------------------------
# Fixture — a mock-wired driver + captured publishers + fake clock
# ---------------------------------------------------------------------------


@pytest.fixture
def anchor_hw(monkeypatch: pytest.MonkeyPatch):
    """(mod, hw, pubs, clk): pubs maps topic -> MagicMock publisher."""
    from zeno.hardware.ros2 import go2w_hw as mod

    node = MagicMock()
    node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock()
    pubs: dict[str, MagicMock] = {}

    def _create_publisher(_t: Any, topic: str, *_a: Any, **_k: Any) -> MagicMock:
        p = MagicMock(name=f"pub{topic}")
        pubs[topic] = p
        return p

    def _create_client(_t: Any, name: str, *_a: Any, **_k: Any) -> MagicMock:
        c = MagicMock(name=f"cli{name}")
        c.wait_for_service.return_value = True
        resp = MagicMock()
        resp.success = True
        future = MagicMock()
        future.result.return_value = resp
        c.call_async.return_value = future
        return c

    node.create_publisher.side_effect = _create_publisher
    node.create_client.side_effect = _create_client
    node.create_subscription = MagicMock()
    monkeypatch.setattr(mod, "get_ros2_runtime", lambda: MagicMock())

    clk = _FakeClock()
    monkeypatch.setattr(mod.time, "monotonic", clk.monotonic)
    monkeypatch.setattr(mod.time, "sleep", clk.sleep)

    with patch.dict("sys.modules", _ros_module_stubs()):
        hw = mod.Go2WHardware()
        hw._install_node_for_test(node)
        yield mod, hw, pubs, clk


# ---------------------------------------------------------------------------
# navigate_to — anchors the PRE-motion position, after the guards
# ---------------------------------------------------------------------------


def test_no_move_anchor_before_any_move_command(anchor_hw) -> None:
    """A fresh driver has no move anchor — moved() must grade False until a
    move is actually commanded (no origin capture on the verify side)."""
    _mod, hw, _pubs, _clk = anchor_hw
    assert hw.move_anchor_xy is None


def test_navigate_records_position_anchor_at_command_start(anchor_hw) -> None:
    """navigate_to() samples get_position() into ``move_anchor_xy`` before the
    poll loop — the moved() oracle grades against it. The anchor must be the
    PRE-motion pose even though verify only runs after arrival (the exact
    ordering that broke turned() in the 2026-07-13 field trace)."""
    _mod, hw, pubs, _clk = anchor_hw
    hw._position = (1.0, 2.0, 0.0)

    # The moment the waypoint goes out, the "robot" teleports to the goal —
    # so the poll loop arrives on its first check, like a completed walk.
    def _teleport(_msg: Any) -> None:
        hw._position = (5.0, 2.0, 0.0)

    pubs["/way_point"].publish.side_effect = _teleport

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(5.0, 2.0, timeout=2.0, poll_hz=50.0)

    assert ok is True
    assert hw.move_anchor_xy == (pytest.approx(1.0), pytest.approx(2.0)), (
        "the anchor must be the position at command START, not post-motion"
    )


def test_navigate_reanchors_per_command(anchor_hw) -> None:
    """Each navigate_to() re-anchors: moved() grades the LAST move command."""
    _mod, hw, pubs, _clk = anchor_hw

    def _teleport_to_goal(msg: Any) -> None:
        hw._position = (float(msg.point.x), float(msg.point.y), 0.0)

    pubs["/way_point"].publish.side_effect = _teleport_to_goal

    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.navigate_to(4.0, 0.0, timeout=2.0, poll_hz=50.0) is True
        assert hw.navigate_to(4.5, 0.0, timeout=2.0, poll_hz=50.0) is True

    assert hw.move_anchor_xy == (pytest.approx(4.0), pytest.approx(0.0))


def test_navigate_nonfinite_goal_does_not_anchor(anchor_hw) -> None:
    """A NaN/inf goal fails loud BEFORE anchoring — a refused command must
    never re-anchor the oracle (it could fake-pass or fake-fail a later
    check, same rule as rotate's estop refusal)."""
    _mod, hw, _pubs, _clk = anchor_hw
    with patch.dict("sys.modules", _ros_module_stubs()):
        with pytest.raises(ValueError):
            hw.navigate_to(float("nan"), 3.0)
    assert hw.move_anchor_xy is None


def test_navigate_offline_refusal_does_not_anchor() -> None:
    """A disconnected driver refuses navigation (False) without anchoring."""
    from zeno.hardware.ros2.go2w_hw import Go2WHardware

    hw = Go2WHardware()
    assert hw.navigate_to(1.0, 1.0, timeout=0.1) is False
    assert hw.move_anchor_xy is None


# ---------------------------------------------------------------------------
# walk — the other displacement command anchors too; rotate must not
# ---------------------------------------------------------------------------


def test_walk_records_position_anchor_at_command_start(anchor_hw) -> None:
    """walk() (direct /teleop_cmd_vel displacement) anchors like navigate_to —
    any future teleop-driven path gets the same honest moved() grading."""
    _mod, hw, _pubs, _clk = anchor_hw
    hw._position = (3.0, 4.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.walk(vx=0.3, duration=0.6) is True
    assert hw.move_anchor_xy == (pytest.approx(3.0), pytest.approx(4.0))


def test_rotate_does_not_touch_move_anchor(anchor_hw) -> None:
    """An in-place rotation between a walk and its verify must not erase the
    walk's anchor — rotate is not a displacement command."""
    _mod, hw, _pubs, _clk = anchor_hw
    hw._position = (3.0, 4.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        assert hw.walk(vx=0.3, duration=0.6) is True
        hw.rotate(math.pi / 2, yaw_rate=0.5)
    assert hw.move_anchor_xy == (pytest.approx(3.0), pytest.approx(4.0))
