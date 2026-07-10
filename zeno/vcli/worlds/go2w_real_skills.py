# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real skills — navigate / move_relative / stance / stop, via Go2WHardware.

Split out of ``go2w_real.py`` to keep each world file small (repo rule: files
under 400 lines). Every skill drives the REAL Go2W through the transport-agnostic
``context.base`` seam (a ``Go2WHardware`` instance) — no HTTP bridge, no ``/gt``;
navigation blocks on ``base.navigate_to`` (latched /way_point + odometry poll)
and stance/E-stop go through the base's std_srvs/Trigger helpers.

The relative-move heading math is identical to the sim world's; the ONLY
difference is the transport (hardware base vs bridge).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

from zeno.core.skill import SkillContext, skill
from zeno.core.types import SkillResult


# ---------------------------------------------------------------------------
# Config (frozen — Invariant 7 / immutability)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RealNavConfig:
    """Immutable knobs for the real-hardware world.

    ``nav_sh`` is the out-of-band lifecycle script; ``arrival_tol_m`` is the
    odometry-oracle arrival tolerance; ``nav_timeout_s`` bounds a blocking drive;
    ``relative_max_m`` caps a single relative move (larger = rejected as bad input).
    """

    nav_sh: str = "~/go2w-nuc/scripts/nav.sh"
    arrival_tol_m: float = 0.8
    nav_timeout_s: float = 120.0
    relative_default_m: float = 2.0
    relative_max_m: float = 50.0


CFG = RealNavConfig()


def nav_sh_path() -> str:
    """Resolve the nav.sh path (env GO2W_NAV_SH overrides; ~ expanded)."""
    raw = os.environ.get("GO2W_NAV_SH", "").strip() or CFG.nav_sh
    return os.path.expanduser(raw)


# ---------------------------------------------------------------------------
# Relative-direction vocabulary
# ---------------------------------------------------------------------------

_RELATIVE_DIRECTIONS: dict[str, float] = {
    "forward": 0.0,
    "backward": math.pi,
    "left": math.pi / 2,
    "right": -math.pi / 2,
}
_DIRECTION_SYNONYMS: dict[str, str] = {
    "前": "forward", "前进": "forward", "向前": "forward", "往前": "forward",
    "后": "backward", "后退": "backward", "向后": "backward", "往后": "backward",
    "倒退": "backward", "back": "backward",
    "左": "left", "向左": "left", "往左": "left",
    "右": "right", "向右": "right", "往右": "right",
}


from zeno.vcli.worlds.go2w_real_diag import (  # noqa: E402
    _latched_hint,
    _stalled_hint,
    oplog,
)


def _base_of(context: Any) -> Any:
    """Return the hardware base from a SkillContext (or None)."""
    if context is None:
        return None
    return getattr(context, "base", None)



