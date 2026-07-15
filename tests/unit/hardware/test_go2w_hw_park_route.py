# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""far_planner is the single /way_point author — how the driver cooperates.

History (both regimes bag-pinned):
* 2026-07-14: the resident far_planner held a stale goal and REPUBLISHED
  /way_point toward it forever, so every direct move fought it. First fix:
  PARK far_planner (publish /goal_point=current pose) before our own /way_point.
* 2026-07-15 bag: park-before-navigate BACKFIRES. A parked far_planner
  republishes /way_point at ~current pose within 0.1s and OVERWRITES our target
  (2465 zero-length paths vs 19 real; 往前走2米 frozen at the origin).

Fix B pinned here:
* navigate_to ROUTES THROUGH far_planner when it is subscribed to /goal_point —
  publish the TARGET on /goal_point, let far_planner plan + own /way_point (we do
  NOT publish /way_point). No far_planner subscribed -> direct /way_point
  fallback. On stop/stall/timeout (routed) we park far_planner to halt it.
* TELEOP motions (rotate / reverse_blind / dock_to) STILL park far_planner up
  front — they drive on /teleop_cmd_vel, so there is no /way_point two-writer
  fight; parking just stops far_planner driving underneath the teleop.
* park_route_planner + its /way_point echo-suppression are unchanged.

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
        hw._operator_override_enabled = True  # fixtures test the override LOGIC
        yield mod, hw, published, clk


def test_navigate_routes_via_far_planner_goal_point(park_hw):
    """Fix B: with far_planner subscribed, navigate publishes the TARGET on
    /goal_point (far_planner routes + owns /way_point) — NOT a park-at-current,
    and NOT our own /way_point. Reverses the 2026-07-14 park-before rule the bag
    proved backfired."""
    mod, hw, pubs, _clk = park_hw
    hw._position = (2.0, 1.0, 0.0)
    hw._goalpoint_pub.get_subscription_count.return_value = 1  # far_planner present
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.navigate_to(5.0, 1.0, timeout=0.5)
    assert pubs.get("/goal_point"), "goal must be routed through far_planner"
    assert pubs["/goal_point"][0] == (pytest.approx(5.0), pytest.approx(1.0)), \
        "/goal_point carries the TARGET (not current pose — no park-before)"
    assert not pubs.get("/way_point"), \
        "we must NOT publish /way_point — far_planner owns it (single author)"


def test_navigate_falls_back_to_waypoint_without_far_planner(park_hw):
    """No far_planner subscribed (fresh-mapping) -> direct /way_point, nobody to
    fight; the TARGET is never routed via /goal_point."""
    mod, hw, pubs, _clk = park_hw
    hw._position = (2.0, 1.0, 0.0)
    hw._goalpoint_pub.get_subscription_count.return_value = 0  # no far_planner
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.navigate_to(5.0, 1.0, timeout=0.5)
    assert pubs.get("/way_point"), "fallback: publish our own /way_point"
    assert pubs["/way_point"][0] == (pytest.approx(5.0), pytest.approx(1.0))
    assert (pytest.approx(5.0), pytest.approx(1.0)) not in pubs.get("/goal_point", []), \
        "no far_planner -> the target is never routed via /goal_point"


def test_navigate_parks_far_planner_on_timeout(park_hw):
    """A routed goal that never arrives -> on stall/timeout we park far_planner
    (goal = CURRENT pose) so it does not keep driving to the abandoned goal."""
    mod, hw, pubs, _clk = park_hw
    hw._position = (2.0, 1.0, 0.0)  # never moves -> never arrives
    hw._goalpoint_pub.get_subscription_count.return_value = 1
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.navigate_to(5.0, 1.0, timeout=0.5)
    gp = pubs.get("/goal_point", [])
    assert gp[0] == (pytest.approx(5.0), pytest.approx(1.0)), "first: the TARGET"
    assert (pytest.approx(2.0), pytest.approx(1.0)) in gp, \
        "then a park at CURRENT pose halts far_planner (reached -> silent)"


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


