# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real turn skill — in-place rotation via the driver's rotate() cadence.

Field trace 2026-07-10 evening: '左转90度' — no rotation capability existed
anywhere in the world (not a skill, not a strategy, not a verify oracle).
This skill closes the gap: direction(left|right) + degrees (default 90;
掉头 = 180) become a SIGNED yaw delta (+left/CCW, -right/CW) handed to
``Go2WHardware.rotate`` (angular-only /teleop_cmd_vel at 5 Hz, wrap-aware
odometry tracking, _nav_abort cancel seam). Grade with ``turned(min_deg)``.

Course compensation (field bug 2026-07-13 evening; REDESIGNED after the
15:32 field disaster): the turn rotates to the ABSOLUTE intended heading
``wrap(course + requested)`` tracked by ``CourseTracker``
(go2w_real_course.py) — the commanded delta ``wrap(target - actual)`` is
<=180° BY CONSTRUCTION, so a square path stays square even when the local
planner nudged the heading during the straight legs. The course is NEVER
re-anchored from a stray yaw (the old >45° re-anchor adopted a pathFollower
reverse-flip and inverted the plan); beyond 45° the compensation is reported
PROMINENTLY (注意:检测到大幅航向偏离…) and the intent still wins.

Split file per the repo rule (files < 400 lines); registered at the skills
extension marker in ``go2w_real.py``; strategy name ``turn_skill``.
"""

from __future__ import annotations

import math
import re

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_course import course_of
from zeno.vcli.worlds.go2w_real_diag import _latched_hint, oplog, wrap_angle
from zeno.vcli.worlds.go2w_real_places import record_departure
from zeno.vcli.worlds.go2w_real_skills import _base_of

#: agent-facing direction -> rotation sign (left = +yaw/CCW, right = -yaw/CW).
_TURN_DIRECTIONS: dict[str, float] = {"left": 1.0, "right": -1.0}
_TURN_SYNONYMS: dict[str, str] = {
    "左": "left", "左转": "left", "向左": "left", "往左": "left",
    "左转弯": "left", "left": "left",
    "右": "right", "右转": "right", "向右": "right", "往右": "right",
    "右转弯": "right", "right": "right",
}
#: phrases that mean "turn around" — degrees defaults to 180, not 90.
_UTURN_WORDS: tuple[str, ...] = ("掉头", "调头", "turn around", "u-turn", "uturn")

_DEFAULT_DEGREES: float = 90.0
_MAX_DEGREES: float = 360.0
_YAW_RATE_RPS: float = 0.5  # gentle in-place rate, well inside the driver MAX_YAW_RPS guard


@skill(aliases=["turn", "左转", "右转", "转身", "掉头", "调头", "原地转",
                "原地左转", "原地右转",
                # PREFIX aliases (field trace 2026-07-13): the router prefix-
                # matches, so '往左转动30度' must start with a listed alias or
                # it takes a full LLM hop. '左转' does NOT prefix '往左转...'.
                "往左转", "向左转", "往右转", "向右转",
                "turn left", "turn right", "rotate", "turn around"], direct=True)
class RealTurnSkill:
    """Rotate the REAL Go2W in place by N degrees (odometry-tracked)."""

    name = "turn"
    description = (
        "Turn the REAL Go2W IN PLACE: direction (left/right) + degrees "
        "(default 90; 掉头=180). Publishes angular-only /teleop_cmd_vel at "
        "5 Hz for |delta|/rate seconds, tracking odometry heading (wrap-aware, "
        "stops early on arrival). Verify with turned(min_deg). "
        "原地转向(左转/右转 N 度;掉头=180)。")
    parameters = {
        "direction": {"type": "string", "default": "left", "required": False,
                      "description": "left | right (左转/右转)"},
        "degrees": {"type": "number", "default": _DEFAULT_DEGREES,
                    "required": False,
                    "description": "rotation magnitude in degrees (掉头=180)"},
        # 'angle' MIRRORS 'degrees' so the engine's VGG fast path
        # (_try_skill_goal_tree extracts generic params by NAME — it knows
        # 'angle', not 'degrees') passes the magnitude through instead of
        # dropping it and defaulting to 90. Without this a fast-pathed
        # '左转45度' turned 90° (a 45° ask → 90° turn — a REAL hazard, field
        # trace 2026-07-13). _parse_degrees already reads the 'angle' key.
        "angle": {"type": "number", "default": _DEFAULT_DEGREES,
                  "required": False,
                  "description": "rotation magnitude in degrees (mirror of "
                                 "'degrees' for the fast-path extractor)"},
    }
    preconditions: list = []
    effects = {"base_state": "turned"}

    @staticmethod
    def _parse_degrees(sources: tuple, text: str) -> float | None:
        """Explicit degrees from params/kwargs, else from the instruction text."""
        for src in sources:
            if not isinstance(src, dict):
                continue
            for key in ("degrees", "deg", "angle", "angle_deg"):
                if key in src and src[key] is not None:
                    return float(src[key])
        m = re.search(r"(-?\d+\.?\d*)\s*(?:度|°|deg)", text)
        return float(m.group(1)) if m else None

    @staticmethod
    def _parse_direction(sources: tuple, text: str) -> str:
        for src in sources:
            if isinstance(src, dict) and src.get("direction"):
                raw = str(src["direction"]).strip().lower()
                return _TURN_SYNONYMS.get(raw, raw)
        for token, en in _TURN_SYNONYMS.items():
            if token in text:
                return en
        return "left"

    def execute(self, params=None, context=None, **kw):
        base = _base_of(context)
        if base is None:
            return SkillResult(success=False, error_message="No Go2W hardware base",
                               diagnosis_code="no_base")
        sources = (params if isinstance(params, dict) else {}, kw)
        text = str(getattr(context, "instruction", "")
                   or getattr(context, "text", "") or "").lower()
        degrees = self._parse_degrees(sources, text)
        if degrees is None:
            degrees = 180.0 if any(w in text for w in _UTURN_WORDS) else _DEFAULT_DEGREES
        direction = self._parse_direction(sources, text)
        if direction not in _TURN_DIRECTIONS:
            return SkillResult(success=False, error_message=(
                f"unknown direction {direction!r} "
                f"(valid: {sorted(_TURN_DIRECTIONS)})"))
        if not math.isfinite(degrees) or not (0.0 < degrees <= _MAX_DEGREES):
            return SkillResult(success=False, error_message=(
                f"degrees {degrees!r} out of range (0, {_MAX_DEGREES:g}]"))

        hint = _latched_hint(base)
        if hint:
            oplog("skill", "turn", f"BLOCKED latched; {direction} {degrees:g}deg")
            return SkillResult(success=False, diagnosis_code="estop_latched",
                               error_message=hint)

        # Session memory: origin (once) + departure breadcrumb (a turn is a
        # motion command start; the 0.3 m recall rule skips in-place crumbs).
        record_departure(context, "turn")
        requested = math.radians(degrees) * _TURN_DIRECTIONS[direction]
        start_yaw = float(base.get_heading())
        # ABSOLUTE-TARGET TURN (field bug 2026-07-13 evening; redesigned after
        # the 15:32 disaster): a relative turn advances the INTENDED course by
        # N° — so the rotation chases the absolute target wrap(course +
        # requested). command = wrap(target - actual) is <=180° BY
        # CONSTRUCTION, which makes the old 45° "compensation cap" pointless:
        # the intent is ALWAYS honored (never a re-anchor to a stray yaw —
        # that inverted the operator's plan when the pathFollower flipped the
        # robot to -179.5°). resolve() only flags a >45° deviation so the
        # result reports the large compensation PROMINENTLY.
        tracker = course_of(context)
        command = requested
        target_course: float | None = None
        comp_deg = 0.0
        large_dev = False
        if tracker is not None:
            course, large_dev = tracker.resolve(start_yaw)
            drift = wrap_angle(course - start_yaw)
            target_course = wrap_angle(course + requested)
            command = wrap_angle(target_course - start_yaw)
            comp_deg = math.degrees(drift)
        command_deg = math.degrees(command)
        oplog("skill", "turn",
              f"{direction} {degrees:g}deg from yaw={start_yaw:.2f}rad "
              f"(course comp {comp_deg:+.1f}deg -> command {command_deg:+.1f}deg"
              f"{', LARGE DEVIATION' if large_dev else ''})")
        ok = bool(base.rotate(command, yaw_rate=_YAW_RATE_RPS))
        end_yaw = float(base.get_heading())
        turned_deg = math.degrees(wrap_angle(end_yaw - start_yaw))
        # Verify floor: 60% of the COMMANDED delta (mirrors the moved(2.0)-for-3m
        # vocab convention) — the robot must physically rotate the compensated
        # amount; wrapped deltas cap at 180°, so 掉头 verifies at 108°.
        min_deg = round(abs(command_deg) * 0.6)
        oplog("skill", "turn",
              f"{'DONE' if ok else 'FAILED'} turned={turned_deg:+.1f}deg "
              f"yaw={end_yaw:.2f}rad")
        data = {"direction": direction, "degrees": degrees,
                "turned_deg": round(turned_deg, 1),
                "command_deg": round(command_deg, 1),
                "compensation_deg": round(comp_deg, 1),
                "course_deviation_large": large_dev,
                "verify_hint": f"turned({min_deg:g})"}
        if target_course is not None:
            data["course_deg"] = round(math.degrees(target_course), 1)
        # Honest course note for the operator: compensation is never silent
        # (e.g. '右转90°(航向补偿+12°,实际下发102°)'); a >45° deviation is
        # reported PROMINENTLY — the plan heading still wins, never the stray
        # yaw (the 15:32 field disaster was a silent re-anchor to one).
        course_note = ""
        if large_dev:
            course_note = (f"(注意:检测到大幅航向偏离{abs(comp_deg):.0f}°,"
                           f"已按计划航向补偿,实际下发{abs(command_deg):.0f}°)")
        elif abs(comp_deg) >= 0.5:
            course_note = (f"(航向补偿{comp_deg:+.0f}°,"
                           f"实际下发{abs(command_deg):.0f}°)")
        if ok:
            if tracker is not None:
                # Intent advanced: the course IS the compensated target now.
                tracker.set_course(target_course)
            data["message"] = (
                f"turned {direction} {abs(turned_deg):.0f}° "
                f"(asked {degrees:g}°){course_note}; "
                f"verify with turned({min_deg:g})")
            return SkillResult(success=True, result_data=data)
        if tracker is not None:
            # Failure/cancel leaves the heading — and the intent — unknown:
            # reset rather than guess (the next command re-anchors honestly).
            tracker.reset()
        stall = ""
        if abs(turned_deg) < 3.0:
            stall = (" — zero rotation while commanding: guard likely latched "
                     "(estop/manual). Try resume_skill, then retry")
        return SkillResult(success=False, result_data=data, error_message=(
            f"rotation did not complete (turned {turned_deg:+.1f}° of "
            f"{direction} {degrees:g}°{course_note})" + stall))
