# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Single-waypoint-author rule — park the resident far_planner (RED first).

Field disaster 2026-07-14 evening: the resident far_planner still held a
stale goal (near home) and REPUBLISHED /way_point toward it forever — every
move_relative then fought it on the same waypoint channel (dog staggered
forward 3m in 24s; the next attempt spun in place because the stale goal sat
BEHIND). The status line even showed the smoking gun: 'RViz手动目标
(-0.08,-0.11)' that nobody clicked.

Rule pinned here: before ANY direct motion (navigate_to / rotate /
reverse_blind / dock_to) the driver PARKS the route planner — publishes
/goal_point at the CURRENT pose, which far_planner immediately treats as
reached and goes silent. Park frames echoing back on /way_point are
plumbing, not operator clicks.

ROS-free: mock node fixture (same as the rotate/dock suites).
"""

from __future__ import annotations

import math
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw import _FakeClock, _ros_module_stubs


@pytest.fixture
def park_hw(monkeypatch: pytest.MonkeyPatch):
    """(mod, hw, pubs, clk): pubs[topic] -> list of published (x, y)."""
    from zeno.hardware.ros2 import go2w_hw as mod

    node = MagicMock()
    node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock()
    raw: dict[str, MagicMock] = {}
    published: dict[str, list[tuple[float, float]]] = {}

    def _create_publisher(_t: Any, topic: str, *_a: Any, **_k: Any) -> MagicMock:
        p = MagicMock(name=f"pub{topic}")
        raw[topic] = p
        published.setdefault(topic, [])

        def _cap(m, _topic=topic):
            if hasattr(m, "point"):
                published[_topic].append((m.point.x, m.point.y))
            else:
                published[_topic].append((getattr(m.linear, "x", 0.0),
                                          getattr(m.linear, "y", 0.0)))

        p.publish.side_effect = _cap
        return p

    def _create_client(_t: Any, name: str, *_a: Any, **_k: Any) -> MagicMock:
        c = MagicMock(name=f"cli{name}")
        c.wait_for_service.return_value = True
        resp = MagicMock(); resp.success = True
        fut = MagicMock(); fut.result.return_value = resp
        c.call_async.return_value = fut
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
        yield mod, hw, published, clk


def test_navigate_parks_route_planner_before_own_waypoint(park_hw):
    mod, hw, pubs, _clk = park_hw
    hw._position = (2.0, 1.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.navigate_to(5.0, 1.0, timeout=0.5)
    assert pubs.get("/goal_point"), "far_planner must be parked (goal_point)"
    assert pubs["/goal_point"][0] == (pytest.approx(2.0), pytest.approx(1.0)), \
        "park goal = CURRENT pose (far_planner treats it as reached -> silent)"
    assert pubs["/way_point"], "own waypoint still published"


def test_rotate_and_reverse_park_the_route_planner(park_hw):
    mod, hw, pubs, _clk = park_hw
    hw._position = (1.0, 0.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.rotate(math.pi / 4)
        hw.reverse_blind(0.3)
    assert len(pubs.get("/goal_point", [])) >= 2, \
        "teleop motions must also silence the route planner"


def test_dock_parks_route_planner(park_hw):
    mod, hw, pubs, _clk = park_hw
    hw._position = (0.0, 0.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.dock_to(0.4, 0.0, timeout=5.0)
    assert pubs.get("/goal_point"), "docking must silence the route planner"


def test_park_echo_on_waypoint_is_not_an_operator_click(park_hw):
    """far_planner briefly republishes /way_point AT the park coords — those
    frames are plumbing, never an operator RViz goal."""
    mod, hw, pubs, _clk = park_hw
    hw._position = (2.0, 1.0, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.park_route_planner()

    class _Pt:
        pass

    msg = MagicMock()
    msg.point.x, msg.point.y = 2.0, 1.0  # far echoing the park goal
    hw._on_waypoint(msg)
    assert hw.external_goal_info() is None, \
        "park echo must not register as an external operator goal"


def test_park_without_node_is_safe():
    from zeno.hardware.ros2 import go2w_hw as mod

    with patch.dict("sys.modules", _ros_module_stubs()):
        hw = mod.Go2WHardware()
        hw.park_route_planner()  # disconnected: silent no-op, never raises
