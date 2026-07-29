# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real manip skill family — hermetic seam suite (Phase 4, 2026-07-29).

Covers the base-side seam into the Z-Mobile-manip task FSM: the thin ROS bridge
(parsing + the approach-reached LATCH), the approach-ONLY skill (auto-cancel at
the servo→grasp handoff so the arm never engages, base mutex, fail/timeout/abort
paths), manip_bringup/status/cancel, the approach_ready() verify oracle, the
local/ssh manip CLI transport, and the vocab↔skill consistency.

Hermetic: mock bridge / fake transport, NO ROS env, NO network, NO sim. The real
bridge's publish path (needs std_msgs) is exercised live by the downstream agent;
here we mock it. ROS is confirmed absent in this venv, so the bridge's send/cancel
take their fail-honest no-ROS branch.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from zeno.core.skill import SkillContext
from zeno.hardware.ros2.go2w_manip_bridge import (
    ARM_PHASES,
    HANDOFF_PHASES,
    Go2WManipBridge,
    ManipStatus,
)
from zeno.hardware.ros2.manip_transport import ManipTransport, manip_transport
from zeno.vcli.worlds import go2w_real_manip_skills as mod
from zeno.vcli.worlds.go2w_real_manip_skills import (
    RealApproachObjectSkill,
    RealManipBringupSkill,
    RealManipCancelSkill,
    RealManipStatusSkill,
)
from zeno.vcli.worlds.go2w_real_manip_verify import make_approach_ready


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------


class _FakeBase:
    """Minimal base carrying the manip mutex flag + a goal sweep recorder."""

    def __init__(self) -> None:
        self.manip_active = False
        self.cleared = 0

    def clear_all_goals(self) -> None:
        self.cleared += 1


class _MockBridge:
    """Stand-in Go2WManipBridge: scripted phases + the approach-reached latch."""

    def __init__(self, phases: list[str], connected: bool = True,
                 send_ok: bool = True, failure: str = "") -> None:
        self._phases = list(phases)
        self._i = 0
        self._last = phases[0] if phases else None
        self.is_connected = connected
        self._send_ok = send_ok
        self._failure = failure
        self.sent: list[str] = []
        self.cancels = 0
        self._reached = False
        self.base: Any = None
        self.busy_seen = False

    def connect(self) -> None:
        self.is_connected = True

    def send_task(self, instruction: str) -> bool:
        self.sent.append(instruction)
        self._reached = False
        return self._send_ok

    def cancel_task(self) -> bool:
        self.cancels += 1
        return True

    @property
    def phase(self) -> str | None:
        if self.base is not None and getattr(self.base, "manip_active", False):
            self.busy_seen = True
        if self._i < len(self._phases):
            self._last = self._phases[self._i]
            self._i += 1
        if self._last in HANDOFF_PHASES:
            self._reached = True
        return self._last

    @property
    def desired_camera_depth_m(self) -> float:
        return 0.55

    @property
    def coarse_ready(self) -> bool:
        return False

    def approach_reached(self) -> bool:
        return self._reached

    def status_snapshot(self) -> ManipStatus:
        return ManipStatus(
            connected=self.is_connected, phase=self._last, coarse_ready=False,
            desired_camera_depth_m=0.55, measured_base_linear_speed_mps=0.0,
            measured_base_angular_speed_rps=0.0, result="",
            failure=self._failure, approach_reached=self._reached,
            status_age_s=0.1, schema="z_manip.task_status.v1", raw={})


