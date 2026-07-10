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
from zeno.vcli.worlds.go2w_real_lifecycle import RealBringupSkill
from zeno.vcli.worlds.go2w_real_viz_tools import Go2WRealVizTool
from zeno.vcli.worlds.go2w_real_route_skills import (
    RealRouteViaSkill,
    RealStopRouteSkill,
)
from zeno.vcli.worlds.go2w_real_route_tools import Go2WRealRouteTool
from zeno.vcli.worlds.go2w_real_route_verify import make_route_reached
from zeno.vcli.worlds.go2w_real_verify import (
    make_at,
    make_explore_finished,
    make_explored_progress,
    make_moved,
    make_stack_ready,
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
        # Managers ALSO ride the driver: the VGG GoalExecutor builds its own
        # SkillContext (no world services) but always wires base — skills fall
        # back to these attributes (first-REPL-contact fix, 2026-07-10).
        self._base.explore_manager = self._explore
        self._base.route_manager = self._route
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
            services={"explore": self._explore, "route": self._route},
        )

    def _sync_robot_state(self) -> None:
        """SkillWrapperTool contract: state is read live from odometry — no-op."""
        return None

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
        # v2-extension point: verify — feature agents APPEND
        # `ns["<fn>"] = make_<fn>(agent)` lines ABOVE this marker (factories
        # live in go2w_real_verify.py; predicates must be fail-safe, never raise).
        return ns

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
        base = getattr(agent, "_base", None)
        if base is not None and hasattr(base, "connect"):
            try:
                base.connect()
            except Exception as exc:  # noqa: BLE001 — setup must not block the REPL
                logger.warning("go2w_real: hardware connect failed: %s", exc)

    def teardown(self) -> None:
        """Nothing process-owned to release (the driver detaches via atexit)."""
        return None

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
            }),
            verify_fn_signatures={
                "at": ("at(x: float, y: float, tol: float = 0.8) -> bool"
                       "  # /state_estimation odometry: robot within tol m of map (x, y)"),
                "moved": ("moved(min_m: float = 0.1) -> bool"
                          "  # robot displaced >= min_m from the first sample (odometry)"),
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
            },
            strategies=frozenset({
                "navigate_skill", "move_relative_skill",
                "standup_skill", "liedown_skill", "stop_skill",
                "explore_skill", "stop_explore_skill",
                "route_via_skill", "stop_route_skill",
                "bringup_skill",
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
  - bringup_skill: {"action": "start|stop"}  (导航栈生命周期; posture belongs to standup/liedown)""",
            examples=REAL_DECOMPOSE_EXAMPLES,
        )

    def derive_vocab_from_registry(self) -> bool:
        return False


# Canonical world id. Registered lazily in worlds/registry.py next to go2w.
GO2W_REAL_WORLD = "go2w_real"


def register() -> None:
    """Register this world (idempotent; replace=True). Runs on import."""
    from zeno.vcli.worlds.registry import get_world_registry

    get_world_registry().register(GO2W_REAL_WORLD, Go2WRealWorld, replace=True)


register()
