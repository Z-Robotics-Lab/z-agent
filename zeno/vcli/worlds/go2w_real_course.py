# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real course tracking — the map-frame heading-INTENT of a relative plan.

Field bug (CEO, 2026-07-13 evening): a multi-step relative plan ('前进3米,
右转90度,前进2米,右转90度…' — a square path) came out SKEWED. During each
straight leg the local planner slightly changes heading (obstacle avoidance,
path corrections); the next 'turn 90°' then rotated 90° from the DRIFTED
heading, not from the intended course — the error accumulated every leg.

The fix is a world-model fact the skills already share: the COURSE — the
map-frame heading the operator's relative plan intends right now. The robot's
own avoidance/correction rotations show up as (actual_yaw - course) and get
compensated at the next turn; straight legs run parallel to the course.

:class:`CourseTracker` is DETERMINISTIC state (Inv-1 parity with the turned()
oracle): its only inputs are odometry yaw samples the driver reads and the
operator's requested turn deltas — never an LLM-authored value. It is owned by
the embodiment and rides the driver as ``base.course_tracker`` (plus
``services['course']``), the same seam as the explore/route managers, because
VGG GoalExecutor contexts carry no world services but always wire ``base``.

Life cycle: unset at session start; ``ensure()`` anchors on the first relative
command; turns advance it; free navigation (navigate/route/explore), estop and
operator interrupt ``reset()`` it — after those the intent is simply over.
"""

from __future__ import annotations

import math
from typing import Any

from zeno.vcli.worlds.go2w_real_diag import oplog, wrap_angle

#: Small-drift cap (degrees). Within it, a course/heading deviation is planner
#: drift (avoidance nudges, path corrections) and gets folded into the next
#: turn. BEYOND it the situation is not small-drift — a big avoidance detour or
#: a manual remote takeover rotated the robot on purpose — so "compensating"
#: would command a large surprise rotation nobody asked for. Instead the course
#: RE-ANCHORS to the actual heading and the plain requested delta executes
#: (reported honestly by the skill).
REANCHOR_LIMIT_DEG: float = 45.0


class CourseTracker:
    """Map-frame intended heading (radians, wrapped); ``None`` = unset."""

    def __init__(self) -> None:
        self._course_yaw: float | None = None

    @property
    def course_yaw(self) -> float | None:
        """The intended course (wrapped radians), or None when unset."""
        return self._course_yaw

    def ensure(self, actual_yaw: float) -> float:
        """Anchor the course to *actual_yaw* IF unset; return the course.

        Anchoring happens once, at the start of a relative plan — a later
        drifted yaw must never silently re-anchor (that is exactly the drift
        we compensate; the >cap case goes through :meth:`resolve`).
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
        """Return ``(course, reanchored)`` for a command starting NOW.

        Anchors an unset course to *actual_yaw*. If the anchored course
        deviates from *actual_yaw* by more than :data:`REANCHOR_LIMIT_DEG`,
        the deviation is NOT small drift (detour / manual takeover): the
        course re-anchors to the actual heading and ``reanchored=True`` tells
        the caller to execute the plain requested motion and say so.
        """
        course = self.ensure(actual_yaw)
        drift = wrap_angle(course - float(actual_yaw))
        if abs(math.degrees(drift)) > REANCHOR_LIMIT_DEG:
            oplog("course", "tracker",
                  f"RE-ANCHOR |drift|={abs(math.degrees(drift)):.1f}deg > "
                  f"{REANCHOR_LIMIT_DEG:g}deg — detour/manual takeover, "
                  f"course := actual {math.degrees(actual_yaw):+.1f}deg")
            return self.set_course(actual_yaw), True
        return course, False

    def reset(self) -> None:
        """Forget the intent (free navigation / estop / cancel / interrupt)."""
        if self._course_yaw is not None:
            oplog("course", "tracker", "reset (intent over/unknown)")
        self._course_yaw = None


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
    """Best-effort course reset from a skill (free navigation / estop).

    Never raises — a missing tracker (foreign context) is simply a no-op.
    """
    try:
        tracker = course_of(context)
        if tracker is not None:
            oplog("course", reason, "course reset")
            tracker.reset()
    except Exception:  # noqa: BLE001 — reset seam must never break a skill
        pass
