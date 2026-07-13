# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real course tracking — the INTENT POSE (position + heading) of a plan.

Field bug #1 (CEO, 2026-07-13 evening): a square path came out SKEWED — each
'turn 90°' rotated from the planner-DRIFTED heading, not the intended course.
Fix: track the COURSE (map-frame intended heading) and fold drift into turns.

FIELD DISASTER #2 (oplog 2026-07-13 15:32-15:34, REAL robot): plan '前进3米,
左转90,前进1米,右转90,前进3米'. Leg 1 arrived 0.5 m SHORT at (2.54,-0.02)
FACING -179.5° (the twoWayDrive pathFollower flipped into reverse during the
chase). The original 45° cap then RE-ANCHORED the course to the stray yaw and
leg 2 'forward 3m' drove 3 m BACKWARD — our own compensation cap inverted the
operator's plan. Operator verdict: '避障会影响机器人对自己全局位置的判断,
多个小任务组合执行不行'.

Redesign — the tracker is the full PLAN FRAME, not just a heading:

* HEADING intent (course): anchored once at the first relative command,
  advanced only by the operator's turns. It is NEVER re-anchored from a stray
  yaw — a move is a POSITION chase (current yaw is irrelevant to its target)
  and a turn rotates to the ABSOLUTE wrap(course + delta) target, which is
  <=180° by construction. Beyond :data:`REANCHOR_LIMIT_DEG` the deviation is
  REPORTED PROMINENTLY by the skills instead of silently adopted.
* POSITION intent: where the plan says the robot should be. Moves target
  intent + d * course_direction and advance the intent by the FULL requested
  d — arrival shortfalls (radius/hesitation) and avoidance displacement
  self-correct at the next leg instead of accumulating (the operator's
  '全局意识' ask, position half). Only POSITION may re-anchor: beyond
  :data:`POSITION_REANCHOR_M` at a leg start the plan frame is stale (big
  detour / manual takeover) — re-anchor to the actual pose and say so.

:class:`CourseTracker` is DETERMINISTIC state (Inv-1 parity with the turned()
oracle): its only inputs are odometry samples the driver reads and the
operator's requested deltas — never an LLM-authored value. It is owned by
the embodiment and rides the driver as ``base.course_tracker`` (plus
``services['course']``), the same seam as the explore/route managers, because
VGG GoalExecutor contexts carry no world services but always wire ``base``.

