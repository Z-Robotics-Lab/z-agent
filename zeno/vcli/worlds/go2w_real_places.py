# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real spatial SESSION MEMORY — origin, breadcrumbs, named places.

Field trace (CEO directive 2026-07-13 night): the operator said '回到刚才的
位置' and the model had NOTHING to resolve it against — it improvised
coordinates from earlier conversation text and drove to an invented spot.
RViz shows the operator the live pose; the agent must also REMEMBER where it
has been. This module is that memory plus the two skills that use it.

:class:`PoseLedger` is DETERMINISTIC state (Inv-1 parity with the course
tracker): the model can trigger a mark or a goto, but every pose value comes
from odometry the driver read — never an LLM-authored coordinate. It records
three facts:

* ORIGIN (起点) — captured ONCE at the first fresh odometry pose any place-
  aware skill sees (motion skills + where call :func:`record_departure` /
  ``ensure_origin``). 回到起点 always means the session start.
* BREADCRUMBS — a bounded deque (N=20) of ``(monotonic_t, x, y, yaw)`` pushed
  at each motion command START (navigate / move_relative / turn / goto). The
  newest crumb at least 0.3 m from the current pose IS '刚才的位置' (a nearer
  crumb is the place we are standing — skip to the older one).
* NAMED MARKS — ``mark(name, pose)``; unnamed marks auto-name 地点N.

The ledger is owned by the embodiment and rides the driver as
``base.pose_ledger`` (plus ``services['places']``) — the manager-rides-driver
seam shared with explore/route/viz/course, because VGG GoalExecutor contexts
carry no world services but always wire ``base``.

