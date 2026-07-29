# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real manip skills — approach_object / manip_bringup / manip_status /
manip_cancel, the base-side seam into the Z-Mobile-manip task FSM.

These skills let the agent DRIVE the mobile-manipulation stack without ever
crossing the arm red line (current phase: base-only). They talk to the FSM
through two transport-agnostic seams:

  * ``context.services['manip']`` (rides the driver as ``base.manip_bridge``) — a
    :class:`~zeno.hardware.ros2.go2w_manip_bridge.Go2WManipBridge` (three
    std_msgs topics; NO can0/arm/executor), for request/cancel/status.
  * :func:`~zeno.hardware.ros2.manip_transport.manip_transport` — the local/ssh
    ``manip`` operator CLI, for component lifecycle (arm-safe by construction:
    that CLI can never actuate the manipulator).

APPROACH-ONLY GUARANTEE (Inv-1 + the arm red line). The FSM has NO
approach-only / no-grasp mode: a task request runs find→approach→grasp→place.
``approach_object`` therefore watches the phase and, the instant the base reaches
the servo→grasp HANDOFF (``final_grounding`` / ``wait_fresh_observation`` /
``planning`` — base stopped at the standoff, perception/compute only, before the
FIRST arm phase ``transit``), it CANCELS. The cancel fires in a ``finally`` on
EVERY exit path (reached / failed / timeout / abort), so the run is provably
arm-free and the base is always zeroed on the way out. Success is graded by the
FSM-latched ``approach_ready()`` oracle, never by perception.

BASE MUTEX (protocol level, this phase): before sending a task the skill clears
any active nav goal (``clear_all_goals``) and sets ``base.manip_active`` so the
navigate / move_relative skills refuse to drive the same chassis concurrently;
the flag is cleared and goals swept again on exit.

Split per the repo rule (files < 400 lines); registered at the skills extension
marker in ``go2w_real.py``; strategies ``approach_object_skill`` /
``manip_bringup_skill`` / ``manip_status_skill`` / ``manip_cancel_skill``.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.hardware.ros2.go2w_manip_bridge import (
    ARM_PHASES,
    CANCELED_PHASE,
    HANDOFF_PHASES,
    TERMINAL_FAIL_PHASES,
)
from zeno.hardware.ros2.manip_transport import manip_transport
from zeno.vcli.worlds.go2w_real_diag import oplog
from zeno.vcli.worlds.go2w_real_skills import _base_of

_SENTINEL: object = object()

#: The Z-Manip planning workbench UI (go2w_planning_control.py on the 4090). The
#: bringup reply ALWAYS surfaces this on success so the operator can open it.
MANIP_UI_URL: str = "http://127.0.0.1:8766"

_NO_STACK_MSG = (
    "manip ROS bridge is not connected — the Z-Mobile-manip task graph is not "
    "reachable on domain 20. Bring it up with manip_bringup(action='start'), "
    "wait for the components, then retry."
)

#: Recovery hint when the NUC base chain (reactive-live) is not up: approach needs
#: something to consume /cmd_vel or the FSM servos into the void (no motion).
_NO_BASE_CHAIN_MSG = (
    "the NUC base chain (reactive-live) is not up, so an approach would servo "
    "into a chassis that cannot move. This is a SEPARATE, motion-enabling step: "
    "run manip_bringup(action='start_base') (operator beside the E-stop), confirm "
    "it is healthy, then retry approach_object."
)


@dataclass(frozen=True)
class ManipApproachConfig:
    """Immutable knobs for the approach skill (additive-only, Inv-7)."""

    poll_hz: float = 1.0            # phase-poll cadence (1-2 s per the red lines)
    approach_timeout_s: float = 120.0  # single-attempt cap (red line: <= 120 s)


CFG = ManipApproachConfig()


