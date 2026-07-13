# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real ops skills — open_viz / where, so VGG plans can orchestrate them.

Field trace 2026-07-10 evening: '启动导航,打开rviz' — the planner produced
ONLY the bringup step. Viz existed solely as a TOOL, and tools are invisible
to strategy planning, so the second half of the command was silently dropped.
Same shape for "where am I" inside a multi-step plan.

Both skills are THIN:

* ``open_viz`` acts on the SAME :class:`VizOverlaySession` the ``go2w_real_viz``
  tool uses (embodiment ``_viz``, ridden on the driver as ``base.viz_manager``)
  — tool-opened and plan-opened views share one launcher table, so nothing can
  double-launch RViz; opening an already-open view reports ok (dedupe).
* ``where`` reads the live pose straight from the driver — and refuses to
  present the never-received default (0,0,0) as a real pose (the stack_ready
  field-bug twin).

Split file per the repo rule (files < 400 lines); registered at the skills
extension marker in ``go2w_real.py``; strategies ``open_viz_skill`` /
``where_skill``.
"""

from __future__ import annotations

import math
from typing import Any

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_course import course_of
from zeno.vcli.worlds.go2w_real_diag import oplog, wrap_angle
from zeno.vcli.worlds.go2w_real_places import places_of
from zeno.vcli.worlds.go2w_real_skills import _base_of

_VIEW_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("explore", "explore"), ("探索", "explore"),
    ("route", "route"), ("路线", "route"), ("路径", "route"),
)


def _viz_session_of(context: Any) -> Any:
    """Return the shared VizOverlaySession from a SkillContext (or None).

    The embodiment publishes it as the 'viz' service (context.services); VGG
    GoalExecutor contexts carry no world services, so it also rides the driver
    (base.viz_manager) — the same two-path seam as the explore/route managers.
    """
    if context is None:
        return None
    services = getattr(context, "services", None) or {}
    session = services.get("viz")
    if session is not None:
        return session
    return getattr(getattr(context, "base", None), "viz_manager", None)


@skill(aliases=["open_viz", "open rviz", "打开rviz", "打开 rviz", "打开可视化",
                "可视化", "show rviz", "rviz"], direct=True)
class RealVizSkill:
    """Open an RViz view for the operator (plan-orchestrable viz)."""

    name = "open_viz"
    description = (
        "Open RViz on the robot's desktop for the operator (Moonlight/local "
        "screen) as a plannable STEP: view main|explore|route — match the "
        "running planner. Shares the go2w_real_viz tool's overlay session: "
        "opening an already-open view reports ok (never double-launches). "
        "打开 RViz 可视化(main/explore/route 视图)。")
    parameters = {
        "view": {"type": "string", "default": "main", "required": False,
                 "description": "main | explore | route"},
    }
    preconditions: list = []
    effects = {"viz": "open"}

    @staticmethod
    def _parse_view(sources: tuple, text: str) -> str:
        for src in sources:
            if isinstance(src, dict) and src.get("view"):
                return str(src["view"]).strip().lower()
        for token, view in _VIEW_KEYWORDS:
            if token in text:
                return view
        return "main"

    def execute(self, params=None, context=None, **kw):
        session = _viz_session_of(context)
        if session is None:
            return SkillResult(success=False, diagnosis_code="no_viz_session",
                               error_message=("No viz session (go2w_real world "
                                              "only)"))
        sources = (params if isinstance(params, dict) else {}, kw)
        text = str(getattr(context, "instruction", "")
                   or getattr(context, "text", "") or "").lower()
        view = self._parse_view(sources, text)
        status, detail = session.open(view)
        oplog("skill", "open_viz", f"view={view} -> {status} ({detail})")
        if status == "opened":
            return SkillResult(success=True, result_data={
                "view": view, "status": status,
                "message": (f"RViz ({view}) opening on the robot desktop — "
                            f"visible via Moonlight or the local screen")})
        if status == "already_open":
            return SkillResult(success=True, result_data={
                "view": view, "status": status,
                "message": f"RViz ({view}) is already open — nothing to do"})
        return SkillResult(success=False,
                           result_data={"view": view, "status": status},
                           error_message=f"could not open RViz ({view}): {detail}")


@skill(aliases=["where", "where_am_i", "where am i", "我在哪", "我在哪里",
                "在哪里", "当前位置", "位置", "current position", "pose"],
       direct=True)
class RealWhereSkill:
    """Report the live map-frame pose (x, y, yaw) from the driver."""

    name = "where"
    description = (
        "Report the REAL Go2W's current map-frame pose {x, y, yaw} from live "
        "/state_estimation odometry, as a plannable STEP (e.g. before a "
        "relative move). Honest: refuses to report a pose when odometry never "
        "arrived. 查询当前位姿。")
    parameters: dict = {}
    preconditions: list = []
    effects: dict = {}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        try:
            pos = base.get_position()
            yaw = float(base.get_heading())
        except Exception as exc:  # noqa: BLE001 — driver boundary, honest failure
            return SkillResult(success=False, diagnosis_code="pose_read_failed",
                               error_message=f"pose read failed: {exc}")
        age = None
        age_fn = getattr(base, "odom_age_s", None)
        if callable(age_fn):
            try:
                age = age_fn()
            except Exception:  # noqa: BLE001 — freshness is best-effort
                age = None
            if age is None:
                # The driver KNOWS it never received odometry — the cached
                # (0,0,0) default is not a pose (stack_ready field-bug twin).
                return SkillResult(
                    success=False, diagnosis_code="no_odometry",
                    error_message=("no odometry received — the pose cache is "
                                   "default zeros, not a real pose; bring the "
                                   "stack up (bringup_skill) first"))
        data: dict[str, Any] = {
            "x": round(float(pos[0]), 3),
            "y": round(float(pos[1]), 3),
            "yaw": round(yaw, 3),
        }
        if age is not None:
            data["odom_age_s"] = round(float(age), 1)
        message = (f"pose: x={data['x']}, y={data['y']}, "
                   f"yaw={data['yaw']} rad")
        # GLOBAL AWARENESS enrichment (CEO directive 2026-07-13 night): the
        # spatial session memory the pose lives in — origin-relative offset,
        # heading-intent (course) drift, marked place names. Everything below
        # is best-effort and ADDITIVE: a ledger-less/tracker-less base keeps
        # today's payload byte-identical.
        ledger = places_of(context)
        if ledger is not None:
            # This fresh pose is also the session's first chance to capture
            # the origin (回到起点 needs it even before any motion command).
            origin = ledger.ensure_origin(
                (float(pos[0]), float(pos[1]), yaw))
            dx = float(pos[0]) - origin[0]
            dy = float(pos[1]) - origin[1]
            data["origin"] = {"x": round(origin[0], 2), "y": round(origin[1], 2)}
            data["origin_distance_m"] = round(math.hypot(dx, dy), 2)
            data["origin_bearing_deg"] = round(math.degrees(math.atan2(dy, dx)), 1)
            message += (f"; 距起点 {data['origin_distance_m']} m "
                        f"(方位 {data['origin_bearing_deg']}°)")
            names = list(ledger.marks)
            if names:
                data["marked_places"] = names
                message += f"; 已标记地点: {', '.join(names)}"
        tracker = course_of(context)
        course = getattr(tracker, "course_yaw", None)
        if course is not None:
            drift = wrap_angle(yaw - float(course))
            data["course_deg"] = round(math.degrees(float(course)), 1)
            data["course_drift_deg"] = round(math.degrees(drift), 1)
            message += (f"; 预期航向 {data['course_deg']}° "
                        f"(漂移 {data['course_drift_deg']:+}°)")
        data["message"] = message
        return SkillResult(success=True, result_data=data)