Life cycle: unset at session start; ``ensure()``/``ensure_position()`` anchor
on the first relative command; turns advance the heading, moves advance the
position; free navigation (navigate/route/explore/goto_place), estop/stop,
operator interrupt, manual takeover and resume ``reset()`` it — after those
the intent is simply over.
"""

from __future__ import annotations

import math
from typing import Any

from zeno.vcli.worlds.go2w_real_diag import oplog, wrap_angle

#: Heading LOUD-REPORT threshold (degrees). Within it, a course/heading
#: deviation is planner drift (avoidance nudges, path corrections) and gets
#: folded into the next turn silently. BEYOND it the compensation still
#: executes — the course is the OPERATOR'S intent, full stop — but the skills
#: report it prominently (注意:检测到大幅航向偏离…). It is NO LONGER a
#: re-anchor cap: re-anchoring to a stray yaw is exactly what drove leg 2 of
#: the 2026-07-13 15:32 plan 3 m backward.
REANCHOR_LIMIT_DEG: float = 45.0

#: Position re-anchor cap (meters). A leg starting farther than this from the
#: intended trajectory is NOT arrival shortfall / small avoidance displacement
#: — a big detour or manual takeover moved the robot on purpose, so the plan
#: frame is stale: the intent position re-anchors to the actual pose (and the
#: move skill says so honestly).
POSITION_REANCHOR_M: float = 1.5


class CourseTracker:
    """Map-frame plan intent: heading (wrapped rad) + position; ``None`` = unset."""

    def __init__(self) -> None:
        self._course_yaw: float | None = None
        self._intent_xy: tuple[float, float] | None = None

    # -- heading intent (course) -------------------------------------------
    @property
    def course_yaw(self) -> float | None:
        """The intended course (wrapped radians), or None when unset."""
        return self._course_yaw

    def ensure(self, actual_yaw: float) -> float:
        """Anchor the course to *actual_yaw* IF unset; return the course.

        Anchoring happens once, at the start of a relative plan — a later
        drifted/flipped yaw must NEVER re-anchor it (that stray yaw is exactly
        what the compensation exists to correct; the 15:32 field disaster was
        a re-anchor to a -179.5° pathFollower flip).
        """
        if self._course_yaw is None:
            self._course_yaw = wrap_angle(float(actual_yaw))
            oplog("course", "tracker",
                  f"anchored course={math.degrees(self._course_yaw):+.1f}deg")
        return self._course_yaw

    def set_course(self, yaw: float) -> float:
        """Set the course to an explicit heading (wrapped); return it."""
        self._course_yaw = wrap_angle(float(yaw))
        return self._course_yaw

    def apply_turn(self, signed_rad: float) -> float:
        """Advance the intent by a signed turn delta (+CCW); return the course.

        Requires an anchored course — callers go through :meth:`ensure` /
        :meth:`resolve` first (a turn without an anchor has no intent to
        advance).
        """
        if self._course_yaw is None:
            raise RuntimeError("CourseTracker.apply_turn: course unset — "
                               "call ensure()/resolve() first")
        return self.set_course(self._course_yaw + float(signed_rad))

    def resolve(self, actual_yaw: float) -> tuple[float, bool]:
        """Return ``(course, deviates)`` for a command starting NOW.

        Anchors an unset course to *actual_yaw*. The course is NEVER
        re-anchored from a stray yaw: ``deviates=True`` only tells the caller
        the actual heading is more than :data:`REANCHOR_LIMIT_DEG` off the
        intent (detour / manual rotation / pathFollower flip) so the
        compensation must be REPORTED PROMINENTLY — the intent still wins.
        """
        course = self.ensure(actual_yaw)
        drift = wrap_angle(course - float(actual_yaw))
        deviates = abs(math.degrees(drift)) > REANCHOR_LIMIT_DEG
        if deviates:
            oplog("course", "tracker",
                  f"LARGE DEVIATION |drift|={abs(math.degrees(drift)):.1f}deg > "
                  f"{REANCHOR_LIMIT_DEG:g}deg — intent KEPT "
                  f"(course {math.degrees(course):+.1f}deg, "
                  f"actual {math.degrees(float(actual_yaw)):+.1f}deg); "
                  f"compensation will be reported loudly")
        return course, deviates

    # -- position intent -----------------------------------------------------
    @property
    def intent_xy(self) -> tuple[float, float] | None:
        """The intended plan position (x, y), or None when unset."""
        return self._intent_xy

    def ensure_position(self, actual_xy: Any) -> tuple[float, float]:
        """Anchor the intent position to *actual_xy* IF unset; return it.

        Anchoring happens once, at the first relative command of a plan —
        later actual poses never silently re-anchor (shortfalls must
        self-correct against the intended trajectory, not redefine it).
        """
        if self._intent_xy is None:
            self._intent_xy = (float(actual_xy[0]), float(actual_xy[1]))
            oplog("course", "tracker",
                  f"anchored intent position "
                  f"({self._intent_xy[0]:.2f},{self._intent_xy[1]:.2f})")
        return self._intent_xy

    def set_position(self, x: float, y: float) -> tuple[float, float]:
        """Advance the intent position to an explicit target; return it."""
        self._intent_xy = (float(x), float(y))
        return self._intent_xy

    def resolve_position(
            self, actual_xy: Any) -> tuple[tuple[float, float], bool, float]:
        """Return ``(intent_xy, reanchored, deviation_m)`` for a leg starting NOW.

        Anchors an unset intent to *actual_xy*. Within
        :data:`POSITION_REANCHOR_M` the intent is kept — arrival shortfall and
        avoidance displacement SELF-CORRECT because the next leg targets the
        intended trajectory. Beyond the cap the plan frame is stale (big
        detour / manual takeover): the intent re-anchors to the actual pose
        and ``reanchored=True`` tells the caller to say so honestly.
        """
        intent = self.ensure_position(actual_xy)
        ax, ay = float(actual_xy[0]), float(actual_xy[1])
        deviation = math.hypot(ax - intent[0], ay - intent[1])
        if deviation > POSITION_REANCHOR_M:
            oplog("course", "tracker",
                  f"RE-ANCHOR intent position |dev|={deviation:.2f}m > "
                  f"{POSITION_REANCHOR_M:g}m — detour/manual takeover, "
                  f"intent := actual ({ax:.2f},{ay:.2f})")
            return self.set_position(ax, ay), True, deviation
        return intent, False, deviation

    def reset(self) -> None:
        """Forget the intent (free navigation / estop / cancel / interrupt)."""
        if self._course_yaw is not None or self._intent_xy is not None:
            oplog("course", "tracker", "reset (intent over/unknown)")
        self._course_yaw = None
        self._intent_xy = None


def course_of(context: Any) -> CourseTracker | None:
    """Return the CourseTracker from a SkillContext (or None).

    The embodiment publishes it as the 'course' service (context.services) —
    the transport-agnostic seam; VGG GoalExecutor contexts carry no world
    services, so it ALSO rides the driver (base.course_tracker), same pattern
    as the explore/route managers. A foreign/older base without the attribute
    yields None and every course behavior degrades to today's live-yaw math.
    """
    if context is None:
        return None
    services = getattr(context, "services", None) or {}
    tracker = services.get("course")
    if tracker is not None:
        return tracker
    return getattr(getattr(context, "base", None), "course_tracker", None)


def reset_course(context: Any, reason: str) -> None:
    """Best-effort intent reset from a skill (free navigation / estop).

    Never raises — a missing tracker (foreign context) is simply a no-op.
    """
    try:
        tracker = course_of(context)
        if tracker is not None:
            oplog("course", reason, "course reset")
            tracker.reset()
    except Exception:  # noqa: BLE001 — reset seam must never break a skill
        pass