def _manip_of(context: Any) -> Any:
    """Return the manip bridge from a SkillContext (services seam, then driver).

    The embodiment publishes it as the 'manip' service; VGG GoalExecutor
    contexts carry no world services, so it also rides the driver
    (``base.manip_bridge``) — the same two-path seam as explore/route/viz.
    """
    if context is None:
        return None
    services = getattr(context, "services", None) or {}
    bridge = services.get("manip")
    if bridge is not None:
        return bridge
    return getattr(getattr(context, "base", None), "manip_bridge", None)


def _approach_instruction(target: str) -> str:
    """Build the RAW-NL task instruction the FSM grounds against.

    The FSM uses the whole string as the instruction and its grounder extracts
    the target noun (bilingual lexicon + VLM fallback, recon Q5). We only need to
    name the target clearly; the verb is irrelevant to grounding.
    """
    t = target.strip()
    if any("一" <= ch <= "鿿" for ch in t):
        return f"靠近{t}"
    return f"approach the {t}"


def _clear_base_goals(base: Any) -> None:
    """Sweep any active nav goal so nothing fights the FSM's servo (best-effort)."""
    if base is None:
        return
    try:
        if callable(getattr(base, "clear_all_goals", None)):
            base.clear_all_goals()
        elif callable(getattr(base, "cancel_navigation", None)):
            base.cancel_navigation()
    except Exception:  # noqa: BLE001 — mutex sweep must never crash a turn
        pass


@skill(aliases=["approach_object", "approach object", "approach", "靠近", "靠近物体",
                "靠近那个", "走近", "凑近", "视觉伺服靠近"], direct=True)