@pytest.fixture
def fast_cfg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink the poll cadence + timeout so blocking loops finish instantly."""
    monkeypatch.setattr(
        mod, "CFG", mod.ManipApproachConfig(poll_hz=1000.0, approach_timeout_s=5.0)
    )


def _ctx(base: Any, bridge: Any) -> SkillContext:
    return SkillContext(base=base, services={"manip": bridge})


# ---------------------------------------------------------------------------
# approach_object — the approach-ONLY skill
# ---------------------------------------------------------------------------


def test_approach_reaches_handoff_and_cancels_arm_free(fast_cfg: None) -> None:
    base = _FakeBase()
    bridge = _MockBridge(["grounding", "standoff", "visual_servo", "final_grounding"])
    bridge.base = base
    res = RealApproachObjectSkill().execute({"target": "红色杯子"}, _ctx(base, bridge))
    assert res.success, res.error_message
    assert res.result_data["verify_hint"] == "approach_ready()"
    assert res.result_data["arm_engaged"] is False
    # The task was sent and CANCELLED (approach-only guarantee) on the way out.
    assert bridge.sent == ["靠近红色杯子"]
    assert bridge.cancels >= 1, "must cancel at the handoff to stay arm-free"
    # Base mutex: flag was SET during the run and CLEARED after; goals swept.
    assert bridge.busy_seen is True
    assert base.manip_active is False
    assert base.cleared >= 2  # before + after


def test_approach_english_target_builds_english_instruction(fast_cfg: None) -> None:
    base = _FakeBase()
    bridge = _MockBridge(["final_grounding"])
    RealApproachObjectSkill().execute({"target": "metal bowl"}, _ctx(base, bridge))
    assert bridge.sent == ["approach the metal bowl"]


def test_approach_instruction_override_sent_verbatim(fast_cfg: None) -> None:
    base = _FakeBase()
    bridge = _MockBridge(["planning"])
    RealApproachObjectSkill().execute(
        {"target": "cup", "instruction": "go to the blue cup on the left"},
        _ctx(base, bridge))
    assert bridge.sent == ["go to the blue cup on the left"]


def test_approach_none_bridge_is_no_manip_stack() -> None:
    base = _FakeBase()
    res = RealApproachObjectSkill().execute(
        {"target": "cup"}, SkillContext(base=base, services={}))
    assert not res.success
    assert res.diagnosis_code == "no_manip_stack"
    assert base.manip_active is False  # never set when we bail before the task


def test_approach_disconnected_bridge_is_no_manip_stack(fast_cfg: None) -> None:
    bridge = _MockBridge(["grounding"], connected=False, send_ok=True)

    # connect() that never succeeds (stack down)
    def _no_connect() -> None:
        return None

    bridge.connect = _no_connect  # type: ignore[method-assign]
    res = RealApproachObjectSkill().execute({"target": "cup"}, _ctx(_FakeBase(), bridge))
    assert not res.success and res.diagnosis_code == "no_manip_stack"
    assert bridge.sent == []  # never sent a task to a down stack


def test_approach_missing_target_is_bad_params(fast_cfg: None) -> None:
    bridge = _MockBridge(["grounding"])
    res = RealApproachObjectSkill().execute({}, _ctx(_FakeBase(), bridge))
    assert not res.success and res.diagnosis_code == "bad_params"
    assert bridge.sent == []


def test_approach_fsm_failure_is_approach_failed(fast_cfg: None) -> None:
    base = _FakeBase()
    bridge = _MockBridge(["grounding", "failed"], failure="planning requires current joint feedback")
    res = RealApproachObjectSkill().execute({"target": "cup"}, _ctx(base, bridge))
    assert not res.success and res.diagnosis_code == "approach_failed"
    assert "joint feedback" in res.error_message
    assert bridge.cancels >= 1  # base zeroed even on failure
    assert base.manip_active is False


def test_approach_timeout_when_never_leaves_grounding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mod, "CFG", mod.ManipApproachConfig(poll_hz=1000.0, approach_timeout_s=0.05)
    )
    base = _FakeBase()
    bridge = _MockBridge(["grounding"])  # holds grounding forever
    res = RealApproachObjectSkill().execute({"target": "cup"}, _ctx(base, bridge))
    assert not res.success and res.diagnosis_code == "approach_timeout"
    assert bridge.cancels >= 1
    assert base.manip_active is False


def test_approach_hard_aborts_if_arm_phase_seen(fast_cfg: None) -> None:
    """Defense-in-depth: an arm phase must NEVER be reached (we cancel at the
    handoff), but if one is observed the skill aborts loud and cancels."""
    base = _FakeBase()
    bridge = _MockBridge(["grounding", "transit"])  # transit = first arm phase
    res = RealApproachObjectSkill().execute({"target": "cup"}, _ctx(base, bridge))
    assert not res.success and res.diagnosis_code == "manip_arm_phase"
    assert bridge.cancels >= 1
    assert base.manip_active is False


def test_approach_send_failure_is_task_send_failed(fast_cfg: None) -> None:
    base = _FakeBase()
    bridge = _MockBridge(["grounding"], send_ok=False)
    res = RealApproachObjectSkill().execute({"target": "cup"}, _ctx(base, bridge))
    assert not res.success and res.diagnosis_code == "task_send_failed"
    assert base.manip_active is False  # released in finally


# ---------------------------------------------------------------------------
# Base mutex — navigate / move_relative refuse a busy chassis
# ---------------------------------------------------------------------------


def test_navigate_refused_while_manip_active() -> None:
    from zeno.vcli.worlds.go2w_real_skills import RealNavigateSkill

    base = _FakeBase()
    base.manip_active = True
    res = RealNavigateSkill().execute({"x": 1.0, "y": 2.0}, SkillContext(base=base))
    assert not res.success and res.diagnosis_code == "manip_busy"


def test_move_relative_refused_while_manip_active() -> None:
    from zeno.vcli.worlds.go2w_real_skills import RealMoveRelativeSkill

    base = _FakeBase()
    base.manip_active = True
    res = RealMoveRelativeSkill().execute(
        {"distance": 1.0, "direction": "forward"}, SkillContext(base=base))
    assert not res.success and res.diagnosis_code == "manip_busy"


def test_navigate_allowed_when_not_manip_active() -> None:
    """The guard is fail-open: a base with the flag False/absent is unaffected."""
    from zeno.vcli.worlds.go2w_real_diag import _manip_busy_hint

    assert _manip_busy_hint(_FakeBase()) is None
    assert _manip_busy_hint(SimpleNamespace()) is None  # older driver, no attr


# ---------------------------------------------------------------------------
# manip_cancel / manip_status
# ---------------------------------------------------------------------------


def test_manip_cancel_sends_cancel_and_clears_mutex() -> None:
    base = _FakeBase()
    base.manip_active = True
    bridge = _MockBridge(["visual_servo"])
    res = RealManipCancelSkill().execute({}, _ctx(base, bridge))
    assert res.success
    assert bridge.cancels == 1
    assert base.manip_active is False


def test_manip_cancel_no_bridge_is_no_manip_stack() -> None:
    res = RealManipCancelSkill().execute({}, SkillContext(base=_FakeBase(), services={}))
    assert not res.success and res.diagnosis_code == "no_manip_stack"


def test_manip_status_reports_phase_from_bridge() -> None:
    bridge = _MockBridge(["visual_servo"])
    res = RealManipStatusSkill().execute({}, _ctx(_FakeBase(), bridge))
    assert res.success
    assert res.result_data["phase"] == "visual_servo"
    assert res.result_data["desired_camera_depth_m"] == 0.55
    assert res.result_data["approach_reached"] is False


def test_manip_status_no_bridge_is_no_manip_stack() -> None:
    res = RealManipStatusSkill().execute({}, SkillContext(base=None, services={}))
    assert not res.success and res.diagnosis_code == "no_manip_stack"


# ---------------------------------------------------------------------------
# approach_ready() verify oracle
# ---------------------------------------------------------------------------


def test_approach_ready_reads_bridge_latch() -> None:
    bridge = _MockBridge(["final_grounding"])
    bridge._reached = True
    agent = SimpleNamespace(_manip=bridge, _base=None)
    assert make_approach_ready(agent)() is True
    bridge._reached = False
    assert make_approach_ready(agent)() is False


def test_approach_ready_fail_safe_without_bridge() -> None:
    assert make_approach_ready(None)() is False
    assert make_approach_ready(SimpleNamespace(_base=None))() is False


def test_approach_ready_rides_the_base_seam() -> None:
    bridge = _MockBridge(["planning"])
    bridge._reached = True
    agent = SimpleNamespace(_base=SimpleNamespace(manip_bridge=bridge))
    assert make_approach_ready(agent)() is True


# ---------------------------------------------------------------------------
# manip_bringup — the CLI lifecycle skill
# ---------------------------------------------------------------------------


class _FakeTransport:
    def __init__(self, pre: str | None = None) -> None:
        self._pre = pre
        self.calls: list[tuple] = []

    def preflight(self) -> str | None:
        return self._pre

    def command_argv(self, subcmd: str, *a: Any) -> list[str]:
        self.calls.append((subcmd, *a))
        return ["bash", "/x/manip", subcmd, *[str(x) for x in a]]

    def describe(self) -> str:
        return "fake"


def _runner(rc: int = 0, out: str = "ok", err: str = ""):
    def run(argv: list[str], timeout: float) -> Any:
        return SimpleNamespace(returncode=rc, stdout=out, stderr=err)

    return run


@pytest.mark.parametrize("action,subcmd", [
    ("start", "bringup"), ("bringup", "bringup"),
    ("stop", "stop"), ("status", "status"),
])
def test_manip_bringup_action_maps_to_cli_subcommand(action: str, subcmd: str) -> None:
    tr = _FakeTransport()
    res = RealManipBringupSkill(runner=_runner(), transport=tr).execute({"action": action}, None)
    assert res.success, res.error_message
    assert tr.calls == [(subcmd,)]


def test_manip_bringup_defaults_to_status() -> None:
    tr = _FakeTransport()
    RealManipBringupSkill(runner=_runner(), transport=tr).execute({}, None)
    assert tr.calls == [("status",)]


def test_manip_bringup_rejects_unknown_action() -> None:
    tr = _FakeTransport()
    res = RealManipBringupSkill(runner=_runner(), transport=tr).execute(
        {"action": "grasp"}, None)
    assert not res.success and res.diagnosis_code == "bad_action"
    assert tr.calls == []  # never touched the CLI


def test_manip_bringup_preflight_failure_is_no_manip_stack() -> None:
    tr = _FakeTransport(pre="manip CLI not found at /x/manip")
    res = RealManipBringupSkill(runner=_runner(), transport=tr).execute(
        {"action": "start"}, None)
    assert not res.success and res.diagnosis_code == "no_manip_stack"
    assert tr.calls == []


def test_manip_bringup_nonzero_rc_is_cli_failed() -> None:
    tr = _FakeTransport()
    res = RealManipBringupSkill(runner=_runner(rc=3, err="boom"), transport=tr).execute(
        {"action": "start"}, None)
    assert not res.success and res.diagnosis_code == "manip_cli_failed"


# ---------------------------------------------------------------------------
# manip_transport — the local/ssh CLI seam
# ---------------------------------------------------------------------------


def test_transport_local_builds_bash_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GO2W_MANIP_TRANSPORT", "local")
    monkeypatch.setenv("GO2W_MANIP_CLI", "/opt/manip")
    tr = manip_transport()
    assert tr.mode == "local" and tr.is_remote is False
    assert tr.command_argv("status") == ["bash", "/opt/manip", "status"]


def test_transport_ssh_builds_ssh_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GO2W_MANIP_TRANSPORT", "ssh")
    monkeypatch.setenv("GO2W_MANIP_SSH_HOST", "workstation")
    monkeypatch.setenv("GO2W_MANIP_CLI_REMOTE", "~/m/manip")
    tr = manip_transport()
    assert tr.mode == "ssh" and tr.is_remote is True
    argv = tr.command_argv("bringup")
    assert argv[0] == "ssh" and argv[-2] == "workstation"
    # CLI path UNquoted (remote ~ expands); subcommand shell-quoted.
    assert argv[-1] == "bash ~/m/manip bringup"


def test_transport_ssh_preflight_requires_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GO2W_MANIP_SSH_HOST", raising=False)
    tr = ManipTransport("ssh", "~/m", host=None)
    assert tr.preflight() and "GO2W_MANIP_SSH_HOST" in tr.preflight()


def test_transport_local_preflight_flags_missing_cli() -> None:
    tr = ManipTransport("local", "/definitely/not/here/manip")
    msg = tr.preflight()
    assert msg and "not found" in msg


def test_transport_auto_picks_local_when_cli_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GO2W_MANIP_TRANSPORT", "auto")
    monkeypatch.setenv("GO2W_MANIP_CLI", __file__)  # a file that exists
    assert manip_transport().mode == "local"


# ---------------------------------------------------------------------------
# Go2WManipBridge — parsing + the approach-reached latch (no ROS)
# ---------------------------------------------------------------------------


def _status_msg(**fields: Any) -> SimpleNamespace:
    doc = {"schema": "z_manip.task_status.v1"}
    doc.update(fields)
    return SimpleNamespace(data=json.dumps(doc))


def test_bridge_parses_status_fields() -> None:
    b = Go2WManipBridge()
    b._on_status(_status_msg(
        phase="visual_servo", desired_camera_depth_m=0.55, coarse_nav_ready=True,
        result="", failure="",
        visual_search={"measured_base_linear_speed_mps": 0.02,
                       "measured_base_angular_speed_rps": 0.0}))
    assert b.phase == "visual_servo"
    assert b.desired_camera_depth_m == 0.55
    assert b.coarse_ready is True
    assert b.measured_base_linear_speed_mps == 0.02
    assert b.measured_base_angular_speed_rps == 0.0
    assert b.schema == "z_manip.task_status.v1"
    assert b.approach_reached() is False  # visual_servo is NOT a handoff phase


def test_bridge_latches_approach_reached_on_handoff() -> None:
    b = Go2WManipBridge()
    assert b.approach_reached() is False
    b._on_status(_status_msg(phase="final_grounding"))
    assert b.approach_reached() is True
    # Latch HOLDS even if a later frame reports a non-handoff phase.
    b._on_status(_status_msg(phase="grounding"))
    assert b.approach_reached() is True


def test_bridge_send_task_resets_the_latch() -> None:
    b = Go2WManipBridge()
    b._on_status(_status_msg(phase="planning"))
    assert b.approach_reached() is True
    # No publisher / no ROS -> send returns False, but the latch is reset first.
    assert b.send_task("approach the cup") is False
    assert b.approach_reached() is False


def test_bridge_coarse_ready_from_topic_or_doc() -> None:
    b = Go2WManipBridge()
    assert b.coarse_ready is False
    b._on_coarse_ready(SimpleNamespace(data=True))
    assert b.coarse_ready is True
    # And independently from the status doc field.
    b2 = Go2WManipBridge()
    b2._on_status(_status_msg(phase="near_grounding", coarse_nav_ready=True))
    assert b2.coarse_ready is True


def test_bridge_malformed_status_is_ignored() -> None:
    b = Go2WManipBridge()
    b._on_status(SimpleNamespace(data="not json{{"))
    assert b.phase is None
    assert b.status_age_s() is None


def test_bridge_snapshot_and_age() -> None:
    b = Go2WManipBridge()
    assert b.status_snapshot().phase is None
    assert b.status_snapshot().status_age_s is None
    b._on_status(_status_msg(phase="standoff", desired_camera_depth_m=0.6))
    snap = b.status_snapshot()
    assert snap.phase == "standoff" and snap.desired_camera_depth_m == 0.6
    assert snap.status_age_s is not None and snap.status_age_s >= 0.0


def test_bridge_publish_returns_false_without_connection() -> None:
    b = Go2WManipBridge()
    assert b.is_connected is False
    assert b.cancel_task() is False
    assert b.send_task("x") is False


# ---------------------------------------------------------------------------
# bug① — process-exit cancel: ordered before rclpy teardown, quiet on a dead
# context (no "rcl not initialized" noise), fires only for an in-flight task.
# ---------------------------------------------------------------------------

_BRIDGE_MOD = "zeno.hardware.ros2.go2w_manip_bridge"


class _RecordPub:
    """Recording publisher stand-in (counts publishes, keeps last msg.data)."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    def publish(self, msg: Any) -> None:
        self.published.append(getattr(msg, "data", msg))


