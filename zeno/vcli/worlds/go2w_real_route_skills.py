# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real route skills — route_via / stop_route via the far_planner overlay.

Split out of ``go2w_real.py`` (files under 400 lines). These skills drive the
embodiment's :class:`~zeno.hardware.ros2.go2w_hw_route.Go2WRouteManager`,
reached through the transport-agnostic ``context.services['route']`` seam (same
idea as ``context.services['explore']`` for TARE). ``route_via`` sends a GLOBAL
goal to far_planner (which plans a route to a FAR target through obstacles);
``stop_route`` tears the overlay down (never touching the estop/manual latches).

Reuses ``_target_xy`` from ``go2w_real_skills.py`` for (x, y) extraction so a
relative/absolute goal parses identically to navigate.
"""

from __future__ import annotations

from typing import Any

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_skills import CFG, _target_xy


def _route_mgr_of(context: Any) -> Any:
    """Return the Go2WRouteManager from a SkillContext (or None).

    The embodiment publishes it as the 'route' service (context.services) — the
    transport-agnostic seam, same idea as context.base for the driver.
    """
    if context is None:
        return None
    services = getattr(context, "services", None) or {}
    mgr = services.get("route")
    if mgr is not None:
        return mgr
    # VGG GoalExecutor contexts carry no world services — the manager also
    # rides the driver (base.route_manager), which every path wires.
    return getattr(getattr(context, "base", None), "route_manager", None)


@skill(aliases=["route", "route_to", "far", "far_planner", "全局导航", "远程导航",
                "规划路线", "长距离导航", "route via", "plan route"], direct=True)
class RealRouteViaSkill:
    """Send a GLOBAL route goal to far_planner (blocks until odometry arrival).

    Ensures the far_planner overlay is up (idempotent ``start_route``), then
    publishes the goal on ``/goal_point``; far_planner plans a global route over
    its visibility graph and drives the local planner there. Blocks until the
    robot is odometry-verified within tolerance of the goal, the timeout expires,
    or the route is cancelled. Verify with ``route_reached()``.
    """

    name = "route_via"
    description = (
        "Send the REAL Go2W to a FAR map coordinate (x, y) via far_planner GLOBAL "
        "route planning: plans a route around obstacles to a distant goal, then "
        "drives there (blocks until odometry-verified arrival). Use for long "
        "cross-map goals where a straight waypoint would get stuck; for short "
        "line-of-sight hops use navigate. 用 far_planner 规划全局路线到远处目标。")
    parameters = {
        "x": {"type": "number", "required": True, "description": "map-frame x (m)"},
        "y": {"type": "number", "required": True, "description": "map-frame y (m)"},
    }
    preconditions: list = []
    effects = {"base_state": "moved"}

    def execute(self, params=None, context=None, **kw):
        mgr = _route_mgr_of(context)
        if mgr is None:
            return SkillResult(success=False, diagnosis_code="no_route_manager",
                               error_message="No route manager (go2w_real world only)")
        try:
            x, y = _target_xy(params, kw, context)
        except ValueError as e:
            return SkillResult(success=False, error_message=str(e))
        # Idempotent: launches far_planner if it is not already up (a second call
        # while active is refused inside the manager and does not disturb it).
        started_ok, start_msg = mgr.start_route()
        ok = bool(mgr.goto_via_route(x, y, timeout=CFG.nav_timeout_s))
        data = {"x": round(x, 2), "y": round(y, 2),
                "verify_hint": f"route_reached() and at({x:.2f}, {y:.2f}, tol=1.0)"}
        if ok:
            data["message"] = (f"routed to ({x:.2f}, {y:.2f}); "
                               f"verify with route_reached()")
            return SkillResult(success=True, result_data=data)
        note = "" if started_ok else f" (start_route: {start_msg})"
        return SkillResult(success=False, result_data=data, error_message=(
            f"did not reach ({x:.2f}, {y:.2f}) via route{note}"))


@skill(aliases=["stop route", "stop routing", "停止路线", "结束路线", "取消路线",
                "别规划了"], direct=True)
class RealStopRouteSkill:
    """Stop far_planner route mode: SIGINT our overlay + /nav_cancel (latches
    untouched)."""

    name = "stop_route"
    description = (
        "Stop far_planner route mode: SIGINT the overlay we launched, then clear "
        "the latched waypoint (/nav_cancel). Never releases the estop/manual "
        "latches. 停止全局路线规划。")
    parameters: dict = {}
    preconditions: list = []
    effects = {"base_state": "stopped"}

    def execute(self, params=None, context=None, **kw):
        mgr = _route_mgr_of(context)
        if mgr is None:
            return SkillResult(success=False, diagnosis_code="no_route_manager",
                               error_message="No route manager (go2w_real world only)")
        ok, msg = mgr.stop_route(resume=False)
        return SkillResult(success=bool(ok), result_data={"message": msg},
                           error_message="" if ok else msg)