def test_routed_far_reach_counts_as_arrival_with_odom_sanity(park_hw):
    """Smoothness (2026-07-15): routed via far_planner, its own reach oracle +
    odometry within FAR_REACH_RADIUS_M ends the drive as arrived — even past
    ARRIVAL_RADIUS_M (far_planner's arrival radius can exceed ours). This is what
    keeps 'walk to the marker' from false-aborting into a route_via skill-hop."""
    mod, hw, _pubs, clk = park_hw
    hw._position = (4.3, 0.0, 0.0)  # 0.7m from goal: past ARRIVAL (0.4), within FAR_REACH (1.0)
    hw._goalpoint_pub.get_subscription_count.return_value = 1  # routed
    hw._far_reach = True
    hw._far_reach_ts = clk.monotonic()  # fresh
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(5.0, 0.0, timeout=5.0)
    assert ok is True, "far_planner reach + odom-close must count as arrival"


def test_routed_far_reach_alone_is_not_arrival_when_odom_far(park_hw):
    """Inv-1 moat: far_reach is NEVER the sole arrival oracle. With odometry far
    from the goal, a stale / other-goal reach frame cannot fake arrival."""
    mod, hw, _pubs, clk = park_hw
    hw._position = (0.0, 0.0, 0.0)  # 5m from goal, never moves
    hw._goalpoint_pub.get_subscription_count.return_value = 1
    hw._far_reach = True
    hw._far_reach_ts = clk.monotonic()
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(5.0, 0.0, timeout=1.0)
    assert ok is False, "far_reach with odom 5m away must NOT count as arrival"


def test_routed_stall_re_nudges_far_planner_instead_of_aborting(park_hw):
    """Owner 2026-07-15: a routed drive must NOT abort on stall (that bubbles
    failure to the agent, which re-plans — the '走几步停下来重新plan' churn). It
    RE-NUDGES far_planner (re-publishes the goal for a fresh route) and keeps
    driving in the SAME call; only MAX_RENUDGE / overall timeout ends it."""
    mod, hw, pubs, _clk = park_hw
    HW = mod.Go2WHardware
    hw._position = (0.0, 0.0, 0.0)  # frozen: never progresses -> perpetual stall
    hw._goalpoint_pub.get_subscription_count.return_value = 1  # routed
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok = hw.navigate_to(5.0, 0.0, timeout=HW.ROUTED_RENUDGE_S * 3)
    target_pubs = [g for g in pubs.get("/goal_point", [])
                   if g == (pytest.approx(5.0), pytest.approx(0.0))]
    assert len(target_pubs) >= 2, \
        "routed stall must RE-NUDGE (re-publish the goal), not abort on first stall"
    assert ok is False, "a perpetually-frozen goal still fails honestly (timeout)"


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


def test_park_echo_survives_far_planner_forever_republish(park_hw):
    """far_planner republishes the park goal FOREVER (its own docstring). The
    park-echo suppression must NOT expire on a timer — a /way_point matching the
    park coords is plumbing no matter how long after the park.

    Field 2026-07-14 (owner RViz): the old 5s window let a stale park echo (which
    far_planner keeps emitting) flip to a phantom operator goal after 5s, so
    navigate_to yielded to its OWN park point (-0.27,-0.04) forever — every
    '前进2米' wedged in a '操作者手动指定' yield loop the operator never triggered.
    """
    mod, hw, _pubs, clk = park_hw
    hw._position = (-0.27, -0.04, 0.0)
    with patch.dict("sys.modules", _ros_module_stubs()):
        hw.park_route_planner()
    clk.sleep(6.0)  # far past the OLD 5s park-echo window
    msg = MagicMock()
    msg.point.x, msg.point.y = -0.27, -0.04  # far_planner STILL republishing park goal
    hw._on_waypoint(msg)
    assert hw.external_goal_info() is None, \
        "far_planner's forever-republished park echo must never become external"
