# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Mobile pick skill — navigate to an object, then delegate to PickTopDownSkill.

Composition:
    1. Guard checks (base / arm / gripper / world_model)
    2. Resolve target via PickTopDownSkill._resolve_target
    3. Compute approach pose via compute_approach_pose
    4. Navigate if not already close enough (unless skip_navigate=True)
    5. Wait for the dog to settle
    6. Delegate to PickTopDownSkill.execute

Routes on aliases: 去拿 / 去抓 / 拿来 / 取来 / 去取 / fetch / go grab / go get
"""
from __future__ import annotations

import logging
import math
import time

from vector_os_nano.core.skill import SkillContext, skill
from vector_os_nano.core.types import SkillResult
from vector_os_nano.skills.utils.approach_pose import compute_approach_pose

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level tunables
# ---------------------------------------------------------------------------

_DEFAULT_CLEARANCE: float = 0.55       # metres from object centre to approach stop
_APPROACH_XY_TOL: float = 0.10        # metres — skip nav if already this close to approach
_APPROACH_YAW_DEG: float = 20.0       # degrees — skip nav if heading is already close
_NAV_TIMEOUT: float = 60.0            # seconds allowed for navigate_to (matches Go2 driver default)
_STABLE_MAX_SPEED: float = 0.05       # m/s — threshold for "dog is still"
_STABLE_SETTLE: float = 1.0           # seconds dog must be below max_speed
_STABLE_TIMEOUT: float = 5.0          # seconds before giving up on stabilisation


# ---------------------------------------------------------------------------
# Inline helpers
# ---------------------------------------------------------------------------


def _dist_xy(x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)


def _ang_diff(a: float, b: float) -> float:
    """Shortest signed angle difference, in [-pi, pi]."""
    d = a - b
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return d


def _wait_stable(
    base,
    max_speed: float,
    settle_duration: float,
    timeout: float,
) -> bool:
    """Return True once the dog's XY speed stays below *max_speed* for
    *settle_duration* seconds.

    Uses position deltas (no velocity API). Polls at 5 Hz.
    Returns False if *timeout* elapses before the condition is met.
    """
    poll_dt = 0.2
    prev_x, prev_y, _ = base.get_position()
    prev_t = time.monotonic()
    sustained = 0.0
    deadline = prev_t + timeout

    while time.monotonic() < deadline:
        time.sleep(poll_dt)
        now = time.monotonic()
        dt = now - prev_t
        if dt <= 0:
            continue
        cx, cy, _ = base.get_position()
        speed = math.hypot(cx - prev_x, cy - prev_y) / dt
        if speed < max_speed:
            sustained += dt
            if sustained >= settle_duration:
                return True
        else:
            sustained = 0.0
        prev_x, prev_y, prev_t = cx, cy, now

    return False


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


@skill(
    aliases=[
        "去拿", "去抓", "拿来", "取来", "去取",
        "抓起", "抓来",   # v2.3 hot-fix: route "抓起 X" to mobile variant
        "fetch", "go grab", "go get",
    ],
    direct=False,
)
class MobilePickSkill:
    """Walk the dog to a reachable pose near a known object and pick it up.

    Uses navigate_to for approach, then delegates to PickTopDownSkill.
    Object must be registered in the world model. (source: world_model)
    """

    name: str = "mobile_pick"
    description: str = (
        "Walk the dog to a reachable pose near an ALREADY-LOCALIZED object and pick it "
        "up with a top-down grasp. REQUIRES the object's 3D position to already be known "
        "in the world model (from a prior detect/look that obtained a 3D pose). It does "
        "NOT find or self-localize a target it cannot yet 3D-place — for a fresh fetch, an "
        "un-localized object, or an OUT-OF-REACH target, use perception_grasp instead "
        "(it perceives AND self-navigates). Uses navigate_to for approach, then delegates "
        "to pick_top_down. (source: world_model)"
    )
    parameters: dict = {
        "object_id": {
            "type": "string",
            "required": False,
            "description": "ID of the object in the world model.",
            "source": "world_model.objects.object_id",
        },
        "object_label": {
            "type": "string",
            "required": False,
            "description": "Label of the object (English or Chinese color descriptor).",
            "source": "world_model.objects.label",
        },
        "skip_navigate": {
            "type": "boolean",
            "required": False,
            "default": False,
            "description": "If True, skip the navigation step (debug use).",
            "source": "static",
        },
    }
    preconditions: list[str] = ["gripper_empty"]
    postconditions: list[str] = []
    effects: dict = {"gripper_state": "holding"}
    failure_modes: list[str] = [
        "no_base",
        "no_arm",
        "no_gripper",
        "no_world_model",
        "object_not_found",
        "nav_failed",
        "wait_stable_timeout",
        "ik_unreachable",
        "move_failed",
    ]

    def __init__(self) -> None:
        from vector_os_nano.skills.pick_top_down import PickTopDownSkill

        self._pick = PickTopDownSkill()

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        # --- Guard: hardware preconditions ---
        if context.base is None:
            return SkillResult(
                success=False,
                error_message="No base connected",
                result_data={"diagnosis": "no_base"},
            )
        if context.arm is None:
            return SkillResult(
                success=False,
                error_message="No arm connected",
                result_data={"diagnosis": "no_arm"},
            )
        if context.gripper is None:
            return SkillResult(
                success=False,
                error_message="No gripper connected",
                result_data={"diagnosis": "no_gripper"},
            )
        if context.world_model is None:
            return SkillResult(
                success=False,
                error_message="No world_model available",
                result_data={"diagnosis": "no_world_model"},
            )

        # --- Resolve target via pick's resolver ---
        target = self._pick._resolve_target(params, context.world_model)

        # v2.3: perception-driven auto-detect retry on world_model miss
        if target is None:
            from vector_os_nano.skills.utils import run_autodetect_retry

            if run_autodetect_retry(params, context, log_tag="MOBILE-PICK") > 0:
                target = self._pick._resolve_target(params, context.world_model)

        if target is None:
            query = params.get("object_label") or params.get("object_id") or ""
            # Routing-independent far fetch (D114 follow-on): mobile_pick needs an ALREADY-localized
            # 3D position, but a FAR object can't be 3D-placed by the tracker (no valid depth at
            # range) -> it never enters the world model with a usable position. Rather than fail,
            # DELEGATE to perception_grasp — the find-AND-self-navigate fetch skill (un-gated
            # open-vocab localize in WORLD frame -> drive to a standoff -> face -> grasp). This makes
            # the far fetch independent of WHICH skill the model routed: whichever it picks, the
            # object gets fetched. Honest: perception_grasp grounds ONLY via the real GT weld, so a
            # truly-absent or ungraspable object still fails loud there (no fake success).
            if (
                query
                and getattr(context, "perception", None) is not None
                and context.base is not None
            ):
                from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill
                logger.info(
                    "[MOBILE-PICK] %r not localizable in world model -> delegating to "
                    "perception_grasp (find + self-navigate + grasp)", query,
                )
                return PerceptionGraspSkill().execute({"query": query}, context)
            known_labels = [
                o.label for o in context.world_model.get_objects()
                if o.object_id.startswith("pickable_")
            ]
            return SkillResult(
                success=False,
                error_message=(
                    f"Cannot locate target object (query={query!r}). "
                    f"Known pickable objects: {known_labels}. "
                    f"Retry with one of these labels."
                ),
                result_data={
                    "diagnosis": "object_not_found",
                    "query": query,
                    "known_objects": known_labels,
                },
            )
        obj_id, obj_xyz = target

        # --- Read dog pose ---
        dog_x, dog_y, _ = context.base.get_position()
        dog_yaw: float = context.base.get_heading()

        # --- Config override for clearance ---
        cfg: dict = context.config.get("skills", {}).get("mobile_pick", {})
        clearance: float = float(cfg.get("clearance", _DEFAULT_CLEARANCE))

        # --- Compute approach pose ---
        ax, ay, ayaw = compute_approach_pose(
            obj_xyz, (dog_x, dog_y, dog_yaw), clearance=clearance
        )

        # --- Decide whether navigation is needed ---
        already_reachable: bool = (
            _dist_xy(dog_x, dog_y, ax, ay) < _APPROACH_XY_TOL
            and abs(_ang_diff(dog_yaw, ayaw)) < math.radians(_APPROACH_YAW_DEG)
        )
        skip_nav: bool = bool(params.get("skip_navigate", False))

        if not already_reachable and not skip_nav:
            logger.info("[MOBILE-PICK] navigate_to approach (%.2f, %.2f)", ax, ay)
            ok: bool = context.base.navigate_to(ax, ay, timeout=_NAV_TIMEOUT)
            if not ok:
                return SkillResult(
                    success=False,
                    error_message="Navigation to approach pose failed",
                    result_data={
                        "diagnosis": "nav_failed",
                        "approach": [ax, ay, ayaw],
                    },
                )

        # --- Wait for dog to settle ---
        if not _wait_stable(
            context.base,
            max_speed=_STABLE_MAX_SPEED,
            settle_duration=_STABLE_SETTLE,
            timeout=_STABLE_TIMEOUT,
        ):
            return SkillResult(
                success=False,
                error_message="Dog did not settle before pick",
                result_data={"diagnosis": "wait_stable_timeout"},
            )

        # --- Delegate to PickTopDownSkill ---
        pick_params = {**params, "object_id": obj_id}
        result: SkillResult = self._pick.execute(pick_params, context)

        if result.success:
            nav_dist = round(_dist_xy(dog_x, dog_y, ax, ay), 2)
            mobile_meta: dict = {
                "approach": [round(ax, 2), round(ay, 2), round(ayaw, 3)],
                "nav_distance": nav_dist,
                "skipped_navigate": already_reachable or skip_nav,
            }
            rd = {**result.result_data, "mobile_pick": mobile_meta}
            # --- ran-no-weld diagnosis (backlog #2) --------------------------
            # PickTopDownSkill reports success even when the weld did not form
            # (diagnosis 'possibly_missed') — the dominant far failure is this RAN
            # (success-but-no-ground) mode. Read the GT weld (gripper.is_holding —
            # the oracle the actor cannot author) and stamp the precise 'ran_no_weld'
            # so it is diagnosable. INFORMATIONAL only: it rides result_data ->
            # StepVerdict.diagnosis, never ``verified`` (the spine grades the oracle).
            weld_formed = False
            try:
                weld_formed = bool(context.gripper.is_holding())
            except Exception as exc:  # noqa: BLE001 — a diagnosis read must never crash the pick
                logger.debug("[MOBILE_PICK] is_holding() diagnosis read failed: %s", exc)
            rd["weld_formed"] = weld_formed
            if not weld_formed and rd.get("diagnosis") in (None, "", "ok", "possibly_missed"):
                rd["diagnosis"] = "ran_no_weld"
            result = SkillResult(
                success=result.success,
                error_message=result.error_message,
                result_data=rd,
            )

        return result