def _target_xy(params: Any, kw: dict, context: Any) -> tuple[float, float]:
    """Extract an (x, y) map-frame target from skill params/kwargs/instruction."""
    for src in (params, kw, getattr(context, "params", None) or {},
                getattr(context, "args", None) or {}):
        if isinstance(src, dict) and "x" in src and "y" in src:
            return float(src["x"]), float(src["y"])
    text = str(getattr(context, "instruction", "") or getattr(context, "text", "") or kw)
    import re

    m = re.search(r"\(?\s*(-?\d+\.?\d*)\s*[,，]\s*(-?\d+\.?\d*)\s*\)?", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    raise ValueError(f"no (x, y) target in skill call: {text[:120]}")


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------


@skill(aliases=["navigate", "nav_to_pos", "nav", "go to", "导航", "去", "开到", "走到"])
class RealNavigateSkill:
    """Blocking navigation to ABSOLUTE map (x, y) through the nav stack.

    Publishes /way_point once (latched pursuit) and polls /state_estimation until
    arrival or timeout — all inside ``Go2WHardware.navigate_to`` (transport seam).
    Reused verbatim on hardware; no bridge, no /gt.
    """

    name = "navigate"
    description = ("Navigate the REAL Go2W to map coordinates (x, y). Blocks until "
                   "odometry-verified arrival (~0.8 m) or timeout. Publishes a "
                   "latched /way_point; the local planner drives there.")
    parameters = {
        "x": {"type": "number", "required": True, "description": "map-frame x (m)"},
        "y": {"type": "number", "required": True, "description": "map-frame y (m)"},
    }
    preconditions: list = []
    effects = {"base_state": "moved"}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        try:
            x, y = _target_xy(params, kw, context)
        except ValueError as e:
            return SkillResult(success=False, error_message=str(e))
        hint = _latched_hint(base)
        if hint:
            oplog("skill", "navigate", f"BLOCKED latched; goal=({x:.2f},{y:.2f})")
            return SkillResult(success=False, diagnosis_code="estop_latched",
                               error_message=hint)
        start = base.get_position()
        oplog("skill", "navigate", f"goal=({x:.2f},{y:.2f}) from=({start[0]:.2f},{start[1]:.2f})")
        ok = bool(base.navigate_to(x, y, timeout=CFG.nav_timeout_s))
        pos = base.get_position()
        oplog("skill", "navigate", f"{'ARRIVED' if ok else 'FAILED'} at=({pos[0]:.2f},{pos[1]:.2f})")
        if ok:
            return SkillResult(success=True, result_data={
                "message": f"arrived at ({pos[0]:.2f}, {pos[1]:.2f}); "
                           f"verify with at({x:.2f}, {y:.2f})",
                "x": round(x, 2), "y": round(y, 2)})
        return SkillResult(
            success=False, result_data={"x": round(x, 2), "y": round(y, 2)},
            error_message=(f"did not arrive; at ({pos[0]:.2f}, {pos[1]:.2f})"
                           + _stalled_hint(start, pos)))


@skill(aliases=["前进", "往前走", "向前走", "move forward", "walk forward"])
class RealMoveRelativeSkill:
    """Relative move: (direction, distance) -> map waypoint from live pose+yaw.

    Reads the current /state_estimation pose+heading from the hardware base,
    computes the map-frame target itself, then reuses navigate_to. Same math as
    the sim world; the ONLY difference is the transport (hardware base, no bridge).
    """

    name = "move_relative"
    description = (
        "Move the REAL Go2W RELATIVE to its current pose: direction "
        "(forward/backward/left/right) + distance in meters. Reads live "
        "odometry pose+yaw and drives the computed map waypoint. "
        "相对移动(前进/后退/左移/右移 N 米)。")
    parameters = {
        "distance": {"type": "number", "default": CFG.relative_default_m,
                     "required": False, "description": "distance in meters"},
        "direction": {"type": "string", "default": "forward", "required": False,
                      "description": "forward | backward | left | right"},
    }
    preconditions: list = []
    effects = {"base_state": "moved"}

    @staticmethod
    def _parse_distance(sources: tuple, text: str) -> float:
        for src in sources:
            if not isinstance(src, dict):
                continue
            for key in ("distance", "distance_m", "meters"):
                if key in src and src[key] is not None:
                    return float(src[key])
        import re

        m = re.search(r"(-?\d+\.?\d*)\s*(?:米|m\b|meter)", text)
        return float(m.group(1)) if m else CFG.relative_default_m

    @staticmethod
    def _parse_direction(sources: tuple, text: str) -> str:
        for src in sources:
            if isinstance(src, dict) and src.get("direction"):
                raw = str(src["direction"]).strip().lower()
                return _DIRECTION_SYNONYMS.get(raw, raw)
        for cn, en in _DIRECTION_SYNONYMS.items():
            if cn in text:
                return en
        return "forward"

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        sources = (params if isinstance(params, dict) else {}, kw)
        text = str(getattr(context, "instruction", "")
                   or getattr(context, "text", "") or "")
        distance = self._parse_distance(sources, text)
        direction = self._parse_direction(sources, text)
        if direction not in _RELATIVE_DIRECTIONS:
            return SkillResult(success=False, error_message=(
                f"unknown direction {direction!r} "
                f"(valid: {sorted(_RELATIVE_DIRECTIONS)})"))
        if not math.isfinite(distance) or not (0.0 < distance <= CFG.relative_max_m):
            return SkillResult(success=False, error_message=(
                f"distance {distance!r} out of range (0, {CFG.relative_max_m}] m"))

        hint = _latched_hint(base)
        if hint:
            oplog("skill", "move_relative", f"BLOCKED latched; {direction} {distance}m")
            return SkillResult(success=False, diagnosis_code="estop_latched",
                               error_message=hint)
        pos = base.get_position()
        oplog("skill", "move_relative",
              f"{direction} {distance}m from=({pos[0]:.2f},{pos[1]:.2f})")
        heading = base.get_heading() + _RELATIVE_DIRECTIONS[direction]
        tx = float(pos[0]) + distance * math.cos(heading)
        ty = float(pos[1]) + distance * math.sin(heading)
        ok = bool(base.navigate_to(tx, ty, timeout=CFG.nav_timeout_s))
        p = base.get_position()
        data = {"target_x": round(tx, 2), "target_y": round(ty, 2),
                "direction": direction, "distance_m": distance}
        if ok:
            data["message"] = (f"moved {direction} {distance}m to "
                               f"({p[0]:.2f}, {p[1]:.2f}); "
                               f"verify with at({tx:.2f}, {ty:.2f}, tol=1.0)")
            return SkillResult(success=True, result_data=data)
        return SkillResult(success=False, result_data=data, error_message=(
            f"did not reach ({tx:.2f}, {ty:.2f}); at ({p[0]:.2f}, {p[1]:.2f})"
            + _stalled_hint(pos, p)))


@skill(aliases=["standup", "stand", "stand up", "起立", "站起来", "起来"], direct=True)
class RealStandUpSkill:
    """Stand up / BalanceStand via the /standup Trigger service."""

    name = "standup"
    description = "Stand the REAL Go2W up (BalanceStand — ready to walk)."
    parameters: dict = {}
    preconditions: list = []
    effects = {"stance": "standing"}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        oplog("skill", "standup", "requested")
        ok = bool(base.standup())
        return SkillResult(success=ok, result_data={"stance": "standing"},
                           error_message="" if ok else "/standup did not succeed")


@skill(aliases=["liedown", "lie down", "sit", "趴下", "坐下", "卧倒"], direct=True)
class RealLieDownSkill:
    """Lie down via the /liedown Trigger service."""

    name = "liedown"
    description = "Lie the REAL Go2W down (safe from any state)."
    parameters: dict = {}
    preconditions: list = []
    effects = {"stance": "lying"}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        ok = bool(base.liedown())
        return SkillResult(success=ok, result_data={"stance": "lying"},
                           error_message="" if ok else "/liedown did not succeed")


def _explore_mgr_of(context: Any) -> Any:
    """Return the Go2WExploreManager from a SkillContext (or None).

    The embodiment publishes it as the 'explore' service (context.services) —
    the transport-agnostic seam, same idea as context.base for the driver.
    """
    if context is None:
        return None
    services = getattr(context, "services", None) or {}
    mgr = services.get("explore")
    if mgr is not None:
        return mgr
    # VGG GoalExecutor contexts carry no world services — the manager also
    # rides the driver (base.explore_manager), which every path wires
    # (first-REPL-contact fix, 2026-07-10).
    return getattr(getattr(context, "base", None), "explore_manager", None)


@skill(aliases=["explore", "探索", "自主探索", "全自主探索", "去探索",
                "autonomous exploration", "start exploration"], direct=True)
class RealExploreSkill:
    """Launch TARE autonomous exploration (non-blocking overlay launch).

    Starts ``nav.sh explore [scenario]`` through the embodiment's explore
    manager and returns immediately — exploration runs for minutes; progress
    is polled via go2w_real_explore(action='status') and graded by the honest
    oracle predicates ``explore_finished()`` / ``explored_progress()``.
    """

    name = "explore"
    description = (
        "Start TARE autonomous exploration on the REAL Go2W (non-blocking: "
        "launches the overlay and returns). scenario: indoor_small (default) "
        "| indoor_large | outdoor. Verify with explore_finished() and "
        "explored_progress(). 启动全自主探索。")
    parameters = {
        "scenario": {"type": "string", "default": "indoor_small",
                     "required": False,
                     "description": "indoor_small | indoor_large | outdoor"},
    }
    preconditions: list = []
    effects = {"base_state": "exploring"}

    def execute(self, params=None, context=None, **kw):
        mgr = _explore_mgr_of(context)
        if mgr is None:
            return SkillResult(success=False, diagnosis_code="no_explore_manager",
                               error_message="No explore manager (go2w_real world only)")
        scenario = "indoor_small"
        for src in (params if isinstance(params, dict) else {}, kw):
            if isinstance(src, dict) and src.get("scenario"):
                scenario = str(src["scenario"])
                break
        ok, msg = mgr.start_explore(scenario)
        data = {"scenario": scenario, "message": msg,
                "verify_hint": "explore_finished() and explored_progress() > 1.0"}
        return SkillResult(success=bool(ok), result_data=data,
                           error_message="" if ok else msg)


@skill(aliases=["stop explore", "stop exploration", "停止探索", "结束探索",
                "别探索了"], direct=True)
class RealStopExploreSkill:
    """Stop the TARE overlay: SIGINT our child + /nav_cancel (latches untouched)."""

    name = "stop_explore"
    description = (
        "Stop TARE autonomous exploration: SIGINT the overlay we launched, "
        "then clear the latched waypoint (/nav_cancel). Never releases the "
        "estop/manual latches. 停止全自主探索。")
    parameters: dict = {}
    preconditions: list = []
    effects = {"base_state": "stopped"}

    def execute(self, params=None, context=None, **kw):
        mgr = _explore_mgr_of(context)
        if mgr is None:
            return SkillResult(success=False, diagnosis_code="no_explore_manager",
                               error_message="No explore manager (go2w_real world only)")
        ok, msg = mgr.stop_explore(resume=False)
        return SkillResult(success=bool(ok), result_data={"message": msg},
                           error_message="" if ok else msg)


@skill(aliases=["stop", "停", "停下", "halt", "别动", "停止", "急停", "estop"], direct=True)
class RealStopSkill:
    """Emergency stop: latched /estop + clear the latched waypoint (/nav_cancel)."""

    name = "stop"
    description = ("EMERGENCY STOP the REAL Go2W: latch zero velocity (/estop) and "
                  "clear the navigation goal (/nav_cancel). Resume with the resume "
                  "tool.")
    parameters: dict = {}
    preconditions: list = []
    effects = {"base_state": "stopped"}

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        # Signal the cognitive abort so a blocking navigate/VGG unwinds too.
        try:
            from zeno.vcli.cognitive.abort import request_abort
            request_abort()
        except Exception:  # noqa: BLE001 — best-effort
            pass
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        estopped = bool(base.estop())
        base.nav_cancel()
        return SkillResult(success=True, result_data={
            "estop": estopped,
            "message": "E-stopped and nav goal cleared; call resume to re-enable"})