HONEST LIMIT (capability card says it too): every pose lives in the CURRENT
SLAM map frame — a nav-stack restart rebuilds the map and silently invalidates
all remembered places (重启导航栈后地点失效). Persistent places need the
relocalization roadmap item; until then the skills say so instead of driving
to stale coordinates in a new frame.
"""

from __future__ import annotations

import math
import re
import time
from collections import deque
from typing import Any

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_course import reset_course
from zeno.vcli.worlds.go2w_real_diag import _latched_hint, oplog

#: '刚才的位置' minimum recall distance (m): a breadcrumb closer than this to
#: the CURRENT pose is where we are standing, not somewhere to go back to.
MIN_RECALL_DISTANCE_M: float = 0.3

#: Breadcrumb bound — enough for a session of motion commands, tiny in memory.
BREADCRUMB_LIMIT: int = 20

#: Names that mean the session origin (label the card teaches: 起点).
_ORIGIN_WORDS: frozenset[str] = frozenset(
    {"起点", "原点", "出发点", "origin", "start", "home"})

#: Names that mean the newest breadcrumb ('刚才的位置').
_RECALL_WORDS: frozenset[str] = frozenset(
    {"刚才", "刚才的位置", "刚刚", "上一个", "上一个位置", "回去",
     "last", "previous", "back"})


class PoseLedger:
    """Deterministic per-session place memory (map frame; None = unknown)."""

    def __init__(self, limit: int = BREADCRUMB_LIMIT) -> None:
        self._origin: tuple[float, float, float] | None = None
        self._crumbs: deque[tuple[float, float, float, float]] = deque(
            maxlen=limit)
        self._marks: dict[str, tuple[float, float, float]] = {}
        self._auto_n = 0

    # -- origin ----------------------------------------------------------
    @property
    def origin(self) -> tuple[float, float, float] | None:
        """The session-start pose (x, y, yaw), or None before any odometry."""
        return self._origin

    def ensure_origin(
            self, pose: tuple[float, float, float]) -> tuple[float, float, float]:
        """Capture the origin ONCE (first fresh odometry pose); return it.

        A later pose must never silently re-capture — 回到起点 means the
        session start, not wherever the robot happened to be last asked.
        """
        if self._origin is None:
            self._origin = (float(pose[0]), float(pose[1]), float(pose[2]))
            oplog("places", "ledger",
                  f"origin captured ({self._origin[0]:.2f},{self._origin[1]:.2f})")
        return self._origin

    # -- breadcrumbs -------------------------------------------------------
    @property
    def breadcrumbs(self) -> tuple[tuple[float, float, float, float], ...]:
        """Bounded trail (monotonic_t, x, y, yaw), oldest -> newest."""
        return tuple(self._crumbs)

    def push_breadcrumb(self, pose: tuple[float, float, float]) -> None:
        """Record a motion-command start pose (newest = '刚才的位置')."""
        self._crumbs.append((time.monotonic(), float(pose[0]),
                             float(pose[1]), float(pose[2])))

    def recall(self, current_xy: tuple[float, float],
               min_m: float = MIN_RECALL_DISTANCE_M,
               ) -> tuple[float, float, float] | None:
        """The newest breadcrumb at least *min_m* from *current_xy*, or None.

        Skips current-pose duplicates: right after arriving somewhere the
        newest crumb IS (about) where we stand — '刚才的位置' means the next
        older place, not a zero-length hop.
        """
        cx, cy = float(current_xy[0]), float(current_xy[1])
        for _t, x, y, yaw in reversed(self._crumbs):
            if math.hypot(x - cx, y - cy) >= float(min_m):
                return (x, y, yaw)
        return None

    # -- named marks -------------------------------------------------------
    @property
    def marks(self) -> dict[str, tuple[float, float, float]]:
        """Named places (copy — callers cannot mutate the ledger)."""
        return dict(self._marks)

    def mark(self, name: str | None,
             pose: tuple[float, float, float]) -> str:
        """Store *pose* under *name* (auto 地点N when empty); return the name."""
        label = str(name or "").strip()
        if not label:
            self._auto_n += 1
            label = f"地点{self._auto_n}"
        self._marks[label] = (float(pose[0]), float(pose[1]), float(pose[2]))
        oplog("places", "ledger",
              f"mark '{label}' = ({pose[0]:.2f},{pose[1]:.2f})")
        return label

    # -- resolution ---------------------------------------------------------
    def resolve(self, name: str | None, current_xy: tuple[float, float],
                ) -> tuple[str | None, tuple[float, float, float] | None]:
        """Resolve a place *name* to ``(kind, pose)``; ``(None, None)`` unknown.

        起点/origin -> the captured origin; 刚才/上一个/back (or empty) -> the
        newest usable breadcrumb; anything else -> a named mark. Kinds are
        'origin' | 'breadcrumb' | 'mark' so callers can refuse honestly (an
        unset origin is 'we never had odometry', not 'drive to (0,0)').
        """
        label = str(name or "").strip()
        if label in _ORIGIN_WORDS:
            return ("origin", self._origin) if self._origin else (None, None)
        if not label or label in _RECALL_WORDS:
            got = self.recall(current_xy)
            return ("breadcrumb", got) if got else (None, None)
        got = self._marks.get(label)
        return ("mark", got) if got else (None, None)


# ---------------------------------------------------------------------------
# Context seams (course_of twins) — services['places'] or base.pose_ledger
# ---------------------------------------------------------------------------


def places_of(context: Any) -> PoseLedger | None:
    """Return the PoseLedger from a SkillContext (or None).

    The embodiment publishes it as the 'places' service; VGG GoalExecutor
    contexts carry no world services, so it ALSO rides the driver
    (``base.pose_ledger``) — same seam as explore/route/viz/course. A
    foreign/older base without the attribute yields None and every place
    behavior degrades to today's (memory-less) world.
    """
    if context is None:
        return None
    services = getattr(context, "services", None) or {}
    ledger = services.get("places")
    if ledger is not None:
        return ledger
    return getattr(getattr(context, "base", None), "pose_ledger", None)


def _fresh_pose(base: Any) -> tuple[float, float, float] | None:
    """The live (x, y, yaw) — or None when odometry NEVER arrived.

    Honesty gate shared by every ledger write (where-skill twin): a driver
    exposing ``odom_age_s() is None`` is telling us its pose cache still
    holds the default zeros — recording that as an origin/breadcrumb/mark
    would fabricate a place at (0,0,0) that never existed.
    """
    if base is None:
        return None
    age_fn = getattr(base, "odom_age_s", None)
    if callable(age_fn):
        try:
            if age_fn() is None:
                return None
        except Exception:  # noqa: BLE001 — freshness probe must not raise
            return None
    try:
        pos = base.get_position()
        return (float(pos[0]), float(pos[1]), float(base.get_heading()))
    except Exception:  # noqa: BLE001 — driver boundary
        return None


def record_departure(context: Any, reason: str) -> None:
    """Best-effort ledger write at a motion command START. Never raises.

    Ensures the origin (first fresh odometry pose of the session) and pushes
    the departure breadcrumb — the pose '回到刚才的位置' resolves to later.
    Missing ledger (foreign context) or never-arrived odometry = no-op.
    """
    try:
        ledger = places_of(context)
        if ledger is None:
            return
        pose = _fresh_pose(getattr(context, "base", None))
        if pose is None:
            return
        ledger.ensure_origin(pose)
        ledger.push_breadcrumb(pose)
        oplog("places", reason,
              f"breadcrumb ({pose[0]:.2f},{pose[1]:.2f})")
    except Exception:  # noqa: BLE001 — memory seam must never break a skill
        pass


# ---------------------------------------------------------------------------
# Skills — mark_place / goto_place
# ---------------------------------------------------------------------------

_NAME_PATTERN = re.compile(
    r"(?:叫|叫做|记为|命名为|称为|called|named|as)\s*"
    r"([^\s,,。.!!??的]{1,24})")


@skill(aliases=["mark_place", "记住这里", "标记这里", "mark here", "记住这个位置",
                "记住当前位置", "标记当前位置", "remember this place",
                "remember here"], direct=True)
class RealMarkPlaceSkill:
    """Remember the CURRENT odometry pose under a name (session memory)."""

    name = "mark_place"
    description = (
        "Remember the robot's CURRENT map-frame pose as a named place "
        "(记住这里/标记这里[, 叫<名字>]); unnamed marks auto-name 地点N. The "
        "pose comes from live odometry — coordinates in params are ignored. "
        "Refuses when odometry never arrived. Places live in the CURRENT SLAM "
        "map and are lost on nav-stack restart. 记住当前位置。")
    parameters = {
        "name": {"type": "string", "default": "", "required": False,
                 "description": "place name (empty = auto 地点N)"},
    }
    preconditions: list = []
    effects: dict = {}

    @staticmethod
    def _parse_name(sources: tuple, text: str) -> str:
        for src in sources:
            if isinstance(src, dict) and src.get("name"):
                return str(src["name"]).strip()
        m = _NAME_PATTERN.search(text)
        return m.group(1).strip() if m else ""

    def execute(self, params=None, context=None, **kw):
        base = getattr(context, "base", None) if context is not None else None
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        ledger = places_of(context)
        if ledger is None:
            return SkillResult(success=False, diagnosis_code="no_place_ledger",
                               error_message=("No place ledger (go2w_real "
                                              "world only)"))
        pose = _fresh_pose(base)
        if pose is None:
            # No (0,0,0) fake marks: the pose cache is default zeros.
            return SkillResult(
                success=False, diagnosis_code="no_odometry",
                error_message=("no odometry received — cannot mark a place "
                               "from the default-zeros pose cache; bring the "
                               "stack up (bringup_skill) first"))
        sources = (params if isinstance(params, dict) else {}, kw)
        text = str(getattr(context, "instruction", "")
                   or getattr(context, "text", "") or "")
        ledger.ensure_origin(pose)
        label = ledger.mark(self._parse_name(sources, text), pose)
        oplog("skill", "mark_place",
              f"'{label}' = ({pose[0]:.2f},{pose[1]:.2f},{pose[2]:.2f}rad)")
        return SkillResult(success=True, result_data={
            "name": label,
            "x": round(pose[0], 2), "y": round(pose[1], 2),
            "yaw": round(pose[2], 3),
            "message": (f"已记住地点“{label}” = ({pose[0]:.2f}, {pose[1]:.2f})"
                        f"(当前 SLAM 地图坐标;重启导航栈后地点失效)")})


@skill(aliases=["goto_place", "回到起点", "回到刚才的位置", "回到刚才", "回去",
                "回到", "go back", "return to origin", "回起点"], direct=True)
class RealGotoPlaceSkill:
    """Drive back to a remembered place (origin / breadcrumb / named mark)."""

    name = "goto_place"
    description = (
        "Drive the REAL Go2W back to a remembered place: name=起点 -> the "
        "session origin (auto-captured at first odometry), 刚才/上一个 (or no "
        "name) -> the newest breadcrumb at least 0.3 m away, anything else -> "
        "a place stored by mark_place. Resolves the target from the ledger "
        "(odometry-recorded, never invented), resets the relative-course "
        "intent (free navigation) and blocks on navigate_to. Refuses honestly "
        "when the place is unknown. 回到起点/回到刚才的位置/回到<地点>。")
    parameters = {
        "name": {"type": "string", "default": "刚才", "required": False,
                 "description": "起点 | 刚才 | <place name from mark_place>"},
    }
    preconditions: list = []
    effects = {"base_state": "moved"}

    @staticmethod
    def _parse_name(sources: tuple, text: str, ledger: PoseLedger) -> str:
        for src in sources:
            if isinstance(src, dict) and src.get("name"):
                return str(src["name"]).strip()
        if text:
            for word in _ORIGIN_WORDS:
                if word in text:
                    return "起点"
            # A marked name quoted anywhere in the utterance wins over 刚才
            # ('回到充电桩' must not resolve to a breadcrumb).
            for label in ledger.marks:
                if label and label in text:
                    return label
        return "刚才"

    def execute(self, params=None, context=None, **kw):
        base = getattr(context, "base", None) if context is not None else None
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        ledger = places_of(context)
        if ledger is None:
            return SkillResult(success=False, diagnosis_code="no_place_ledger",
                               error_message=("No place ledger (go2w_real "
                                              "world only)"))
        pose = _fresh_pose(base)
        if pose is None:
            return SkillResult(
                success=False, diagnosis_code="no_odometry",
                error_message=("no odometry received — cannot resolve or "
                               "drive to a remembered place; bring the stack "
                               "up (bringup_skill) first"))
        sources = (params if isinstance(params, dict) else {}, kw)
        text = str(getattr(context, "instruction", "")
                   or getattr(context, "text", "") or "")
        name = self._parse_name(sources, text, ledger)
        kind, target = ledger.resolve(name, (pose[0], pose[1]))
        if target is None:
            known = list(ledger.marks)
            if ledger.origin is not None:
                known.insert(0, "起点")
            return SkillResult(success=False, diagnosis_code="unknown_place",
                               error_message=(
                f"无法解析地点 {name!r} — "
                + (f"已知地点: {', '.join(known)}" if known
                   else "本会话尚未记录任何位置(先运动或 mark_place)")
                + f";面包屑 {len(ledger.breadcrumbs)} 条"
                + ("(都在原地 0.3m 内)" if ledger.breadcrumbs
                   and name in _RECALL_WORDS else "")))
        hint = _latched_hint(base)
        if hint:
            oplog("skill", "goto_place", f"BLOCKED latched; name={name!r}")
            return SkillResult(success=False, diagnosis_code="estop_latched",
                               error_message=hint)
        # Free navigation: the relative-plan course intent is over.
        reset_course(context, "goto_place")
        # Leaving IS a motion command start — record it, so '回去' after this
        # goto returns to where we left from.
        ledger.ensure_origin(pose)
        ledger.push_breadcrumb(pose)
        tx, ty = float(target[0]), float(target[1])
        oplog("skill", "goto_place",
              f"'{name}' [{kind}] -> ({tx:.2f},{ty:.2f}) "
              f"from ({pose[0]:.2f},{pose[1]:.2f})")
        from zeno.vcli.worlds.go2w_real_skills import CFG

        ok = bool(base.navigate_to(tx, ty, timeout=CFG.nav_timeout_s))
        p = base.get_position()
        data = {"name": name, "kind": kind,
                "x": round(tx, 2), "y": round(ty, 2),
                "verify_hint": f"at({tx:.2f}, {ty:.2f}, tol=1.0)"}
        if ok:
            data["message"] = (f"已回到“{name}” ({tx:.2f}, {ty:.2f});"
                               f"verify with at({tx:.2f}, {ty:.2f}, tol=1.0)")
            return SkillResult(success=True, result_data=data)
        return SkillResult(success=False, result_data=data, error_message=(
            f"did not reach '{name}' ({tx:.2f}, {ty:.2f}); "
            f"at ({p[0]:.2f}, {p[1]:.2f})"))
