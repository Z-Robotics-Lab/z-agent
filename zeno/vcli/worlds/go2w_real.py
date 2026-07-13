# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real — REAL Unitree Go2W world, driven through the running nav stack.

Sibling of the ``go2w`` sim world (Isaac digital twin). Same CLI, same tool /
skill / verify seams — but every command goes through the nav stack running on
THIS NUC over its existing ROS2 interface (``Go2WHardware``), with NO
``unitree_sdk2`` dependency and NO HTTP bridge (CEO ruling 2026-07-10).

The verify oracle is ``/state_estimation`` odometry, read by ``Go2WHardware``
(Inv-1: there is no ``/gt`` on hardware, so ``at``/``moved`` grade on the pose
the local planner itself estimates — the actor cannot forge it). Lifecycle is
out-of-band via ``~/go2w-nuc/scripts/nav.sh``.

Plug-and-play (Invariants 3/4): a first-class BYO world registered lazily in
worlds/registry.py next to ``go2w``. It registers tools + skills + a verify
namespace + a persona, disables the kernel sim/diag/system categories that are
meaningless or misleading on hardware, and declares ``go2w_real`` as an
essential router category — ZERO kernel edits. rclpy stays out of module import
(the driver imports it lazily), so importing this world never needs a ROS env.

This module is the slim world + embodiment; the skills, tools and verify
predicates live in sibling files (repo rule: files under 400 lines):
  - go2w_real_skills.py :: navigate / move_relative / stance / stop / explore
  - go2w_real_tools.py  :: bringup(nav.sh) / navigate / where / stop / manual /
                           resume / explore (TARE overlay lifecycle)
  - go2w_real_verify.py :: at / moved / explore_finished / explored_progress
  - hardware seam       :: go2w_hw_explore.py (overlay manager + honest oracle)

v2 EXTENSION SEAMS: the '# v2-extension point: {tools,skills,verify,vocab}'
markers below are APPEND-ONLY registration sections for the parallel feature
agents (route-mode etc.) — add lines above a marker, never edit existing ones.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from zeno.core.skill import SkillContext, SkillRegistry
from zeno.hardware.base import ensure_finite_nav_goal
from zeno.vcli.worlds.base import DecomposeVocab
from zeno.vcli.worlds.go2w_real_skills import (
    RealExploreSkill,
    RealLieDownSkill,
    RealMoveRelativeSkill,
    RealNavigateSkill,
    RealStandUpSkill,
    RealStopExploreSkill,
    RealStopSkill,
)
from zeno.vcli.worlds.go2w_real_tools import (
    Go2WRealBringupTool,
    Go2WRealExploreTool,
    Go2WRealManualTool,
    Go2WRealNavigateTool,
    Go2WRealResumeTool,
    Go2WRealStopTool,
    Go2WRealWhereTool,
)
from zeno.vcli.worlds.go2w_real_lifecycle import RealBringupSkill, RealResumeSkill
from zeno.vcli.worlds.go2w_real_ops_skills import RealVizSkill, RealWhereSkill
from zeno.vcli.worlds.go2w_real_turn_skills import RealTurnSkill
from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool, VizOverlaySession
from zeno.vcli.worlds.go2w_real_route_skills import (
    RealRouteViaSkill,
    RealStopRouteSkill,
)
from zeno.vcli.worlds.go2w_real_route_tools import Go2WRealRouteTool
from zeno.vcli.worlds.go2w_real_route_verify import make_route_reached
from zeno.vcli.worlds.go2w_real_course import CourseTracker
from zeno.vcli.worlds.go2w_real_places import (
    PoseLedger,
    RealGotoPlaceSkill,
    RealMarkPlaceSkill,
)
from zeno.vcli.worlds.go2w_real_verify import (
    make_at,
    make_course_locked,
    make_explore_finished,
    make_explored_progress,
    make_moved,
    make_stack_ready,
    make_turned,
)
from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES

logger = logging.getLogger(__name__)

#: The agent's self-knowledge card (persona source) — editable without code.
_CAPABILITIES_MD = Path(__file__).with_name("go2w_real_capabilities.md")


# ---------------------------------------------------------------------------
# Embodiment — a hardware-backed agent (Go2WHardware base + skill registry)
# ---------------------------------------------------------------------------