class RealApproachObjectSkill:
    """Visually servo the BASE up to an object, stopping at the handoff (arm-free).

    Sends an approach task to the Z-Mobile-manip FSM and blocks, polling
    ``/z_manip/task/status``. Returns success the moment the base reaches the
    servo→grasp handoff (verify with ``approach_ready()``); CANCELS on every exit
    so the run never enters an arm phase and the base is always stopped.
    """

    name = "approach_object"
    description = (
        "Visually servo the REAL Go2W chassis up to a named object and STOP at the "
        "servo→grasp handoff (~0.55 m standoff), the moment before the arm would "
        "engage. APPROACH-ONLY (current phase): it auto-cancels the task at the "
        "handoff phase, so the manipulator NEVER moves. Blocks until "
        "handoff/failure/timeout; verify with approach_ready() (the FSM's own "
        "phase latch — perception is decision input, never proof). Needs the "
        "Z-Mobile-manip stack up (manip_bringup). 靠近某物体(只靠近,不抓)。"
    )
    parameters = {
        "target": {
            "type": "string", "required": True,
            "description": ("what to approach, phrased by real appearance "
                            "(e.g. 'metal bowl', '红色杯子')"),
        },
        "instruction": {
            "type": "string", "required": False,
            "description": ("optional raw-NL override sent verbatim to the FSM "
                            "(defaults to an 'approach <target>' phrasing)"),
        },
    }
    preconditions: list = []
    effects = {"base_state": "moved"}

    def __init__(self, transport: Any = None,
                 runner: Callable[..., Any] | None = None) -> None:
        # Injectable seams for the base-chain precheck (fake transport/runner in
        # tests). Default: the resolved manip transport + a real subprocess runner.
        self._transport = transport
        self._runner = runner or _default_runner

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        base = _base_of(context)
        bridge = _manip_of(context)
        if bridge is None:
            return SkillResult(success=False, diagnosis_code="no_manip_stack",
                               error_message=_NO_STACK_MSG)
        if not getattr(bridge, "is_connected", False):
            try:
                bridge.connect()
            except Exception:  # noqa: BLE001 — connect is best-effort
                pass
        if not getattr(bridge, "is_connected", False):
            return SkillResult(success=False, diagnosis_code="no_manip_stack",
                               error_message=_NO_STACK_MSG)
        src = params if isinstance(params, dict) else {}
        target = str(src.get("target") or kw.get("target") or "").strip()
        instruction = str(src.get("instruction") or kw.get("instruction") or "").strip()
        if not instruction:
            if not target:
                return SkillResult(success=False, diagnosis_code="bad_params",
                                   error_message="approach_object needs a target")
            instruction = _approach_instruction(target)

        # Base-chain precheck: approach servos the CHASSIS, so the NUC base chain
        # (reactive-live) must be up or the FSM commands velocities nothing
        # consumes. The active probe runs ONLY when a transport was injected: a
        # blind default would ssh the NUC on every approach (latency + disturbs a
        # box we must not poke), so the registry-default path skips it and the
        # recovery hint rides the stall/timeout message instead. When wired, a
        # definite down fails CLOSED with the hint; an undeterminable probe (None)
        # fails OPEN so a flaky CLI never blocks a run the operator knows is fine.
        if self._transport is not None:
            if _base_chain_ready(self._transport, self._runner) is False:
                oplog("skill", "approach_object", "base chain down -> recovery hint")
                return SkillResult(
                    success=False, diagnosis_code="no_base_chain",
                    result_data={"recovery": "manip_bringup(action='start_base')"},
                    error_message=_NO_BASE_CHAIN_MSG)

        # Base mutex: clear stale goals, mark the chassis busy for the manip run.
        _clear_base_goals(base)
        if base is not None:
            try:
                base.manip_active = True
            except Exception:  # noqa: BLE001 — flag is best-effort
                pass
        oplog("skill", "approach_object", f"task -> {instruction!r}")
        try:
            if not bridge.send_task(instruction):
                return SkillResult(
                    success=False, diagnosis_code="task_send_failed",
                    error_message="could not publish the approach task to "
                                  "/z_manip/task/request")
            return self._poll(bridge, target)
        finally:
            # ALWAYS cancel (approach-only guarantee + base zero) and release.
            try:
                bridge.cancel_task()
            except Exception:  # noqa: BLE001 — cancel is best-effort
                pass
            if base is not None:
                try:
                    base.manip_active = False
                except Exception:  # noqa: BLE001
                    pass
                _clear_base_goals(base)

    def _poll(self, bridge: Any, target: str) -> SkillResult:
        period = 1.0 / max(CFG.poll_hz, 0.5)
        deadline = time.monotonic() + CFG.approach_timeout_s
        last_phase: Any = _SENTINEL
        while time.monotonic() < deadline:
            phase = bridge.phase
            if phase != last_phase:
                oplog("skill", "approach_object",
                      f"phase={phase} depth={bridge.desired_camera_depth_m} "
                      f"coarse={bridge.coarse_ready}")
                last_phase = phase
            if phase in ARM_PHASES:
                return self._arm_abort(phase)
            if bridge.approach_reached() or phase in HANDOFF_PHASES:
                return self._reached(bridge, target)
            if phase in TERMINAL_FAIL_PHASES:
                return self._failed(bridge)
            if phase == CANCELED_PHASE:
                return SkillResult(
                    success=False, diagnosis_code="approach_canceled",
                    result_data={"phase": phase, "verify_hint": "approach_ready()"},
                    error_message="approach task was CANCELED before the handoff")
            time.sleep(period)
        return self._timeout(last_phase)

    @staticmethod
    def _reached(bridge: Any, target: str) -> SkillResult:
        snap = bridge.status_snapshot()
        depth = snap.desired_camera_depth_m
        depth_txt = f"{depth:.2f}m" if depth is not None else "standoff"
        data = {
            "phase": snap.phase,
            "coarse_ready": snap.coarse_ready,
            "desired_camera_depth_m": depth,
            "measured_base_linear_speed_mps": snap.measured_base_linear_speed_mps,
            "measured_base_angular_speed_rps": snap.measured_base_angular_speed_rps,
            "arm_engaged": False,
            "verify_hint": "approach_ready()",
            "message": (f"已靠近{(' ' + target) if target else ''}到交接距离"
                        f"({depth_txt}),底盘停稳 — 手臂全程未参与(approach-only,"
                        f"已在交接相位自动取消)。用 approach_ready() 验收"),
        }
        oplog("skill", "approach_object",
              f"REACHED handoff phase={snap.phase} depth={depth}")
        return SkillResult(success=True, result_data=data)

    @staticmethod
    def _failed(bridge: Any) -> SkillResult:
        snap = bridge.status_snapshot()
        reason = snap.failure or "unknown"
        oplog("skill", "approach_object", f"FAILED phase={snap.phase} reason={reason}")
        return SkillResult(
            success=False, diagnosis_code="approach_failed",
            result_data={"phase": snap.phase, "failure": reason,
                         "verify_hint": "approach_ready()"},
            error_message=f"approach failed at phase {snap.phase!r}: {reason}")

    @staticmethod
    def _timeout(last_phase: Any) -> SkillResult:
        phase = None if last_phase is _SENTINEL else last_phase
        oplog("skill", "approach_object", f"TIMEOUT last_phase={phase}")
        return SkillResult(
            success=False, diagnosis_code="approach_timeout",
            result_data={"phase": phase, "verify_hint": "approach_ready()"},
            error_message=(
                f"approach did not reach the handoff within "
                f"{CFG.approach_timeout_s:.0f}s (last phase {phase!r}). The FSM "
                "needs joint feedback (/piper/state) to leave GROUNDING and the "
                "external nav stack for COARSE_NAV — check manip_status(). If the "
                "chassis never moved, the NUC base chain is likely down: bring it "
                "up with manip_bringup(action='start_base'), then retry."))

    @staticmethod
    def _arm_abort(phase: Any) -> SkillResult:
        oplog("skill", "approach_object", f"ARM-PHASE ABORT phase={phase}")
        return SkillResult(
            success=False, diagnosis_code="manip_arm_phase",
            result_data={"phase": phase},
            error_message=(
                f"SAFETY: FSM reached arm phase {phase!r} before the handoff "
                "cancel — cancelling now. approach-only must never enter an arm "
                "phase; report this."))


