# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Go2WExploreManager — TARE autonomous exploration over nav.sh (v2 core).

Pure-unit: the overlay child is a FakeProc behind an injected Popen factory,
the hardware driver is a duck-typed fake, and the ROS message modules are
sys.modules stubs — nothing here touches rclpy, nav.sh, or the real robot.

Ground truth is the HONEST EXPLORE ORACLE (Inv-1: no /gt on hardware):

* TARE's own finish signal: the tare_planner node publishes std_msgs/Bool on
  ``/exploration_finish`` every planning cycle (sensor_coverage_planner_ground
  .cpp PublishExplorationState; topic param ``pub_exploration_finish_topic_``
  = 'exploration_finish', node launched with NO namespace, NO remaps) — data
  stays False while exploring and latches True when coverage completes;
* an INDEPENDENT progress metric: travel distance integrated from
  /state_estimation odometry, so verify can tell 'finished because done' from
  'finished because it never left the spawn';
* std_msgs/Float32 ``/runtime`` (TARE's total planning runtime, seconds).

State machine: idle -> launching -> exploring -> finishing -> stopped, with
orphan detection (child died unexpectedly => stopped + reason) and SIGINT-only
stop semantics (stop -> wait -> /nav_cancel -> resume GUARDED by the estop
latch: stop_explore must never silently release an operator's E-stop).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.unit.hardware.test_go2w_hw_overlay import FakePopenFactory, FakeProc


# ---------------------------------------------------------------------------
# Stubs — ROS module fakes + a duck-typed Go2WHardware
# ---------------------------------------------------------------------------


def _ros_module_stubs() -> dict[str, Any]:
    return {
        "rclpy": MagicMock(),
        "rclpy.qos": MagicMock(),
        "std_msgs": MagicMock(),
        "std_msgs.msg": MagicMock(),
        "nav_msgs": MagicMock(),
        "nav_msgs.msg": MagicMock(),
    }


class FakeHW:
    """Duck-typed Go2WHardware: node factory + safety triggers the manager uses."""

    def __init__(self, connected: bool = True, connect_heals: bool = False) -> None:
        self.is_connected = connected
        self._connect_heals = connect_heals
        self.connect_calls = 0
        self._node = MagicMock()
        self.estop_latched = False
        self.nav_cancel = MagicMock(return_value=True)
        self.estop_release = MagicMock(return_value=True)

    def connect(self) -> None:
        self.connect_calls += 1
        if self._connect_heals:
            self.is_connected = True


def _bool_msg(data: bool) -> Any:
    return SimpleNamespace(data=data)


def _odom_msg(x: float, y: float) -> Any:
    pos = SimpleNamespace(x=x, y=y, z=0.0)
    return SimpleNamespace(pose=SimpleNamespace(pose=SimpleNamespace(position=pos)))


def _mgr(tmp_path: Path, hw: FakeHW | None = None, proc: FakeProc | None = None):
    """Build a manager wired to a fake hw + fake child; return (mgr, hw, factory)."""
    from zeno.hardware.ros2.go2w_hw_explore import ExploreConfig, Go2WExploreManager

    nav = tmp_path / "nav.sh"
    nav.write_text("#!/usr/bin/env bash\n")
    factory = FakePopenFactory(proc)
    hw = hw if hw is not None else FakeHW()
    cfg = ExploreConfig(nav_sh=str(nav), stop_grace_s=0.01)
    mgr = Go2WExploreManager(hw, config=cfg, popen_factory=factory)
    return mgr, hw, factory


def _started(tmp_path: Path, hw: FakeHW | None = None, proc: FakeProc | None = None,
             scenario: str = "indoor_small"):
    """A manager already launched (inside the ROS stubs); returns callbacks too."""
    mgr, hw, factory = _mgr(tmp_path, hw=hw, proc=proc)
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok, msg = mgr.start_explore(scenario)
    assert ok is True, msg
    return mgr, hw, factory


def _sub_callback(hw: FakeHW, topic: str):
    """Extract the subscription callback the manager registered for *topic*."""
    for call in hw._node.create_subscription.call_args_list:
        if call.args[1] == topic:
            return call.args[2]
    raise AssertionError(f"no subscription created for {topic}")


# ---------------------------------------------------------------------------
# Import + construction — offline-safe, no ROS env
# ---------------------------------------------------------------------------


def test_module_imports_and_constructs_without_ros() -> None:
    from zeno.hardware.ros2.go2w_hw_explore import Go2WExploreManager

    mgr = Go2WExploreManager(None)  # no hardware at all — still constructible
    assert mgr.state() == "idle"
    assert mgr.explore_finished() is False
    assert mgr.explored_progress() == 0.0


def test_finish_topic_is_tares_exploration_finish() -> None:
    """The oracle listens on the topic TARE actually publishes (source-verified:
    'exploration_finish' relative name, node has no namespace => absolute)."""
    from zeno.hardware.ros2 import go2w_hw_explore as mod

    assert mod.Go2WExploreManager.FINISH_TOPIC == "/exploration_finish"
    assert mod.Go2WExploreManager.RUNTIME_TOPIC == "/runtime"
    assert mod.Go2WExploreManager.ODOM_TOPIC == "/state_estimation"


# ---------------------------------------------------------------------------
# start_explore — connected-driver gate, oracle attach, scenario passthrough
# ---------------------------------------------------------------------------


def test_start_requires_connected_driver_but_tries_to_heal(tmp_path: Path) -> None:
    """A disconnected driver refuses to launch (the oracle would be blind) after
    one connect() heal attempt; nothing is spawned."""
    hw = FakeHW(connected=False, connect_heals=False)
    mgr, hw, factory = _mgr(tmp_path, hw=hw)

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok, msg = mgr.start_explore("indoor_small")

    assert ok is False
    assert hw.connect_calls == 1, "start must attempt a connect() heal first"
    assert not factory.calls, "no overlay may launch with a blind oracle"
    assert mgr.state() == "idle"


def test_start_heals_disconnected_driver_then_launches(tmp_path: Path) -> None:
    hw = FakeHW(connected=False, connect_heals=True)
    mgr, hw, factory = _mgr(tmp_path, hw=hw)

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok, _ = mgr.start_explore("indoor_small")

    assert ok is True
    assert mgr.state() == "launching"


def test_start_launches_child_and_attaches_oracle(tmp_path: Path) -> None:
    """start_explore spawns ``bash nav.sh explore <scenario>`` and subscribes the
    finish/runtime/odometry oracle topics on the driver's node."""
    mgr, hw, factory = _started(tmp_path, scenario="indoor_large")

    argv, _ = factory.calls[0]
    assert argv[2:] == ["explore", "indoor_large"]
    topics = {c.args[1] for c in hw._node.create_subscription.call_args_list}
    assert {"/exploration_finish", "/runtime", "/state_estimation"} <= topics
    st = mgr.status()
    assert st.state == "launching"
    assert st.scenario == "indoor_large"
    assert st.pid == factory.proc.pid
    assert st.oracle_attached is True


def test_start_rejects_unknown_scenario(tmp_path: Path) -> None:
    """Scenario names map to TARE config yamls — an unknown one fails loud
    BEFORE spawning a child that would just crash."""
    mgr, _hw, factory = _mgr(tmp_path)

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok, msg = mgr.start_explore("moon_base")

    assert ok is False
    assert "moon_base" in msg
    assert not factory.calls


def test_double_start_refused_while_active(tmp_path: Path) -> None:
    mgr, _hw, factory = _started(tmp_path)

    with patch.dict("sys.modules", _ros_module_stubs()):
        ok, msg = mgr.start_explore("indoor_small")

    assert ok is False
    assert len(factory.calls) == 1


# ---------------------------------------------------------------------------
# Finish-topic handling — launching -> exploring -> finishing
# ---------------------------------------------------------------------------


def test_finish_false_confirms_exploring(tmp_path: Path) -> None:
    """TARE publishes finish=False every cycle while exploring: the first one is
    the liveness proof that moves launching -> exploring."""
    mgr, hw, _factory = _started(tmp_path)
    on_finish = _sub_callback(hw, "/exploration_finish")

    on_finish(_bool_msg(False))

    assert mgr.state() == "exploring"
    assert mgr.explore_finished() is False


def test_finish_true_latches_finished_and_moves_to_finishing(tmp_path: Path) -> None:
    mgr, hw, _factory = _started(tmp_path)
    on_finish = _sub_callback(hw, "/exploration_finish")

    on_finish(_bool_msg(False))
    on_finish(_bool_msg(True))

    assert mgr.state() == "finishing"
    assert mgr.explore_finished() is True
    # Later False frames must not un-finish (TARE latches the flag; so do we).
    on_finish(_bool_msg(False))
    assert mgr.explore_finished() is True


def test_stale_finish_after_stop_is_ignored(tmp_path: Path) -> None:
    """A finish=True that arrives after the session stopped must not fabricate a
    finished verdict for a session that never finished."""
    mgr, hw, _factory = _started(tmp_path)
    on_finish = _sub_callback(hw, "/exploration_finish")
    mgr.stop_explore()

    on_finish(_bool_msg(True))

    assert mgr.state() == "stopped"
    assert mgr.explore_finished() is False


def test_runtime_topic_recorded_in_status(tmp_path: Path) -> None:
    mgr, hw, _factory = _started(tmp_path)
    on_runtime = _sub_callback(hw, "/runtime")

    on_runtime(SimpleNamespace(data=12.5))

    assert mgr.status().runtime_s == pytest.approx(12.5)


# ---------------------------------------------------------------------------
# Independent progress oracle — odometry travel distance
# ---------------------------------------------------------------------------


def test_explored_progress_integrates_odometry_travel(tmp_path: Path) -> None:
    mgr, hw, _factory = _started(tmp_path)
    on_odom = _sub_callback(hw, "/state_estimation")

    on_odom(_odom_msg(0.0, 0.0))
    on_odom(_odom_msg(1.0, 0.0))
    on_odom(_odom_msg(1.0, 2.0))

    assert mgr.explored_progress() == pytest.approx(3.0)


def test_explored_progress_is_monotone_and_freezes_after_stop(tmp_path: Path) -> None:
    """The metric never decreases, and a stopped session's progress is frozen —
    it describes THAT explore run, not whatever moves the robot later."""
    mgr, hw, _factory = _started(tmp_path)
    on_odom = _sub_callback(hw, "/state_estimation")
    on_odom(_odom_msg(0.0, 0.0))
    on_odom(_odom_msg(2.0, 0.0))
    before = mgr.explored_progress()
    assert before == pytest.approx(2.0)

    mgr.stop_explore()
    on_odom(_odom_msg(10.0, 0.0))

    assert mgr.explored_progress() == pytest.approx(before)


def test_finished_but_stuck_at_spawn_is_distinguishable(tmp_path: Path) -> None:
    """THE honest-oracle case: TARE can claim finished while the robot never left
    the spawn (e.g. fully 'covered' a degenerate map). explore_finished() is True
    but explored_progress() stays ~0 — verify can and must tell them apart."""
    mgr, hw, _factory = _started(tmp_path)
    on_finish = _sub_callback(hw, "/exploration_finish")
    on_odom = _sub_callback(hw, "/state_estimation")

    on_odom(_odom_msg(0.0, 0.0))
    on_odom(_odom_msg(0.005, 0.0))  # odom jitter only — no real travel
    on_finish(_bool_msg(True))

    assert mgr.explore_finished() is True
    assert mgr.explored_progress() == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Orphan detection — the child dying is a state transition, not a mystery
# ---------------------------------------------------------------------------


def test_child_unexpected_death_flags_stopped_with_reason(tmp_path: Path) -> None:
    mgr, _hw, factory = _started(tmp_path)

    factory.proc.die(1)  # e.g. nav.sh require_stack failed inside the overlay

    assert mgr.state() == "stopped"
    st = mgr.status()
    assert "unexpected" in st.reason.lower()
    assert "1" in st.reason
    assert mgr.explore_finished() is False


def test_orphan_death_allows_restart(tmp_path: Path) -> None:
    mgr, _hw, factory = _started(tmp_path)
    factory.proc.die(1)
    assert mgr.state() == "stopped"

    factory.proc = FakeProc(pid=5001)
    with patch.dict("sys.modules", _ros_module_stubs()):
        ok, _ = mgr.start_explore("indoor_small")

    assert ok is True
    assert mgr.state() == "launching"
    assert mgr.status().reason == ""


