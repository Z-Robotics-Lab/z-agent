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

PERSISTENCE (2026-07-14, relocalization LIVE): when running on a PRE-BUILT map
(nav.sh start <map> -> arise_slam localization), the map frame is STABLE across
restarts, so NAMED marks now persist to ~/maps/<map>/places.json and reload at
session setup (预建图模式下地点跨重启有效). Breadcrumbs + origin stay session-
only. In FRESH-MAPPING mode (no active map) the frame is rebuilt each run, so
marks remain session-only — the card teaches this split. Whether a map is active
is nav.sh's current_map.txt handshake (go2w_real_maps.current_map()).
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

    def load_marks(self, marks: dict[str, tuple[float, float, float]]) -> None:
        """Merge persisted NAMED marks into the ledger (pre-built map load).

        Additive: origin + breadcrumbs (session-only) are untouched; a loaded
        name overwrites a same-named session mark. Every value is coerced to a
        float triple — a malformed entry is skipped, never raised.
        """
        for name, triple in (marks or {}).items():
            try:
                pose = (float(triple[0]), float(triple[1]), float(triple[2]))
            except (TypeError, ValueError, IndexError):
                continue
            self._marks[str(name)] = pose

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
        got = self._resolve_mark(label)
        return ("mark", got) if got else (None, None)

    def _resolve_mark(
            self, label: str) -> tuple[float, float, float] | None:
        """Fuzzy-resolve a mark NAME to a pose; None when unknown OR ambiguous.

        Tiers, first UNAMBIGUOUS hit wins: (1) exact, (2) case-insensitive
        exact ('harry' -> 'Harry ...'), (3) case-insensitive substring either
        direction ('harry' <-> 'Harry Z Lab 工位'; 'go 公司厨房' -> '公司厨房').
        A tier matching >1 mark yields None — a place the robot DRIVES to must
        never be a guess (Inv-1 parity): the caller then refuses and lists the
        candidates so the operator disambiguates instead of rolling to the
        wrong landmark.
        """
        label = str(label or "").strip()
        if not label:
            return None
        if label in self._marks:                              # 1. exact
            return self._marks[label]
        low = label.lower()
        ci = [v for k, v in self._marks.items() if k.lower() == low]
        if len(ci) == 1:                                      # 2. case-fold
            return ci[0]
        if len(ci) >= 2:
            return None
        subs = [v for k, v in self._marks.items()             # 3. substring
                if low in k.lower() or k.lower() in low]
        return subs[0] if len(subs) == 1 else None

    def match_candidates(self, label: str) -> list[str]:
        """Names that fuzzily match *label* (case-insensitive substring, either
        direction) — for a 'did you mean …?' refusal. Empty when nothing is
        close. Exact/case-fold hits are included too (they're substrings)."""
        low = str(label or "").strip().lower()
        if not low:
            return []
        return [k for k in self._marks
                if low in k.lower() or k.lower() in low]


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