def _default_runner(argv: list[str], timeout: float) -> Any:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


@dataclass(frozen=True)
class _BringupGrade:
    """One manip_bringup grade: the CLI tokens, timeout, motion class, UI-surface."""

    tokens: tuple[str, ...]   # manip <tokens...>
    timeout_s: float
    motion_enabling: bool     # True = starts/needs the base chain (approach can move)
    show_ui: bool             # append the UI address to the success reply


#: manip_bringup action -> grade. MODULAR / GRADED (2026-07-29):
#:  * ``start``      — ZERO-MOTION-RISK level: the perception vision components +
#:    the task FSM + the planning-workbench UI, via ``manip start``. It NEVER
#:    touches the NUC base chain, so the chassis has no /cmd_vel consumer and is
#:    physically inert; this is the default the persona steers to.
#:  * ``start_base`` — the NUC base chain (reactive-live), a SEPARATE, deliberate,
#:    motion-enabling action (``manip component restart reactive-control``). Only
#:    after this can approach_object actually drive the chassis.
#:  * ``bringup``    — the full cold stack INCLUDING the base chain (``manip
#:    bringup``); operator-initiated, motion-enabling, kept for a from-cold host.
#:  * ``stop`` / ``status`` — tear down / query.
_BRINGUP_ACTIONS: dict[str, _BringupGrade] = {
    "start": _BringupGrade(("start",), 120.0, motion_enabling=False, show_ui=True),
    "start_base": _BringupGrade(
        ("component", "restart", "reactive-control"), 180.0,
        motion_enabling=True, show_ui=False),
    "bringup": _BringupGrade(("bringup",), 240.0, motion_enabling=True, show_ui=True),
    "stop": _BringupGrade(("stop",), 120.0, motion_enabling=False, show_ui=False),
    "status": _BringupGrade(("status",), 30.0, motion_enabling=False, show_ui=False),
}