@pytest.fixture
def fake_std_msgs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a minimal std_msgs.msg so the publish path runs without ROS."""
    import sys
    import types

    class _Bool:
        def __init__(self) -> None:
            self.data = False

    class _String:
        def __init__(self) -> None:
            self.data = ""

    pkg = types.ModuleType("std_msgs")
    msg = types.ModuleType("std_msgs.msg")
    msg.Bool = _Bool
    msg.String = _String
    pkg.msg = msg
    monkeypatch.setitem(sys.modules, "std_msgs", pkg)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", msg)


def test_bridge_cancel_quiet_when_context_down(
    monkeypatch: pytest.MonkeyPatch, fake_std_msgs: None
) -> None:
    # A dead rclpy context (interpreter-exit race) must make cancel_task a QUIET
    # no-op — return False WITHOUT publishing (so no C-layer "context invalid"
    # onto stderr), even though a publisher is installed.
    b = Go2WManipBridge()
    cancel_pub = _RecordPub()
    b._install_pubs_for_test(_RecordPub(), cancel_pub)
    monkeypatch.setattr(f"{_BRIDGE_MOD}._rclpy_ok", lambda: False)
    assert b.cancel_task() is False
    assert cancel_pub.published == []


def test_bridge_cancel_publishes_when_context_ok(
    monkeypatch: pytest.MonkeyPatch, fake_std_msgs: None
) -> None:
    b = Go2WManipBridge()
    cancel_pub = _RecordPub()
    b._install_pubs_for_test(_RecordPub(), cancel_pub)
    monkeypatch.setattr(f"{_BRIDGE_MOD}._rclpy_ok", lambda: True)
    assert b.cancel_task() is True
    assert cancel_pub.published == [True]


def test_bridge_exit_hook_cancels_inflight_task(
    monkeypatch: pytest.MonkeyPatch, fake_std_msgs: None
) -> None:
    # Simulate a live task then a process exit: the atexit hook sends ONE clean
    # cancel while the context is still up, and clears the in-flight flag so a
    # racing skill-finally cancel won't double-fire.
    b = Go2WManipBridge()
    req_pub, cancel_pub = _RecordPub(), _RecordPub()
    b._install_pubs_for_test(req_pub, cancel_pub)
    monkeypatch.setattr(f"{_BRIDGE_MOD}._rclpy_ok", lambda: True)
    monkeypatch.setattr(f"{_BRIDGE_MOD}.time", SimpleNamespace(
        sleep=lambda *_a, **_k: None, monotonic=lambda: 0.0))
    assert b.send_task("approach the cup") is True
    assert b._task_active is True
    b._atexit_cancel()
    assert cancel_pub.published == [True]
    assert b._task_active is False
    # Idempotent: a second hook call (or a skill-finally cancel) adds nothing.
    b._atexit_cancel()
    assert cancel_pub.published == [True]


def test_bridge_exit_hook_noop_without_inflight_task(
    monkeypatch: pytest.MonkeyPatch, fake_std_msgs: None
) -> None:
    b = Go2WManipBridge()
    cancel_pub = _RecordPub()
    b._install_pubs_for_test(_RecordPub(), cancel_pub)
    monkeypatch.setattr(f"{_BRIDGE_MOD}._rclpy_ok", lambda: True)
    # No task in flight -> the exit hook is a pure no-op (a clean run added no noise).
    b._atexit_cancel()
    assert cancel_pub.published == []


def test_bridge_exit_hook_skips_when_context_down(
    monkeypatch: pytest.MonkeyPatch, fake_std_msgs: None
) -> None:
    b = Go2WManipBridge()
    cancel_pub = _RecordPub()
    b._install_pubs_for_test(_RecordPub(), cancel_pub)
    b._task_active = True
    monkeypatch.setattr(f"{_BRIDGE_MOD}._rclpy_ok", lambda: False)
    b._atexit_cancel()  # context already down -> silent, no publish
    assert cancel_pub.published == []


def test_bridge_successful_cancel_clears_inflight_flag(
    monkeypatch: pytest.MonkeyPatch, fake_std_msgs: None
) -> None:
    # The normal skill-finally cancel clears the flag so the exit hook stays silent.
    b = Go2WManipBridge()
    cancel_pub = _RecordPub()
    b._install_pubs_for_test(_RecordPub(), cancel_pub)
    monkeypatch.setattr(f"{_BRIDGE_MOD}._rclpy_ok", lambda: True)
    b._task_active = True
    assert b.cancel_task() is True
    assert b._task_active is False
    b._atexit_cancel()
    assert cancel_pub.published == [True]  # only the explicit cancel, no exit dup


def test_bridge_speed_missing_is_none_and_toplevel_wins() -> None:
    b = Go2WManipBridge()
    b._on_status(_status_msg(phase="visual_search",
                             measured_base_linear_speed_mps=0.03))
    assert b.measured_base_linear_speed_mps == 0.03  # top-level read
    assert b.measured_base_angular_speed_rps is None  # absent -> None


def test_bridge_arm_phase_set_is_disjoint_from_handoff() -> None:
    """Sanity on the phase groupings the skill trusts: the handoff (cancel-here)
    phases and the arm (never-reach) phases must not overlap, and transit is the
    first arm phase."""
    assert not (HANDOFF_PHASES & ARM_PHASES)
    assert "transit" in ARM_PHASES
    assert "visual_servo" not in HANDOFF_PHASES and "visual_servo" not in ARM_PHASES


# ---------------------------------------------------------------------------
# Vocab ↔ skill consistency (engine preflight surface)
# ---------------------------------------------------------------------------


def test_manip_strategies_are_taught_and_resolve() -> None:
    from zeno.vcli.cognitive.strategy_selector import StrategySelector
    from zeno.vcli.cognitive.types import SubGoal
    from zeno.vcli.worlds import resolve_world_named

    world = resolve_world_named("go2w_real")
    reg = world.build_embodiment()._skill_registry
    sel = StrategySelector(skill_registry=reg, has_base=True)
    vocab = world.decompose_vocab()
    skills = set(reg.list_skills())
    for strat in ("approach_object_skill", "manip_bringup_skill",
                  "manip_status_skill", "manip_cancel_skill"):
        assert strat in vocab.strategies
        assert strat in vocab.strategy_descriptions
        r = sel.select(SubGoal(name="s", description="s", verify="True", strategy=strat))
        assert (r.executor_type, r.name in skills) == ("skill", True)


def test_approach_fewshot_and_verify_are_wired() -> None:
    from zeno.vcli.worlds import resolve_world_named
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES

    assert "approach_object_skill" in REAL_DECOMPOSE_EXAMPLES
    assert "approach_ready()" in REAL_DECOMPOSE_EXAMPLES
    vocab = resolve_world_named("go2w_real").decompose_vocab()
    assert "approach_ready" in vocab.verify_functions
    assert "approach_ready" in vocab.verify_fn_signatures


def test_manip_recovery_hints_present() -> None:
    from zeno.vcli.worlds import resolve_world_named

    hints = resolve_world_named("go2w_real").build_embodiment().recovery_hints()
    for code in ("no_manip_stack", "approach_failed", "manip_busy"):
        assert code in hints and hints[code]
