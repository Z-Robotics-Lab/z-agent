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

_NO_STACK_MSG = (
    "manip ROS bridge is not connected — the Z-Mobile-manip task graph is not "
    "reachable on domain 20. Bring it up with manip_bringup(action='start'), "
    "wait for the components, then retry."
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
                "external nav stack for COARSE_NAV — check manip_status()."))

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


#: manip_bringup action -> (CLI subcommand, subprocess timeout seconds).
_BRINGUP_ACTIONS: dict[str, tuple[str, float]] = {
    "start": ("bringup", 240.0),
    "bringup": ("bringup", 240.0),
    "stop": ("stop", 120.0),
    "status": ("status", 30.0),
}


@skill(aliases=["manip_bringup", "manip bringup", "manip起", "起manip栈",
                "启动manip", "manip组件", "manip stack", "起视觉抓取栈"],
       direct=True)
class RealManipBringupSkill:
    """Bring the Z-Mobile-manip component stack up / down / query via the manip CLI."""

    name = "manip_bringup"
    description = (
        "Lifecycle for the Z-Mobile-manip vision+perception components through the "
        "manip operator CLI. action=start|bringup brings the full stack up; stop "
        "tears it down; status queries it. This CLI can NEVER actuate the "
        "manipulator (home/grasp are UI-only, beside the E-stop), so it is "
        "arm-safe by construction. 起停查 manip 组件(纯生命周期,不动手臂)。"
    )
    parameters = {
        "action": {"type": "string", "required": False, "default": "status",
                   "description": "start | bringup | stop | status"},
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
        if action not in _BRINGUP_ACTIONS:
            return SkillResult(
                success=False, diagnosis_code="bad_action",
                error_message=(f"unknown manip action {action!r}; valid: "
                               f"{sorted(_BRINGUP_ACTIONS)}"))
        subcmd, timeout = _BRINGUP_ACTIONS[action]
        transport = self._transport or manip_transport()
        pre = transport.preflight()
        if pre:
            return SkillResult(success=False, diagnosis_code="no_manip_stack",
                               error_message=pre)
        argv = transport.command_argv(subcmd)
        oplog("skill", "manip_bringup", f"{action} -> manip {subcmd} ({transport.describe()})")
        try:
            proc = self._runner(argv, timeout=timeout)
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
        return SkillResult(success=True, result_data={
            "action": action, "stdout": out,
            "message": f"manip {subcmd} 完成\n{out.strip()}"})


@skill(aliases=["manip_status", "manip status", "manip状态", "查manip",
                "抓取任务状态"], direct=True)
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