def _base_chain_ready(transport: Any, runner: Callable[..., Any]) -> bool | None:
    """Best-effort read of whether the NUC base chain (reactive-live) is healthy.

    Runs ``manip status reactive-control`` and looks for an active/healthy marker.
    Returns True (up), False (clearly down), or None (undeterminable — no CLI, ssh
    down, parse miss) so the caller can fail-OPEN on None (never block an approach
    on a flaky probe) but fail-CLOSED with a recovery hint on a definite False."""
    if transport is None:
        return None
    try:
        if transport.preflight():
            return None
        argv = transport.command_argv("status", "reactive-control")
        proc = runner(argv, timeout=20.0)
    except Exception:  # noqa: BLE001 — probe boundary, undeterminable
        return None
    if getattr(proc, "returncode", 1) != 0:
        return None
    out = (getattr(proc, "stdout", "") or "").lower()
    if not out.strip():
        return None
    # Down markers FIRST — "inactive" / "not active" contain the substring "active",
    # so an up-first check would misread a down chain as up.
    if any(k in out for k in ("inactive", "not active", "down", "absent", "failed",
                              "stopped", "unreachable")):
        return False
    if any(k in out for k in ("healthy", "active", "running")):
        return True
    return None


@skill(aliases=["manip_bringup", "manip bringup", "manip起", "起manip栈",
                "启动manip", "manip组件", "manip stack", "起视觉抓取栈"],
       direct=True)
