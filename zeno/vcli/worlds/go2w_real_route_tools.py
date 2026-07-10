# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real route tool — far_planner GLOBAL route mode lifecycle + goals.

Split out of ``go2w_real.py`` (files under 400 lines). ``go2w_real_route`` drives
the session's :class:`~zeno.hardware.ros2.go2w_hw_route.Go2WRouteManager`:
start/stop the far_planner overlay, send a global goal (goto), cancel the current
goal without tearing the overlay down, and read the honest status (state +
odometry-verified ``reached`` + far_planner's own ``far_reach``). Degrades to a
clear error (never a crash) when no manager is on the session.
"""

from __future__ import annotations

import json
from typing import Any

from zeno.vcli.tools.base import ToolContext, ToolResult, tool


def _route_of(context: ToolContext) -> Any:
    """Return the Go2WRouteManager from a tool's agent context (or None)."""
    agent = getattr(context, "agent", None)
    return getattr(agent, "_route", None) if agent is not None else None


@tool(
    name="go2w_real_route",
    description=(
        "far_planner GLOBAL route mode on the REAL Go2W (overlay child of "
        "nav.sh). action: start (launch far_planner, NON-blocking), goto "
        "(send a FAR goal x,y — plans a global route around obstacles, blocks "
        "until odometry-verified arrival), status (state/reached/goal/far_reach "
        "— reached is the honest odometry oracle, far_reach is far_planner's own "
        "signal), cancel (clear the current goal, keep the overlay up), stop "
        "(SIGINT our overlay + /nav_cancel; NEVER releases a latched E-stop — use "
        "go2w_real_resume). Use for long cross-map goals; short hops use "
        "go2w_real_navigate. 全局路线规划(启动/发目标/状态/取消/停止)。"),
    read_only=False,
    permission="allow",
)
class Go2WRealRouteTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["start", "goto", "status", "cancel", "stop"],
                       "default": "status"},
            "x": {"type": "number", "description": "goto target x (map frame, m)"},
            "y": {"type": "number", "description": "goto target y (map frame, m)"},
            "resume": {"type": "boolean", "default": False,
                       "description": ("on stop: release the estop/manual latches "
                                       "afterwards (refused while an E-stop is "
                                       "latched)")},
        },
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        mgr = _route_of(context)
        if mgr is None:
            return ToolResult(content=(
                "no route manager on this session (go2w_real world only)"),
                is_error=True)
        action = (params or {}).get("action", "status")
        try:
            if action == "start":
                ok, msg = mgr.start_route()
                return ToolResult(content=f"{msg}\n{self._status_json(mgr)}",
                                  is_error=not ok)
            if action == "goto":
                return self._goto(mgr, params or {})
            if action == "status":
                return ToolResult(content=self._status_json(mgr))
            if action == "cancel":
                ok, msg = mgr.cancel_route()
                return ToolResult(content=f"{msg}\n{self._status_json(mgr)}",
                                  is_error=not ok)
            if action == "stop":
                ok, msg = mgr.stop_route(resume=bool((params or {}).get("resume")))
                return ToolResult(content=f"{msg}\n{self._status_json(mgr)}",
                                  is_error=not ok)
        except Exception as e:  # noqa: BLE001 — manager boundary
            return ToolResult(content=f"route {action} error: {e}", is_error=True)
        return ToolResult(content=(
            f"unknown action {action!r}; valid: "
            f"['start', 'goto', 'status', 'cancel', 'stop']"), is_error=True)

    def _goto(self, mgr: Any, params: dict[str, Any]) -> ToolResult:
        if "x" not in params or "y" not in params:
            return ToolResult(content=(
                "goto needs x and y (map-frame meters)"), is_error=True)
        try:
            x, y = float(params["x"]), float(params["y"])
        except (TypeError, ValueError):
            return ToolResult(content="goto x/y must be numbers", is_error=True)
        ok = bool(mgr.goto_via_route(x, y))
        return ToolResult(content=(
            f"{'arrived-via-route' if ok else 'did-not-arrive'} at "
            f"({x:.2f}, {y:.2f})\n{self._status_json(mgr)}"), is_error=not ok)

    @staticmethod
    def _status_json(mgr: Any) -> str:
        from dataclasses import asdict

        return json.dumps(asdict(mgr.status()), ensure_ascii=False)