def refresh_marks_from_disk(ledger: Any) -> int:
    """Re-read ~/maps/<active>/places.json into *ledger* (additive merge).

    Returns the number of named marks merged; 0 on no-ledger / no-active-map /
    any error. NEVER raises — a stale-memory refresh must not break a skill.

    WHY (field bug 2026-07-15): named places are written by a SEPARATE process
    (``nav mark …``) and the active map can flip AFTER the REPL started, so the
    one-shot setup load (:meth:`Go2WRealWorld._load_persistent_places`) goes
    stale and the agent 'can't read any landmarks'. Every place query re-reads
    the tiny JSON so the ledger always mirrors what ``nav mark list`` shows.
    Additive: session origin/breadcrumbs and same-named session marks are
    preserved except a disk mark of the same name wins (disk is the record).
    """
    if ledger is None or not hasattr(ledger, "load_marks"):
        return 0
    try:
        from zeno.vcli.worlds.go2w_real_maps import (
            current_map,
            home_place,
            load_places,
        )

        active = current_map()
        if active is None:  # fresh-mapping / down stack -> session-only places
            return 0
        marks = load_places(active)
        home = home_place(active)
        if home is not None:
            marks.setdefault("home", home)
            marks.setdefault("家", home)
        ledger.load_marks(marks)
        return len(marks)
    except Exception:  # noqa: BLE001 — memory refresh must never break a skill
        return 0


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
        # PERSISTENCE (2026-07-14): on a pre-built map (localization mode) the
        # map frame is STABLE across restarts, so a named mark can survive to
        # ~/maps/<map>/places.json. In fresh-mapping mode (no active map) the
        # frame is rebuilt each run, so marks stay session-only — the honest
        # limit the card teaches. current_map() is nav.sh's handshake.
        from zeno.vcli.worlds.go2w_real_maps import current_map, save_places

        active_map = current_map()
        persisted = False
        if active_map is not None:
            persisted = save_places(active_map, ledger.marks)
            oplog("skill", "mark_place",
                  f"'{label}' persist -> map={active_map} ok={persisted}")
        if persisted:
            tail = f"(预建图 {active_map};已持久化,跨重启有效)"
        else:
            tail = "(当前 SLAM 地图坐标;从零建图模式下重启导航栈后地点失效)"
        return SkillResult(success=True, result_data={
            "name": label,
            "x": round(pose[0], 2), "y": round(pose[1], 2),
            "yaw": round(pose[2], 3),
            "persisted": persisted,
            "map": active_map,
            "message": (f"已记住地点“{label}” = ({pose[0]:.2f}, {pose[1]:.2f})"
                        + tail)})


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
        "precise": {"type": "boolean", "default": False, "required": False,
                    "description": ("manipulation-grade docking: after coarse "
                                    "arrival, servo to ~8cm + the place's "
                                    "recorded heading (精准进站)")},
    }
    preconditions: list = []
    effects = {"base_state": "moved"}

    @staticmethod
    def _parse_precise(sources: tuple, text: str) -> bool:
        for src in sources:
            if isinstance(src, dict) and "precise" in src:
                return bool(src["precise"])
        return any(w in text for w in ("精准", "精确", "进站", "dock"))

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
            # ('回到充电桩' must not resolve to a breadcrumb). Case/space-loose
            # so '回到harry z lab工位' still meets stored 'Harry Z Lab 工位'.
            def _squash(s: str) -> str:
                return "".join(str(s).lower().split())

            sq_text = _squash(text)
            for label in ledger.marks:
                if label and (label in text or _squash(label) in sq_text):
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
        # Mirror the on-disk store first: a name just written by `nav mark`
        # (separate process) or a map activated after this REPL started would
        # otherwise be invisible (field bug 2026-07-15).
        refresh_marks_from_disk(ledger)
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
            # Fuzzy hit >1 mark (ambiguous) -> we refused ON PURPOSE rather than
            # guess; name the near-misses so the operator says the full name.
            cands = [c for c in ledger.match_candidates(name) if c != name]
            hint = f"(近似:{'、'.join(cands)},请说全名) " if cands else ""
            return SkillResult(success=False, diagnosis_code="unknown_place",
                               error_message=(
                f"无法解析地点 {name!r} — " + hint
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
        precise = self._parse_precise(sources, text)
        if ok and precise and callable(getattr(base, "dock_to", None)):
            # Manipulation-grade fine stage (CEO 2026-07-14): servo the last
            # ~30cm to ~8cm + the place's RECORDED heading — the arm needs a
            # repeatable base pose, and marks store yaw for exactly this.
            tyaw = float(target[2]) if len(target) >= 3 else None
            docked = bool(base.dock_to(tx, ty, yaw=tyaw))
            p = base.get_position()
            data["docked"] = docked
            data["verify_hint"] = f"at({tx:.2f}, {ty:.2f}, tol=0.15)"
            oplog("skill", "goto_place",
                  f"dock '{name}' -> {'DOCKED' if docked else 'DOCK FAILED'} "
                  f"at ({p[0]:.2f},{p[1]:.2f})")
            if docked:
                data["message"] = (
                    f"已精准进站“{name}” ({p[0]:.2f}, {p[1]:.2f}, ±8cm+朝向);"
                    f"verify with at({tx:.2f}, {ty:.2f}, tol=0.15)")
                return SkillResult(success=True, result_data=data)
            return SkillResult(success=False, result_data=data, error_message=(
                f"粗导航已到“{name}”附近但精准进站失败(当前 "
                f"({p[0]:.2f}, {p[1]:.2f}))— 站位可能被挡,或急停锁存"))
        if ok:
            data["message"] = (f"已回到“{name}” ({tx:.2f}, {ty:.2f});"
                               f"verify with at({tx:.2f}, {ty:.2f}, tol=1.0)")
            return SkillResult(success=True, result_data=data)
        from zeno.vcli.worlds.go2w_real_skills import (
            _operator_override,
            _override_message,
        )

        override = _operator_override(base)
        if override is not None:
            ox, oy, _age = override
            # Course intent already reset above (free navigation); nothing more.
            oplog("skill", "goto_place",
                  f"OPERATOR OVERRIDE -> ({ox:.2f},{oy:.2f})")
            data["operator_goal_x"] = round(ox, 2)
            data["operator_goal_y"] = round(oy, 2)
            return SkillResult(
                success=False, diagnosis_code="operator_override",
                result_data=data, error_message=_override_message(ox, oy))
        return SkillResult(success=False, result_data=data, error_message=(
            f"did not reach '{name}' ({tx:.2f}, {ty:.2f}); "
            f"at ({p[0]:.2f}, {p[1]:.2f})"))


@skill(aliases=["list_places", "有哪些地点", "有哪些地标", "能去哪些地标",
                "能去哪些地方", "能去哪", "能去哪里", "可以去哪", "可以去哪里",
                "列出地点", "列出地标", "地点列表", "地标列表", "known places",
                "list places", "list landmarks", "where can i go"],
       direct=True)
class RealListPlacesSkill:
    """List the ACTIVE map's navigable named places (re-read from disk)."""

    name = "list_places"
    description = (
        "列出当前地图上所有可导航的已知地点/地标(名字 + 地图坐标),从 "
        "~/maps/<地图>/places.json 实时读取(含刚用 nav mark 记的点)。回答"
        "“你能去哪些地标 / 有哪些地点 / 可以去哪”。纯查询:不移动机器人、"
        "不需要里程计。之后用 goto_place 前往其中任意名字(名字支持大小写/"
        "子串模糊匹配)。")
    parameters: dict = {}
    preconditions: list = []
    effects: dict = {}

    def execute(self, params=None, context=None, **kw):
        ledger = places_of(context)
        if ledger is None:
            return SkillResult(
                success=False, diagnosis_code="no_place_ledger",
                error_message="No place ledger (go2w_real world only)")
        loaded = refresh_marks_from_disk(ledger)  # mirror nav-mark / map switch
        marks = ledger.marks
        specials: list[str] = []
        if ledger.origin is not None:
            specials.append("起点")
        if ledger.breadcrumbs:
            specials.append("刚才/上一个")
        data: dict[str, Any] = {
            "places": {k: [round(v[0], 2), round(v[1], 2), round(v[2], 3)]
                       for k, v in marks.items()},
            "count": len(marks),
            "map_places_loaded": loaded,
        }
        if not marks:
            msg = ("当前地图没有已标记的地点。用 nav mark(或说“记住这里叫"
                   "<名字>”)记录后即可“去<名字>”。")
            if specials:
                msg += "现可直接说:" + "、".join(specials) + "。"
            data["message"] = msg
            oplog("skill", "list_places", "0 places")
            return SkillResult(success=True, result_data=data)
        listing = "、".join(
            f"{k}({v[0]:.1f},{v[1]:.1f})" for k, v in marks.items())
        msg = f"可去的地标(共 {len(marks)} 个):{listing}。"
        if specials:
            msg += "另可说:" + "、".join(specials) + "。"
        msg += "说“去<名字>”前往(名字支持模糊匹配)。"
        data["message"] = msg
        oplog("skill", "list_places", f"{len(marks)} places")
        return SkillResult(success=True, result_data=data)