class RealManipBringupSkill:
    """Bring the Z-Mobile-manip component stack up / down / query via the manip CLI."""

    name = "manip_bringup"
    description = (
        "GRADED lifecycle for the Z-Mobile-manip stack through the manip operator "
        "CLI (arm-safe by construction: home/grasp are UI-only beside the E-stop, "
        "never a CLI verb). action='start' = the ZERO-MOTION-RISK level — vision "
        "perception + task FSM + the planning UI at " + MANIP_UI_URL + "; it never "
        "touches the base chain, so the chassis stays physically inert. "
        "action='start_base' = a SEPARATE, motion-enabling step that brings up the "
        "NUC base chain (reactive-live) so approach_object can actually drive. "
        "'bringup' = the full cold stack incl the base; 'stop' tears down; 'status' "
        "queries. On a successful start the reply carries the UI address. "
        "起停查 manip(start=感知+任务FSM+UI 零运动;start_base=底盘链单独起;不动手臂)。"
    )
    parameters = {
        "action": {"type": "string", "required": False, "default": "status",
                   "description": "start | start_base | bringup | stop | status"},
    }
    preconditions: list = []
    effects = {"manip_stack": "changed"}

    def __init__(self, runner: Callable[..., Any] | None = None,
                 transport: Any = None) -> None:
        self._runner = runner or _default_runner
        self._transport = transport

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        action = "status"
        for src in (params if isinstance(params, dict) else {}, kw):
            if isinstance(src, dict) and src.get("action"):
                action = str(src["action"]).lower().strip()
                break
        grade = _BRINGUP_ACTIONS.get(action)
        if grade is None:
            return SkillResult(
                success=False, diagnosis_code="bad_action",
                error_message=(f"unknown manip action {action!r}; valid: "
                               f"{sorted(_BRINGUP_ACTIONS)}"))
        transport = self._transport or manip_transport()
        pre = transport.preflight()
        if pre:
            return SkillResult(success=False, diagnosis_code="no_manip_stack",
                               error_message=pre)
        argv = transport.command_argv(*grade.tokens)
        subcmd = " ".join(grade.tokens)
        oplog("skill", "manip_bringup",
              f"{action} -> manip {subcmd} ({transport.describe()})")
        try:
            proc = self._runner(argv, timeout=grade.timeout_s)
        except Exception as exc:  # noqa: BLE001 — honest failure, never raise
            return SkillResult(success=False, diagnosis_code="manip_cli_failed",
                               error_message=f"manip {subcmd} failed: {exc}")
        rc = getattr(proc, "returncode", 1)
        out = (getattr(proc, "stdout", "") or "")[-600:]
        err = (getattr(proc, "stderr", "") or "")[-300:]
        if rc != 0:
            return SkillResult(
                success=False, diagnosis_code="manip_cli_failed",
                result_data={"action": action, "returncode": rc, "stdout": out},
                error_message=f"manip {subcmd} rc={rc}: {err}")
        oplog("skill", "manip_bringup", f"{action} ok")
        data = {
            "action": action,
            "stdout": out,
            "ui_url": MANIP_UI_URL if grade.show_ui else None,
            "motion_enabling": grade.motion_enabling,
        }
        message = self._success_message(action, grade, out)
        if action in ("start", "bringup"):
            # `manip start` returns when the containers are up, but the FSM node
            # set takes tens of seconds to reach ready — probe the DDS graph
            # (bounded) so the "已就绪" reply and the manip_stack_up() verify
            # probe that follows stay honest.
            confirmed = self._confirm_fsm_up(context)
            data["fsm_confirmed"] = confirmed
            data["verify_hint"] = "manip_stack_up()"
            if confirmed is False:
                message = (
                    f"manip 组件已启动,但任务 FSM 在 "
                    f"{int(self._FSM_CONFIRM_TIMEOUT_S)}s 内未确认就绪"
                    f"(/z_manip/task/status 无 publisher)— 用 manip_status "
                    f"复查;UI 地址 {MANIP_UI_URL}")
        data["message"] = message
        return SkillResult(success=True, result_data=data)

    _FSM_CONFIRM_TIMEOUT_S = 60.0
    _FSM_CONFIRM_POLL_S = 2.0

    def _confirm_fsm_up(self, context) -> bool | None:
        """Bounded wait for the task FSM's status publisher (DDS graph fact).

        True = publisher seen; False = timed out (FSM not confirmed); None = no
        bridge to probe (undeterminable — NOT a failure, the verify probe will
        still read the graph at grade time if a bridge exists by then).
        """
        bridge = _manip_of(context)
        if bridge is None:
            return None
        try:
            connect = getattr(bridge, "connect", None)
            if callable(connect):
                connect()
        except Exception:  # noqa: BLE001 — probe must never break bringup
            return None
        deadline = time.monotonic() + self._FSM_CONFIRM_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                if int(bridge.status_publisher_count()) > 0:
                    return True
            except Exception:  # noqa: BLE001 — torn context etc.: undeterminable
                return None
            time.sleep(self._FSM_CONFIRM_POLL_S)
        return False

    @staticmethod
    def _success_message(action: str, grade: _BringupGrade, out: str) -> str:
        """Compose the honest, grade-aware success line (UI address on start)."""
        tail = out.strip()
        if action == "start":
            head = (f"mobile manip 已就绪(零运动级:感知+任务FSM+UI,未起底盘链) — "
                    f"UI 地址 {MANIP_UI_URL} 。要让底盘能靠近物体,再单独 "
                    f"manip_bringup(action='start_base')(操作员在急停旁)")
        elif action == "start_base":
            head = ("NUC 底盘链(reactive-live)已起 — 底盘现在可被 approach_object "
                    "驱动(运动使能级,操作员在急停旁)")
        elif action == "bringup":
            head = (f"完整 manip 冷启动完成(含底盘链,运动使能) — UI 地址 "
                    f"{MANIP_UI_URL}")
        elif action == "stop":
            head = "manip 栈已停"
        else:
            head = f"manip {' '.join(grade.tokens)} 完成"
        return f"{head}\n{tail}" if tail else head


@skill(aliases=["manip_status", "manip status", "manip状态", "查manip",
                "抓取任务状态"], direct=True, verify_exempt=True)