class Go2WRealEmbodiment:
    """Minimal embodiment: a Go2WHardware base + the real skill registry.

    ``_base`` is the VGG readiness criterion and the verify oracle source. The
    driver is CONSTRUCTED here but NOT connected (offline-safe); the world's
    ``setup`` hook connects it once the session starts (so importing/building the
    world never needs a ROS env).
    """

    def __init__(self) -> None:
        from zeno.hardware.ros2.go2w_hw import Go2WHardware
        from zeno.hardware.ros2.go2w_hw_explore import Go2WExploreManager
        from zeno.hardware.ros2.go2w_hw_route import Go2WRouteManager

        self._base = Go2WHardware()
        # Overlay-session managers share the base driver (its node hosts the
        # oracle subscriptions; its Trigger helpers do the safety teardown).
        self._explore = Go2WExploreManager(self._base)
        self._route = Go2WRouteManager(self._base)
        # ONE viz overlay session shared by the go2w_real_viz TOOL and the
        # open_viz SKILL — the two faces can never double-launch RViz.
        self._viz = VizOverlaySession()
        # Heading-INTENT (course) tracker: the map-frame heading a relative
        # plan means right now (field bug CEO 2026-07-13: planner drift skewed
        # square paths). Deterministic state shared by move_relative/turn and
        # the course_locked() oracle. Session start = unset.
        self._course = CourseTracker()
        # Spatial SESSION MEMORY (CEO directive 2026-07-13 night): origin +
        # breadcrumbs + named marks, all odometry-recorded (Inv-1). Unset at
        # session start; motion skills / where fill it deterministically.
        self._places = PoseLedger()
        # Managers ALSO ride the driver: the VGG GoalExecutor builds its own
        # SkillContext (no world services) but always wires base — skills fall
        # back to these attributes (first-REPL-contact fix, 2026-07-10).
        self._base.explore_manager = self._explore
        self._base.route_manager = self._route
        self._base.viz_manager = self._viz
        self._base.course_tracker = self._course
        self._base.pose_ledger = self._places
        self._skill_registry = SkillRegistry()
        self._skill_registry.register(RealNavigateSkill())
        self._skill_registry.register(RealMoveRelativeSkill())
        self._skill_registry.register(RealStandUpSkill())
        self._skill_registry.register(RealLieDownSkill())
        self._skill_registry.register(RealStopSkill())
        self._skill_registry.register(RealExploreSkill())
        self._skill_registry.register(RealStopExploreSkill())
        self._skill_registry.register(RealRouteViaSkill())
        self._skill_registry.register(RealStopRouteSkill())
        self._skill_registry.register(RealBringupSkill())
        self._skill_registry.register(RealResumeSkill())
        self._skill_registry.register(RealTurnSkill())
        self._skill_registry.register(RealVizSkill())
        self._skill_registry.register(RealWhereSkill())
        self._skill_registry.register(RealMarkPlaceSkill())
        self._skill_registry.register(RealGotoPlaceSkill())
        # v2-extension point: skills — feature agents APPEND
        # `self._skill_registry.register(<Skill>())` lines ABOVE this marker
        # (one per line; never edit or reorder the existing registrations).

    def _build_context(self) -> SkillContext:
        """SkillWrapperTool contract: execution context bound to this base.

        ``services`` is the seam for session-scoped managers (explore today;
        route next) — skills reach them via ``context.services[<name>]``.
        """
        return SkillContext(
            bases={"go2w": self._base},
            services={"explore": self._explore, "route": self._route,
                      "viz": self._viz, "course": self._course,
                      "places": self._places},
        )

    def _sync_robot_state(self) -> None:
        """SkillWrapperTool contract: state is read live from odometry — no-op."""
        return None

    def recovery_hints(self) -> dict[str, str]:
        """World-honest recovery hints (SkillWrapperTool override contract).

        Merged OVER the kernel ``_RECOVERY_HINTS`` on a skill failure — so a
        ``no_base`` failure on the real dog steers the model to go2w_real_bringup
        (the real health/lifecycle source of truth) instead of the sim-era
        ``start_simulation`` (a tool this world DISABLES). ``estop_latched`` names
        the resume path required after stop_skill. Only the codes this world wants
        to change are listed; every other code keeps its kernel default.
        """
        return {
            "no_base": (
                "No robot connected. Bring up the nav stack with "
                "go2w_real_bringup(action='start') — status is the source of truth."
            ),
            "estop_latched": (
                "E-stop/manual latch is engaged. Call resume_skill (解除急停) "
                "before any motion; go2w_real_bringup does NOT clear it."
            ),
        }

    # native_loop base contract (blocking navigate through the driver).
    def navigate_to(self, x: float, y: float, timeout: float = 120.0) -> bool:
        # E190 goal boundary: reject NaN/inf here too (defense-in-depth — this
        # embodiment is a distinct navigate_to sink reachable from native_loop;
        # the driver guards again before the topic).
        ensure_finite_nav_goal(x, y, "Go2WRealEmbodiment.navigate_to")
        return bool(self._base.navigate_to(x, y, timeout=timeout))

    def get_position(self):
        pos = self._base.get_position()
        return (pos[0], pos[1])

    def get_heading(self):
        return float(self._base.get_heading())

    def get_pose(self):
        pos = self._base.get_position()
        return (pos[0], pos[1], float(self._base.get_heading()))


