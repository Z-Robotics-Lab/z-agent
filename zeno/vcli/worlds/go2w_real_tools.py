# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real tools — bringup (nav.sh) + navigate / where / stop / manual / resume.

Split out of ``go2w_real.py`` (files under 400 lines). The bringup tool drives
the out-of-band ``nav.sh`` lifecycle; the rest act on the session's
``Go2WHardware`` base. Every tool degrades to a clear error (never a crash) when
no base is connected, and steers the model to go2w_real_bringup(start).
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from zeno.vcli.tools.base import ToolContext, ToolResult, tool
from zeno.vcli.worlds.go2w_real_skills import CFG, nav_sh_path

# The lifecycle subcommands the bringup tool may invoke — the idempotent,
# non-blocking ones (start/stop/status + stance up/down). nav.sh's blocking /
# interactive modes (explore/route/rviz/log) are deliberately NOT exposed as an
# agent tool: they would hang the turn.
_BRINGUP_ACTIONS: dict[str, str] = {
    "up": "up",           # stand up (BalanceStand — ready to walk)
    "down": "down",       # lie down (safe from any state)
    "start": "start",     # bring up the nav stack (~40-60s until SLAM ready)
    "stop": "stop",       # tear the stack down
    "status": "status",   # unit state + key topic rates
}


def _hw_of(context: ToolContext) -> Any:
    """Return the Go2WHardware base from a tool's agent context (or None)."""
    agent = getattr(context, "agent", None)
    return getattr(agent, "_base", None) if agent is not None else None


@tool(
    name="go2w_real_bringup",
    description=(
        "Manage the REAL Go2W nav stack lifecycle via nav.sh (out-of-band). "
        "action: start (bring the stack up — ~40-60s until SLAM ready), stop "
        "(tear it down), status (unit state + key topic rates), up (stand up), "
        "down (lie down). Idempotent. 管理真机导航栈生命周期。"),
    read_only=False,
    permission="allow",
)
class Go2WRealBringupTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["start", "stop", "status", "up", "down"],
                       "default": "status"},
        },
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        action = (params or {}).get("action", "status")
        subcmd = _BRINGUP_ACTIONS.get(action)
        if subcmd is None:
            return ToolResult(content=(
                f"unknown action {action!r}; valid: {sorted(_BRINGUP_ACTIONS)}"),
                is_error=True)
        script = nav_sh_path()
        if not os.path.isfile(script):
            return ToolResult(content=(
                f"nav.sh not found at {script} — set GO2W_NAV_SH to the nav.sh path"),
                is_error=True)
        # 'start' stops-old-first then returns after launching (SLAM readies async);
        # a longer timeout covers stack teardown on 'stop'.
        timeout = 120 if subcmd in ("start", "stop") else 60
        try:
            r = subprocess.run(["bash", script, subcmd], capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return ToolResult(content=(
                f"nav.sh {subcmd} timed out after {timeout}s (still running in "
                f"background?). Poll go2w_real_bringup(action='status')."),
                is_error=True)
        out = (r.stdout + r.stderr).strip()[-1200:]
        if r.returncode != 0:
            return ToolResult(content=(
                f"nav.sh {subcmd} FAILED (exit={r.returncode}).\n{out}"), is_error=True)
        hint = ("\n(stack starting — SLAM ready in ~40-60s; poll "
                "go2w_real_bringup(action='status') until topics show rates)"
                if subcmd == "start" else "")
        return ToolResult(content=f"nav.sh {subcmd}:\n{out}{hint}")


@tool(
    name="go2w_real_navigate",
    description=(
        "Send the REAL Go2W to map coordinates (x, y). Publishes a latched "
        "/way_point; the local planner drives there. Blocking until "
        "odometry-verified arrival (~0.8 m) or timeout. 让真机导航到 (x, y)。"),
    read_only=False,
    permission="allow",
)
class Go2WRealNavigateTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "target x (map frame, m)"},
            "y": {"type": "number", "description": "target y (map frame, m)"},
        },
        "required": ["x", "y"],
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        base = _hw_of(context)
        if base is None:
            return ToolResult(content="no Go2W hardware base connected", is_error=True)
        try:
            x, y = float(params["x"]), float(params["y"])
            ok = bool(base.navigate_to(x, y, timeout=CFG.nav_timeout_s))
            pos = base.get_position()
            return ToolResult(content=(
                f"{'arrived' if ok else 'did-not-arrive'} at "
                f"({pos[0]:.2f}, {pos[1]:.2f}); goal ({x:.2f}, {y:.2f})"),
                is_error=not ok)
        except Exception as e:  # noqa: BLE001 — driver boundary
            return ToolResult(content=f"navigate error: {e}", is_error=True)