class RealManipStatusSkill:
    """Report the live Z-Mobile-manip FSM state (read-only query)."""

    name = "manip_status"
    description = (
        "Report the Z-Mobile-manip task FSM state — phase, standoff depth, "
        "coarse/handoff readiness, result, failure — from its live status "
        "stream. Read-only query; the answer is DECISION INPUT, never "
        "verification evidence (approach is proven by approach_ready()). "
        "查询 manip 任务状态。"
    )
    parameters: dict = {}
    preconditions: list = []
    effects: dict = {}

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        bridge = _manip_of(context)
        if bridge is None:
            return SkillResult(success=False, diagnosis_code="no_manip_stack",
                               error_message=_NO_STACK_MSG)
        if not getattr(bridge, "is_connected", False):
            try:
                bridge.connect()
            except Exception:  # noqa: BLE001 — best-effort
                pass
        snap = bridge.status_snapshot()
        data = {
            "connected": snap.connected,
            "phase": snap.phase,
            "coarse_ready": snap.coarse_ready,
            "desired_camera_depth_m": snap.desired_camera_depth_m,
            "measured_base_linear_speed_mps": snap.measured_base_linear_speed_mps,
            "measured_base_angular_speed_rps": snap.measured_base_angular_speed_rps,
            "result": snap.result,
            "failure": snap.failure,
            "approach_reached": snap.approach_reached,
            "status_age_s": (round(snap.status_age_s, 1)
                             if snap.status_age_s is not None else None),
            "schema": snap.schema,
        }
        if snap.phase is None and snap.status_age_s is None:
            data["message"] = (
                "manip 桥已连接但从未收到 /z_manip/task/status — 任务图很可能未启动"
                "(manip_bringup(action='start')),或当前没有活动任务。"
                if snap.connected else
                "manip 桥未连接 — 任务图不可达,先 manip_bringup(action='start')")
            return SkillResult(success=True, result_data=data)
        data["message"] = (
            f"manip 相位={snap.phase}, 交接就绪={snap.approach_reached}, "
            f"coarse_ready={snap.coarse_ready}, 目标深度={snap.desired_camera_depth_m}, "
            f"result={snap.result or '—'}, failure={snap.failure or '—'} "
            f"(状态 {data['status_age_s']}s 前)")
        return SkillResult(success=True, result_data=data)


@skill(aliases=["manip_cancel", "manip cancel", "取消manip", "取消抓取任务",
                "停manip", "manip停", "abort manip"], direct=True)
class RealManipCancelSkill:
    """Send a clean cancel to the Z-Mobile-manip task FSM (arm-free safety abort)."""

    name = "manip_cancel"
    description = (
        "Send a clean cancel to the Z-Mobile-manip task FSM "
        "(/z_manip/task/cancel) — stops the current task at ANY phase and zeros "
        "the chassis via the FSM's own safety action. The arm-free abort; "
        "idempotent and safe to fire anytime. 取消 manip 任务。"
    )
    parameters: dict = {}
    preconditions: list = []
    effects: dict = {}

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        bridge = _manip_of(context)
        if bridge is None:
            return SkillResult(success=False, diagnosis_code="no_manip_stack",
                               error_message=_NO_STACK_MSG)
        if not getattr(bridge, "is_connected", False):
            try:
                bridge.connect()
            except Exception:  # noqa: BLE001 — best-effort
                pass
        ok = False
        try:
            ok = bool(bridge.cancel_task())
        except Exception as exc:  # noqa: BLE001 — honest failure
            return SkillResult(success=False, diagnosis_code="manip_cancel_failed",
                               error_message=f"cancel publish failed: {exc}")
        # Release the base mutex either way (a cancel means the manip run is over).
        base = _base_of(context)
        if base is not None:
            try:
                base.manip_active = False
            except Exception:  # noqa: BLE001
                pass
        oplog("skill", "manip_cancel", "cancel sent" if ok else "cancel FAILED")
        return SkillResult(
            success=ok,
            result_data={"message": ("已发送 manip 取消 — 任务在任意相位干净停止,"
                                     "底盘归零(手臂本阶段不参与)")},
            error_message="" if ok else "/z_manip/task/cancel publish did not go out")