# ---------------------------------------------------------------------------
# World — the plug-and-play adapter
# ---------------------------------------------------------------------------


class Go2WRealWorld:
    """World Protocol duck-typed impl for the REAL Go2W (no kernel subclassing)."""

    name = "go2w-real"

    def is_robot(self) -> bool:
        return True

    def persona_blocks(self) -> tuple[str, str]:
        """Self-knowledge, loaded from ``go2w_real_capabilities.md``.

        The md IS the agent's capability card (product doctrine, CEO
        2026-07-10): editing it changes what the agent knows it can do, with
        no code change. Falls back to a minimal safe persona if the file is
        missing — never crashes the CLI.
        """
        try:
            text = _CAPABILITIES_MD.read_text(encoding="utf-8")
            head, tail = text.split("<!-- persona-split -->", 1)
            if head.strip() and tail.strip():
                return head.strip(), tail.strip()
        except (OSError, ValueError) as exc:  # missing file / no marker
            logging.getLogger(__name__).warning(
                "go2w_real capabilities md unusable (%s) — minimal persona", exc)
        return (
            "You operate a REAL Unitree Go2W robot dog through its running "
            "navigation stack. THIS IS PHYSICAL HARDWARE — no reset, no undo; "
            "keep the E-stop in reach and act deliberately.",
            "Manage the stack with go2w_real_bringup (status is the source of "
            "truth), drive with go2w_real_navigate(x, y), stop with "
            "go2w_real_stop, verify arrivals with at(x, y).",
        )

    def register_tools(self, registry: Any, agent: Any) -> None:
        registry.register(Go2WRealBringupTool(), category="go2w_real")
        registry.register(Go2WRealNavigateTool(), category="go2w_real")
        registry.register(Go2WRealWhereTool(), category="go2w_real")
        registry.register(Go2WRealStopTool(), category="go2w_real")
        registry.register(Go2WRealManualTool(), category="go2w_real")
        registry.register(Go2WRealResumeTool(), category="go2w_real")
        registry.register(Go2WRealExploreTool(), category="go2w_real")
        registry.register(Go2WRealRouteTool(), category="go2w_real")
        registry.register(Go2WRealVizTool(), category="go2w_real")
        # v2-extension point: tools — feature agents APPEND
        # `registry.register(<Tool>(), category="go2w_real")` lines ABOVE this
        # marker (and add the tool name to _EXPECTED_TOOLS in
        # tests/vcli/test_world_go2w_real.py — it pins the category by equality).
        # Disable kernel categories that are meaningless / misleading on this
        # hardware (mirrors go2w.py:759): 'sim' (MuJoCo start/stop would mis-route
        # 'start' away from the real stack); 'diag'/'system' read MuJoCo-era paths
        # or the host default ROS domain, not the nav stack's ROS_DOMAIN_ID=20, so
        # they return empty/misleading data. Zero friendly-fire — none hold a
        # go2w_real tool; go2w_real_bringup(status) is the health source of truth.
        disable = getattr(registry, "disable_category", None)
        if callable(disable):
            disable("sim")
            disable("diag")
            disable("system")

    def essential_categories(self) -> frozenset[str]:
        """Keep the world's own tool category in scope on the routed path."""
        return frozenset({"go2w_real"})

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        """Contribute the hardware oracle predicates (odometry + explore)."""
        ns: dict[str, Any] = {
            "at": make_at(agent),
            "moved": make_moved(agent),
            "explore_finished": make_explore_finished(agent),
            "explored_progress": make_explored_progress(agent),
        }
        ns["route_reached"] = make_route_reached(agent)
        ns["stack_ready"] = make_stack_ready(agent)
        ns["turned"] = make_turned(agent)
        ns["course_locked"] = make_course_locked(agent)
        # v2-extension point: verify — feature agents APPEND
        # `ns["<fn>"] = make_<fn>(agent)` lines ABOVE this marker (factories
        # live in go2w_real_verify.py; predicates must be fail-safe, never raise).
        return ns

    def verify_namespace_deny(self) -> frozenset[str]:
        """Engine-stub names this HARDWARE world does not serve (opt-OUT, Inv-1).

        Field forensics 2026-07-10 ('verdict 0/N grounded'): the engine seeds
        these sim/perception names into the verifier namespace BEFORE the world
        merge; the additive merge could never remove them, so they leaked into
        ``verify_oracle_names`` and the model was TAUGHT phantom predicates that
        evaluate stub-falsy on the real dog. Denying them (applied AFTER the
        merge — remove-only, strictly stricter) makes the advertised verify
        vocab exactly what this world serves: at/moved/explore_finished/
        explored_progress/route_reached/stack_ready + the kernel dev predicates.

        get_position/get_heading are denied ON PURPOSE (audited before denying):
        the world-context display (engine._build_world_context), robot_context,
        and actor_causation.capture all read the BASE OBJECT directly — never
        the verifier namespace — so nothing load-bearing consumes these entries.
        Their only namespace role was verify eval + the advertised oracle list,
        where a raw-pose read invites the model to self-author uncalibrated
        pose compares instead of the tol-calibrated at()/moved() odometry
        oracles. at_position/facing are absent on this world today (they are
        sim-world merges) — denied defensively so no future engine seeding can
        resurrect them here.
        """
        return frozenset({
            "describe_scene", "detect_objects", "certainty", "last_seen",
            "objects_in_room", "find_object", "room_coverage",
            "predict_navigation", "at_position", "facing",
            "get_position", "get_heading",
        })

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        return None

    def build_embodiment(self) -> "Go2WRealEmbodiment":
        """BYO front door: a hardware-backed agent (no --sim). Driver unconnected
        until setup() so building the world needs no ROS env."""
        return Go2WRealEmbodiment()

    def setup(self, agent: Any) -> None:
        """Connect the hardware driver once, at session start (best-effort).

        A missing ROS env / down stack leaves the driver disconnected (tools then
        report 'no base' and steer the user to go2w_real_bringup) — never a crash.
        """
        import os

        from zeno.vcli.worlds.go2w_real_diag import oplog
        oplog("env", "session", (
            f"domain={os.environ.get('ROS_DOMAIN_ID', 'UNSET!')} "
            f"rmw={os.environ.get('RMW_IMPLEMENTATION', 'UNSET!')} "
            f"cyclonedds_uri={'set' if os.environ.get('CYCLONEDDS_URI') else 'UNSET!'}"))
        base = getattr(agent, "_base", None)
        if base is not None and hasattr(base, "connect"):
            try:
                base.connect()
                oplog("env", "session", "driver connected")
            except Exception as exc:  # noqa: BLE001 — setup must not block the REPL
                oplog("env", "session", f"driver connect FAILED: {exc}")
                logger.warning("go2w_real: hardware connect failed: %s", exc)

    def on_operator_interrupt(self, agent: Any) -> str:
        """Ctrl+C during a blocking turn: cancel motion, keep the session alive.

        Deliberately NOT an E-stop (interrupt = "stop pursuing that goal",
        the operator can still say stop for the latched zero). Never raises.
        """
        from zeno.vcli.worlds.go2w_real_diag import oplog
        base = getattr(agent, "_base", None) if agent is not None else None
        try:
            if base is not None and hasattr(base, "cancel_navigation"):
                base.cancel_navigation()
            # A cancelled motion leaves the heading intent unknown — reset the
            # course so the next relative command re-anchors honestly (same
            # rule as the stop skill; base.course_tracker is the driver-ride
            # seam, so this works from any context).
            tracker = getattr(base, "course_tracker", None)
            if tracker is not None:
                tracker.reset()
            from zeno.vcli.cognitive.abort import request_abort
            request_abort()
        except Exception:  # noqa: BLE001 — interrupt path must never raise
            pass
        oplog("lifecycle", "interrupt", "operator Ctrl+C — goal cancelled")
        return ("已中断:导航目标已取消,机器人将停止追踪。需要锁死急停请说 stop;"
                "直接继续对话即可。")

    def teardown(self) -> None:
        """Nothing process-owned to release (the driver detaches via atexit)."""
        return None

    def supports_pose_reset(self) -> bool:
        """False: the REPL ``/reset`` sim pose-flag has NO consumer on hardware.

        ``/reset`` writes ``/tmp/vector_reset_pose`` — read ONLY by the MuJoCo sim
        vnav bridge (``scripts/go2_vnav_bridge.py`` -> ``MuJoCoGo2.reset_pose``).
        The real driver is ROS2/nav.sh and never reads that flag, so on go2w_real
        the command would be a dead no-op dressed up as a working tip-over recovery.
        Declaring False makes ``/reset`` refuse honestly and point at the real
        recovery path (standup_skill + resume_skill). Opt-OUT: a world that omits
        this hook keeps the flag-writing behaviour byte-identical (dev/sim).
        """
        return False

    def world_context_ttl(self) -> float:
        """0.0 — the plan-time world context must always read the LIVE pose.

        Global-awareness hook A (CEO directive 2026-07-13: the agent must
        always know its live global coordinates + orientation). The kernel's
        5 s cache exists to protect EXPENSIVE sensor/graph queries (sim scene
        graphs); this world's Position/Heading contribution is a CACHED driver
        attribute the /state_estimation subscription already paid for — a
        zero-cost read — while at 0.6 m/s a 5 s-stale pose is up to 3 m wrong
        at plan time. Opt-in hook: a world without it keeps the 5 s default.
        """
        return 0.0

    def live_status_line(self, agent: Any) -> str:
        """ONE live-state line the native loop injects before EVERY model call.

        Global-awareness hook B (same CEO directive): pose x/y (2 decimals),
        yaw in BOTH degrees and radians (the model does mental geometry in
        degrees but the verify oracles / cos-sin math speak radians), the
        course INTENT + live drift when a relative plan anchored one
        (base.course_tracker), and the odometry age. Honesty first: when
        ``odom_age_s()`` is None (stack down / never connected) — or any pose
        read fails — the line says so instead of fabricating the driver's
        (0, 0) defaults (the same 永真 trap stack_ready() closed). Never raises.
        """
        import math

        base = getattr(agent, "_base", None) if agent is not None else None
        fallback = "(no odometry — stack down?)"
        if base is None:
            return fallback
        try:
            age_fn = getattr(base, "odom_age_s", None)
            age = age_fn() if callable(age_fn) else None
            if age is None:
                return fallback
            pos = base.get_position()
            yaw = float(base.get_heading())
        except Exception:  # noqa: BLE001 — live status is best-effort, never fatal
            return fallback
        line = (
            f"pose x={pos[0]:.2f} y={pos[1]:.2f} "
            f"yaw={math.degrees(yaw):+.1f}deg ({yaw:+.3f}rad)"
        )
        tracker = getattr(base, "course_tracker", None)
        course = getattr(tracker, "course_yaw", None) if tracker is not None else None
        if course is not None:
            from zeno.vcli.worlds.go2w_real_diag import wrap_angle

            drift = wrap_angle(float(course) - yaw)
            line += (
                f" | course {math.degrees(float(course)):+.1f}deg"
                f" (drift {math.degrees(drift):+.1f}deg)"
            )
        return line + f" | odom age {age:.1f}s"

    def decompose_vocab(self) -> DecomposeVocab | None:
        return DecomposeVocab(
            planner_intro=(
                "Drive a REAL Go2W robot dog through its nav stack. Navigation "
                "goals are map-frame (x, y); verify arrival with at(x, y). For "
                "RELATIVE motion ('往前走 2 米', 'move forward 3 m') use "
                "move_relative_skill — it computes the map target from the live "
                "odometry pose+yaw at runtime. For its verify, compute the "
                "expected target from the world context's Position (x, y) and "
                "Heading h: forward d meters => target = (x + d*cos(h), "
                "y + d*sin(h)); verify with at(tx, ty, tol=1.5). This is HARDWARE: "
                "no reset; if anything is wrong the stop_skill E-stops the robot."
            ),
            # v2-extension point: vocab — feature agents APPEND their strategy
            # to strategy_descriptions AND strategies (the sets must stay equal,
            # a test pins it), plus any new verify fn to verify_functions AND
            # verify_fn_signatures, plus a strategy_params_help line.
            verify_functions=frozenset({
                "at", "moved", "explore_finished", "explored_progress",
                "route_reached",  # v2 route mode (far_planner arrival oracle)
                "stack_ready",    # lifecycle: odometry flowing = stack truly up
                "turned",         # v2 in-place rotation (odometry yaw, wrap-aware)
                "course_locked",  # heading-intent tracking (drift-compensated turns)
            }),
            verify_fn_signatures={
                "at": ("at(x: float, y: float, tol: float = 0.8) -> bool"
                       "  # /state_estimation odometry: robot within tol m of map (x, y)"),
                "moved": ("moved(min_m: float = 0.1) -> bool"
                          "  # the LAST move command displaced >= min_m "
                          "(odometry position vs driver anchor)"),
                "explore_finished": (
                    "explore_finished() -> bool"
                    "  # TARE's OWN finish signal (/exploration_finish latched True)"),
                "explored_progress": (
                    "explored_progress() -> float"
                    "  # meters travelled during explore (odometry-integrated, monotone)"),
                "route_reached": (
                    "route_reached() -> bool"
                    "  # far_planner route arrival: robot reached the goto goal (odometry)"),
                "stack_ready": (
                    "stack_ready() -> bool"
                    "  # nav stack up: fresh /state_estimation odometry within 3s"),
                "turned": (
                    "turned(min_deg: float = 30.0) -> bool"
                    "  # the LAST turn command rotated >= min_deg (odometry yaw "
                    "vs driver anchor; wrapped delta caps at 180)"),
                "course_locked": (
                    "course_locked(tol_deg: float = 10.0) -> bool"
                    "  # heading within tol of the plan's INTENDED course "
                    "(drift-compensated relative plans); False when no course"),
            },
            strategy_descriptions={
                "navigate_skill": ("Drive to ABSOLUTE map (x, y); blocks until "
                                   "odometry-verified arrival"),
                "move_relative_skill": ("Move RELATIVE to current pose "
                                        "(forward/backward/left/right by N meters); "
                                        "computes the map target from live pose+yaw"),
                "standup_skill": "Stand the robot up (BalanceStand)",
                "liedown_skill": "Lie the robot down",
                "stop_skill": "EMERGENCY STOP: E-stop + cancel the nav goal",
                "explore_skill": ("Launch TARE autonomous exploration (non-blocking); "
                                  "verify explore_finished() and explored_progress()"),
                "stop_explore_skill": ("Stop the exploration overlay (SIGINT + "
                                       "/nav_cancel; never touches the E-stop latch)"),
                "route_via_skill": ("Drive to a FAR map (x, y) via far_planner GLOBAL "
                                    "route planning (routes around obstacles); blocks "
                                    "until arrival, verify route_reached()"),
                "stop_route_skill": ("Stop the far_planner route overlay (SIGINT + "
                                     "/nav_cancel; never touches the E-stop latch)"),
                "bringup_skill": ("Nav-stack LIFECYCLE: start (launch + block "
                                  "until SLAM-ready, verify stack_ready()) or "
                                  "stop. 启动/关闭导航栈 — NOT standing up"),
                "resume_skill": ("Release the E-stop/manual latch so motion works "
                                 "again — REQUIRED after stop_skill. 解除急停/恢复自主"),
                "turn_skill": ("Turn IN PLACE by direction+degrees (左转/右转; "
                               "掉头=180); verify turned(min_deg) — use ~60% of "
                               "the request (wrapped delta caps at 180)"),
                "open_viz_skill": ("Open RViz for the operator (view main|explore|"
                                   "route — match the running planner); "
                                   "already-open dedupes to ok. 打开可视化"),
                "where_skill": ("Report the current map-frame pose {x, y, yaw} "
                                "from live odometry, plus origin distance/"
                                "bearing, course drift and marked places. "
                                "查询当前位姿"),
                "mark_place_skill": ("Remember the CURRENT odometry pose as a "
                                     "named place (记住这里[叫X]; unnamed = "
                                     "地点N); refuses before odometry arrives"),
                "goto_place_skill": ("Drive back to a remembered place: 起点="
                                     "session origin, 刚才=newest breadcrumb "
                                     "(>=0.3m away), else a mark_place name; "
                                     "resets course intent; verify with the "
                                     "returned at(x, y) hint. 回到起点/回到刚才的位置"),
            },
            strategies=frozenset({
                "navigate_skill", "move_relative_skill",
                "standup_skill", "liedown_skill", "stop_skill",
                "explore_skill", "stop_explore_skill",
                "route_via_skill", "stop_route_skill",
                "bringup_skill", "resume_skill",
                "turn_skill", "open_viz_skill", "where_skill",
                "mark_place_skill", "goto_place_skill",
            }),
            strategy_params_help="""\
  - navigate_skill: {"x": <map-frame meters float>, "y": <map-frame meters float>}
  - move_relative_skill: {"distance": <meters float>, "direction": "forward|backward|left|right"}
  - standup_skill: {}
  - liedown_skill: {}
  - stop_skill: {}
  - explore_skill: {"scenario": "indoor_small|indoor_large|outdoor"}  (optional; default indoor_small)
  - stop_explore_skill: {}
  - route_via_skill: {"x": <map-frame meters float>, "y": <map-frame meters float>}  (FAR goal via far_planner)
  - stop_route_skill: {}
  - bringup_skill: {"action": "start|restart|stop"}  (start=幂等,栈在跑则不动; restart=强制重建; posture belongs to standup/liedown)
  - resume_skill: {}  (解除急停;stop 之后、任何运动之前)
  - turn_skill: {"direction": "left|right", "degrees": <float, default 90>}  (掉头=180; verify turned(~0.6*degrees))
  - open_viz_skill: {"view": "main|explore|route"}  (optional; default main — match the running planner)
  - where_skill: {}
  - mark_place_skill: {"name": "<地点名>"}  (optional; default auto 地点N — the pose comes from odometry, never from you)
  - goto_place_skill: {"name": "起点|刚才|<地点名>"}  (起点=session origin, 刚才=newest breadcrumb >=0.3m away)""",
            examples=REAL_DECOMPOSE_EXAMPLES,
            # SUPPRESS the class-default '## Loop Example' (it teaches
            # detect_objects(), a phantom here — field forensics 2026-07-10).
            # This world has no list-producing detect step to loop over; if a
            # v2 feature ever adds one, replace '' with an example built from
            # THIS world's verify_functions.
            foreach_example="",
        )

    def derive_vocab_from_registry(self) -> bool:
        return False

    def disable_keyword_ladder(self) -> bool:
        """True: opt OUT of the kernel's go2-SIM keyword ladder (StrategySelector).

        The ladder encodes the robot / go2-SIM vocabulary — navigate with a {room}
        param, a 'stand' skill, walk_forward/turn primitives, look/detect skills.
        This world serves DIFFERENT names + param shapes (navigate{x,y}, standup, a
        stop SKILL, no look/detect/walk_forward), so a fabricated ladder target for
        an empty-strategy step would misdispatch or no-op. Opting out routes such
        steps by THIS world's registry aliases (前进->move_relative, 站起来->standup,
        去->navigate) or the loud fallback. Latent in practice (the DecomposeVocab
        above fills explicit strategies) but strictly safer. Opt-OUT hook: a world
        that omits it keeps the ladder ON (robot/go2-sim byte-identical)."""
        return True


# Canonical world id. Registered lazily in worlds/registry.py next to go2w.
GO2W_REAL_WORLD = "go2w_real"


def register() -> None:
    """Register this world (idempotent; replace=True). Runs on import."""
    from zeno.vcli.worlds.registry import get_world_registry

    get_world_registry().register(GO2W_REAL_WORLD, Go2WRealWorld, replace=True)


register()