@tool(
    name="go2w_real_where",
    description=("Get the REAL Go2W's current /state_estimation pose {x, y, yaw} in "
                 "the map frame. 查询真机当前位姿。"),
    read_only=True,
    permission="allow",
)
class Go2WRealWhereTool:
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        base = _hw_of(context)
        if base is None:
            return ToolResult(content="no Go2W hardware base connected", is_error=True)
        pos = base.get_position()
        return ToolResult(content=json.dumps(
            {"x": round(pos[0], 3), "y": round(pos[1], 3),
             "yaw": round(base.get_heading(), 3)}))


@tool(
    name="go2w_real_stop",
    description=("EMERGENCY STOP the REAL Go2W: latch zero velocity (/estop) and "
                 "clear the nav goal (/nav_cancel). Resume with go2w_real_resume. "
                 "急停真机。"),
    read_only=False,
    permission="allow",
)
class Go2WRealStopTool:
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            from zeno.vcli.cognitive.abort import request_abort
            request_abort()
        except Exception:  # noqa: BLE001 — best-effort
            pass
        base = _hw_of(context)
        if base is None:
            return ToolResult(content="no Go2W hardware base connected", is_error=True)
        estopped = bool(base.estop())
        base.nav_cancel()
        return ToolResult(content=(
            f"E-STOP {'latched' if estopped else 'FAILED'}; nav goal cleared. "
            f"Call go2w_real_resume to re-enable."), is_error=not estopped)


def _explore_of(context: ToolContext) -> Any:
    """Return the Go2WExploreManager from a tool's agent context (or None)."""
    agent = getattr(context, "agent", None)
    return getattr(agent, "_explore", None) if agent is not None else None


@tool(
    name="go2w_real_explore",
    description=(
        "TARE autonomous exploration on the REAL Go2W (overlay child of "
        "nav.sh). action: start (launch, NON-blocking — poll status), status "
        "(state/finished/travel_m/runtime_s — the honest oracle: finished "
        "comes from TARE's own /exploration_finish, travel_m from odometry), "
        "stop (SIGINT our overlay + /nav_cancel; NEVER releases a latched "
        "E-stop — use go2w_real_resume explicitly). scenario: indoor_small "
        "(default) | indoor_large | outdoor. 全自主探索(启动/状态/停止)。"),
    read_only=False,
    permission="allow",
)
class Go2WRealExploreTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["start", "status", "stop"],
                       "default": "status"},
            # Mirrors ExploreConfig.scenarios (nav.sh scenario -> TARE yaml).
            "scenario": {"type": "string",
                         "enum": ["indoor_small", "indoor_large", "outdoor"],
                         "default": "indoor_small"},
            "resume": {"type": "boolean", "default": False,
                       "description": ("on stop: release the estop/manual "
                                       "latches afterwards (refused while an "
                                       "E-stop is latched)")},
        },
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        mgr = _explore_of(context)
        if mgr is None:
            return ToolResult(content=(
                "no explore manager on this session (go2w_real world only)"),
                is_error=True)
        action = (params or {}).get("action", "status")
        try:
            if action == "start":
                ok, msg = mgr.start_explore((params or {}).get("scenario"))
                return ToolResult(content=f"{msg}\n{self._status_json(mgr)}",
                                  is_error=not ok)
            if action == "status":
                return ToolResult(content=self._status_json(mgr))
            if action == "stop":
                ok, msg = mgr.stop_explore(resume=bool((params or {}).get("resume")))
                return ToolResult(content=f"{msg}\n{self._status_json(mgr)}",
                                  is_error=not ok)
        except Exception as e:  # noqa: BLE001 — manager boundary
            return ToolResult(content=f"explore {action} error: {e}", is_error=True)
        return ToolResult(content=(
            f"unknown action {action!r}; valid: ['start', 'status', 'stop']"),
            is_error=True)

    @staticmethod
    def _status_json(mgr: Any) -> str:
        from dataclasses import asdict

        return json.dumps(asdict(mgr.status()), ensure_ascii=False)


@tool(
    name="go2w_real_manual",
    description=("Hand control to the hardware remote: silence the guard so the "
                 "teleop pendant owns the robot (/manual). Resume autonomy with "
                 "go2w_real_resume. 遥控接管。"),
    read_only=False,
    permission="allow",
)
class Go2WRealManualTool:
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        base = _hw_of(context)
        if base is None:
            return ToolResult(content="no Go2W hardware base connected", is_error=True)
        ok = bool(base.manual())
        return ToolResult(content=(
            f"manual takeover {'engaged' if ok else 'FAILED'}; the remote owns "
            f"control. go2w_real_resume returns to autonomy."), is_error=not ok)


@tool(
    name="go2w_real_resume",
    description=("Resume autonomous arbitration: release both the E-stop and manual "
                 "latches (/estop_release). 恢复自主。"),
    read_only=False,
    permission="allow",
)
class Go2WRealResumeTool:
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        base = _hw_of(context)
        if base is None:
            return ToolResult(content="no Go2W hardware base connected", is_error=True)
        ok = bool(base.estop_release())
        return ToolResult(content=(
            f"autonomy {'resumed' if ok else 'resume FAILED'} (estop + manual "
            f"released)."), is_error=not ok)
