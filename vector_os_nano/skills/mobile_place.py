# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Walk the dog to an approach pose, then delegate to PlaceTopDownSkill.

Phase C mobile variant of the manipulation stack (v2.2 Wave 3, Task T9).
Mirrors MobilePickSkill composition pattern:

  1. Hardware guards (base / arm / gripper).
  2. Resolve target XYZ (explicit or receptacle_id from world_model).
  3. Compute approach pose via compute_approach_pose.
  4. Check already_reachable / skip_navigate flag.
  5. navigate_to approach pose (if needed).
  6. wait_stable so arm IK is computed from a stationary base.
  7. Delegate to PlaceTopDownSkill (force-passing resolved target_xyz).
  8. Enrich result_data with mobile_place metadata.

No ROS2 imports. No perception imports.
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
# Module constants
# ---------------------------------------------------------------------------

_DEFAULT_CLEARANCE: float = 0.90  # m from receptacle to the nav approach. Larger than the ~0.22 m
# reach ON PURPOSE: nav stops OUTSIDE the receptacle's obstacle inflation (a closer approach pose is
# inside it -> navigate_to fails), then the Step-6b jam-approach DOCK closes the remaining gap
# arm-close (D118/D123). A too-small clearance navigates into the inflated obstacle and nav_failed.
_APPROACH_XY_TOL: float = 0.10   # metres — within this → already_reachable
_APPROACH_YAW_DEG: float = 20.0  # degrees — yaw tolerance for already_reachable
_NAV_TIMEOUT: float = 20.0       # seconds for navigate_to
_DROP_XY_TOL: float = 0.30       # m; drop-release only when the EE is within this of the target xy
# (over the receptacle). The flat place receptacle is ~0.36 x 0.80 m, so 0.30 keeps the drop on it.
_STABLE_MAX_SPEED: float = 0.05  # m/s — dog counts as stable below this
_STABLE_SETTLE: float = 1.0      # seconds to remain stable
_STABLE_TIMEOUT: float = 5.0     # maximum seconds to wait for stability
_RECEPTACLE_BODY: str = "place_bin"  # the scene's designated flat place receptacle
_RECEPTACLE_OBJECT_HALF_Z: float = 0.04  # rest centre = receptacle top + object half-height
_RECEPTACLE_SETTLE: float = 2.5  # s — let the dropped object come to REST before returning, so the
# verdict's resting_on_receptacle (which requires AT-REST) sees a settled object, not one mid-fall


# ---------------------------------------------------------------------------
# Inline helpers (mirrored from MobilePickSkill to avoid cross-import)
# ---------------------------------------------------------------------------


def _dist_xy(x1: float, y1: float, x2: float, y2: float) -> float:
    """Euclidean distance in XY plane."""
    dx = x1 - x2
    dy = y1 - y2
    return math.sqrt(dx * dx + dy * dy)


def _ang_diff(a: float, b: float) -> float:
    """Signed angular difference a - b, wrapped to [-pi, pi]."""
    d = a - b
    while d > math.pi:
        d -= 2.0 * math.pi
    while d < -math.pi:
        d += 2.0 * math.pi
    return d


def _wait_stable(
    base: object,
    max_speed: float,
    settle_duration: float,
    timeout: float,
) -> bool:
    """Block until the base reports low speed for settle_duration seconds.

    Returns True if stable within timeout, False on timeout.
    Polls at 10 Hz. Uses time.sleep for test patching compatibility.
    """
    deadline = time.monotonic() + timeout
    stable_since: float | None = None

    while time.monotonic() < deadline:
        pos_a = base.get_position()
        time.sleep(0.1)
        pos_b = base.get_position()
        dx = pos_b[0] - pos_a[0]
        dy = pos_b[1] - pos_a[1]
        speed = math.sqrt(dx * dx + dy * dy) / 0.1
        if speed < max_speed:
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= settle_duration:
                return True
        else:
            stable_since = None

    return False


def _scene_place_geom(base: object):
    """``(cx, cy, rest_z, (x_min, y_min, x_max, y_max))`` of the scene's flat place receptacle
    from the LIVE MJCF body, or ``None``. Lets a bare-cli model route ``mobile_place`` with NO
    coordinates: the place receptacle is static furniture, invisible to detect/describe (D133),
    so the model can't author a target — the skill self-resolves the scene receptacle from the
    same live geometry the verify oracle reads (config-from-scene, Rule 11). The xy REGION is
    returned too, so the safe-drop guard can accept any drop ON the (large, anisotropic)
    receptacle, not just within a fixed radius of its centre. Fails safe to ``None``.
    """
    mjw = getattr(base, "_mj", None)
    model = getattr(mjw, "model", None)
    if model is None:
        return None
    try:
        import mujoco

        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, _RECEPTACLE_BODY)
        if bid < 0 or int(model.body_geomnum[bid]) < 1:
            return None
        gid = int(model.body_geomadr[bid])
        bx, by, bz = (float(v) for v in model.body_pos[bid])
        gx, gy, gz = (float(v) for v in model.geom_pos[gid])
        sx, sy, sz = (float(v) for v in model.geom_size[gid])
        cx, cy = bx + gx, by + gy
        rest_z = (bz + gz + sz) + _RECEPTACLE_OBJECT_HALF_Z
        region = (cx - sx, cy - sy, cx + sx, cy + sy)
        return (cx, cy, rest_z, region)
    except Exception as exc:  # noqa: BLE001 — no receptacle resolvable is fine
        logger.debug("[MOBILE-PLACE] scene receptacle resolve failed: %s", exc)
        return None


def _scene_place_target(base: object) -> tuple[float, float, float] | None:
    """``(cx, cy, rest_z)`` of the scene place receptacle, or ``None`` (see _scene_place_geom)."""
    geom = _scene_place_geom(base)
    return geom[:3] if geom is not None else None


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


@skill(
    aliases=[
        "去放", "送到", "搬到", "拿去放", "放到", "放在", "放下", "放好",
        "放到架子上", "放到台子上", "放到盒子里",
        "deliver", "put at", "carry to", "put on", "place on", "place it on",
        "put it on the shelf", "set it down",
    ],
    direct=False,
)
class MobilePlaceSkill:
    """PLACE the currently-held object ON the scene's place receptacle (shelf / table /
    box). Walks the dog to it and releases with a drop. Use this for any "put / place X
    on the shelf/table" command AFTER the object is grasped.
    """

    name: str = "mobile_place"
    description: str = (
        "PLACE the held object onto the scene's place receptacle (a shelf/table/box). "
        "Use for 'put/place X on the shelf/table' (放到架子上/台子上) once the object is "
        "in the gripper. target_xyz and receptacle_id are OPTIONAL — with neither, the "
        "skill auto-resolves the scene's place receptacle, so just call mobile_place with "
        "no arguments to place the held object on it. Walks there and drops."
    )
    parameters: dict = {
        "target_xyz": {
            "type": "list",
            "required": False,
            "description": "Explicit world XYZ (3 floats) to drop at.",
            "source": "explicit",
        },
        "receptacle_id": {
            "type": "string",
            "required": False,
            "description": "Receptacle object id in world model.",
            "source": "world_model.objects.object_id",
        },
        "drop_height": {
            "type": "number",
            "required": False,
            "default": 0.05,
            "description": "Z offset above target to release (m).",
            "source": "static",
        },
        "skip_navigate": {
            "type": "boolean",
            "required": False,
            "default": False,
            "description": "Skip the navigation step (debug use).",
            "source": "static",
        },
    }
    preconditions: list[str] = ["gripper_holding_any"]
    postconditions: list[str] = []
    effects: dict = {"gripper_state": "open", "held_object": None}
    failure_modes: list[str] = [
        "no_base", "no_arm", "no_gripper",
        "receptacle_not_found", "invalid_target_xyz", "missing_target",
        "nav_failed", "wait_stable_timeout",
        "ik_unreachable", "move_failed", "dock_off_receptacle", "drop_release",
    ]
    # The bare-cli verdict grades a PLACE by this predicate (D106/D116 moat-proven
    # oracle, wired into the verify namespace in robot.py from the live receptacle
    # geometry, D130). Zero-arg: the oracle is pre-bound to the scene's place
    # receptacle, so the model authors verify="resting_on_receptacle() >= 1" with no
    # coordinates to guess (consumed by vocab_from_registry via schema["verify_hint"]).
    verify_hint: str = "resting_on_receptacle() >= 1"

    def __init__(self) -> None:
        from vector_os_nano.skills.place_top_down import PlaceTopDownSkill
        self._place = PlaceTopDownSkill()

    # ------------------------------------------------------------------

    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        base = context.base
        arm = context.arm
        gripper = context.gripper
        wm = context.world_model
        cfg = context.config.get("skills", {}).get("mobile_place", {})

        # Step 1 — Hardware guards
        if base is None:
            return SkillResult(
                success=False,
                error_message="No base connected",
                result_data={"diagnosis": "no_base"},
            )
        if arm is None:
            return SkillResult(
                success=False,
                error_message="No arm connected",
                result_data={"diagnosis": "no_arm"},
            )
        if gripper is None:
            return SkillResult(
                success=False,
                error_message="No gripper connected",
                result_data={"diagnosis": "no_gripper"},
            )

        # Step 2 — Resolve target XYZ (explicit / world-model receptacle / scene receptacle)
        resolved = self._resolve_target(params, wm, base)
        if isinstance(resolved, SkillResult):
            return resolved
        tx, ty, tz = resolved

        # Step 3 — Read dog pose, compute approach pose
        dog_pos = base.get_position()
        dog_heading = base.get_heading()
        dog_pose = (dog_pos[0], dog_pos[1], dog_heading)

        clearance = float(cfg.get("clearance", _DEFAULT_CLEARANCE))
        # For the SCENE place receptacle, approach from -X facing +X — the controlled dock
        # that lands the EE over the receptacle CENTRE (the 6/6-verified approach, D123/D135),
        # instead of compute_approach_pose's dog-side diagonal which lands the EE at the near
        # -Y edge so ~half the drops bounce off (D135). The -X side is the open/approachable
        # face of the scene receptacle; this is what makes the place RELIABLE over N.
        scene_geom = _scene_place_geom(base)
        is_scene_receptacle = (
            scene_geom is not None
            and abs(tx - scene_geom[0]) < 0.02
            and abs(ty - scene_geom[1]) < 0.02
        )
        if is_scene_receptacle:
            approach_x, approach_y, approach_yaw = (tx - clearance, ty, 0.0)
            logger.info(
                "[MOBILE-PLACE] scene receptacle: controlled -X approach at (%.2f,%.2f) facing +X",
                approach_x, approach_y,
            )
        else:
            approach_x, approach_y, approach_yaw = compute_approach_pose(
                (tx, ty, tz), dog_pose, clearance=clearance
            )
        nav_distance = _dist_xy(dog_pos[0], dog_pos[1], approach_x, approach_y)

        # Step 4 — Check already_reachable or skip_navigate
        xy_close = nav_distance < _APPROACH_XY_TOL
        yaw_close = abs(_ang_diff(dog_heading, approach_yaw)) < math.radians(
            _APPROACH_YAW_DEG
        )
        already_reachable = xy_close and yaw_close
        skip_navigate = bool(params.get("skip_navigate", False))

        logger.info(
            "[MOBILE-PLACE] target=(%.3f, %.3f, %.3f) approach=(%.3f, %.3f) "
            "dist=%.3f already_reachable=%s skip=%s",
            tx, ty, tz, approach_x, approach_y,
            nav_distance, already_reachable, skip_navigate,
        )

        # Step 5 — Navigate (if needed)
        if not already_reachable and not skip_navigate:
            # For the scene receptacle's -X approach, navigate in TWO legs (an L-path):
            # first -X to the approach x at the dog's CURRENT y (a clear corridor -X of the
            # receptacle), THEN +Y to the approach point. A single diagonal leg cuts the
            # corner and STALLS against the receptacle/furniture inflation for some grasp
            # poses (blue stalled 0.37 m short, D137) — the L-path keeps the dog -X of the
            # obstruction the whole way, making the controlled approach colour-agnostic.
            if is_scene_receptacle and abs(dog_pos[1] - approach_y) > _APPROACH_XY_TOL:
                logger.info(
                    "[MOBILE-PLACE] L-nav leg 1: -X corridor to (%.2f, %.2f)",
                    approach_x, dog_pos[1],
                )
                base.navigate_to(approach_x, dog_pos[1], timeout=_NAV_TIMEOUT)
            logger.info(
                "[MOBILE-PLACE] navigating to approach (%.3f, %.3f) timeout=%.0fs",
                approach_x, approach_y, _NAV_TIMEOUT,
            )
            nav_ok = base.navigate_to(approach_x, approach_y, timeout=_NAV_TIMEOUT)
            if not nav_ok:
                return SkillResult(
                    success=False,
                    error_message="Navigation to approach pose failed",
                    result_data={"diagnosis": "nav_failed"},
                )

        # Step 6 — Wait for stable
        if not _wait_stable(base, _STABLE_MAX_SPEED, _STABLE_SETTLE, _STABLE_TIMEOUT):
            return SkillResult(
                success=False,
                error_message="Base did not stabilise after navigation",
                result_data={"diagnosis": "wait_stable_timeout"},
            )

        # Step 6b — DOCK ARM-CLOSE (D118): navigate_to leaves the dog ~0.5 m short (the
        # compute_approach_pose clearance + the in-process nav's terminal error), beyond the
        # Piper's ~0.22 m top-down reach -> the release IK is unreachable. Reuse perception_grasp's
        # PROVEN jam-approach (the same dock that makes the GRASP reachable): face the target ->
        # forward-jam to the closest stall standoff -> tight final face. World-agnostic (duck-typed
        # walk/get_position/get_heading); a benign no-op when the base lacks the surface or is
        # already docked. Only then is the top-down release within reach.
        if not skip_navigate:
            try:
                from vector_os_nano.skills.perception_grasp import (
                    _approach_object,
                    _face_object,
                    _grasp_ready_repose,
                )
                _grasp_ready_repose(base, (tx, ty))
                _approach_object(base, (tx, ty))
                _face_object(base, (tx, ty))
            except Exception as exc:  # noqa: BLE001 — dock is best-effort; the place IK still runs
                logger.warning("[MOBILE-PLACE] dock approach raised (continuing): %s", exc)

        # Step 7 — Delegate to PlaceTopDownSkill with resolved target_xyz
        place_params = {**params, "target_xyz": [tx, ty, tz]}
        logger.info("[MOBILE-PLACE] delegating to PlaceTopDownSkill target=%s", [tx, ty, tz])
        place_result = self._place.execute(place_params, context)

        # Step 7b — DROP-RELEASE fallback (D123): the precise top-down place IK is UNREACHABLE at a
        # free-standing receptacle (the arm reaches it only at carry-z, not the low place pose —
        # unlike the tuned pick-table grasp). But after the Step-6b jam-dock the held object is
        # already OVER the receptacle, so simply RELEASE there: open the gripper and let the object
        # DROP onto the (flat) receptacle. This is the proven place primitive (skill-direct 6/6 onto
        # a flat receptacle, D123). ONLY on the ik_unreachable failure after a real dock; a
        # successful precise place is unchanged, and a genuinely-undocked failure is NOT masked.
        if (
            not place_result.success
            and (place_result.result_data or {}).get("diagnosis") == "ik_unreachable"
            and not skip_navigate
        ):
            # SAFE-DROP guard (D124): the jam-dock occasionally lands the arm OFF the receptacle
            # (lateral variance); dropping there scatters the object off-target, yet gripper.open
            # always "succeeds" -> a FALSE success report the bare-cli model would trust. So drop
            # ONLY when the end-effector (where the held object hangs) is actually OVER the
            # receptacle (within _DROP_XY_TOL of the target xy). Else DON'T drop -> honest failure
            # (dock_off_receptacle), never a success-claim for a missed place. Reads the arm's own
            # fk (the predicate the verify oracle also uses), not a self-report.
            ee_xy = None
            try:
                ee_pos, _rot = arm.fk(arm.get_joint_positions())
                ee_xy = (float(ee_pos[0]), float(ee_pos[1]))
            except Exception as exc:  # noqa: BLE001 — no fk -> cannot confirm over-receptacle
                logger.debug("[MOBILE-PLACE] fk for safe-drop failed: %s", exc)
            # Prefer the receptacle REGION (anisotropic, large) — drop iff the EE is actually ON
            # the receptacle, not merely within a fixed radius of its centre. The jam-dock lands
            # the EE near the receptacle's NEAR edge (in-region, but >_DROP_XY_TOL from centre on a
            # 0.36x0.80 m top), so a centre-radius guard refuses valid in-region drops (D133).
            geom = _scene_place_geom(base)
            region = geom[3] if geom is not None else None
            _m = 0.03  # small margin (m) so an EE right at the rim still counts as over
            if ee_xy is not None and region is not None:
                over_receptacle = (
                    region[0] - _m <= ee_xy[0] <= region[2] + _m
                    and region[1] - _m <= ee_xy[1] <= region[3] + _m
                )
            else:
                over_receptacle = (
                    ee_xy is not None and _dist_xy(ee_xy[0], ee_xy[1], tx, ty) <= _DROP_XY_TOL
                )
            if over_receptacle:
                logger.info(
                    "[MOBILE-PLACE] EE over receptacle (%.2f,%.2f ~ %.2f,%.2f) -> DROP-RELEASE",
                    ee_xy[0], ee_xy[1], tx, ty,
                )
                try:
                    # GENTLE partial descent before release: the FULL top-down place IK is
                    # unreachable at the receptacle, but a HIGHER intermediate EE pose often IS —
                    # lower the EE as far as it reaches to cut the ~0.27 m carry->top fall that
                    # bounces the wider can off the receptacle (D138). Best-effort; release from
                    # wherever the descent stops (the dock pose if none reaches).
                    try:
                        for _z in (0.48, 0.44, 0.40, 0.37):
                            _q = arm.ik_top_down((tx, ty, _z))
                            if _q is not None:
                                arm.move_joints(_q, duration=1.0)
                                logger.info(
                                    "[MOBILE-PLACE] gentle descent EE->z=%.2f before release", _z
                                )
                                break
                    except Exception as _exc:  # noqa: BLE001 — descent is best-effort
                        logger.debug("[MOBILE-PLACE] gentle descent skipped: %s", _exc)
                    gripper.open()
                    # Let the dropped object SETTLE before returning: the verdict checks
                    # resting_on_receptacle right after this step, and that oracle requires the
                    # object to be AT REST. Without the wait a just-dropped object is still
                    # falling/bouncing -> resting_on_receptacle reads 0 -> a GROUNDED place is
                    # graded RAN (verified in-cli: drop_release but verify_result false, D133).
                    time.sleep(_RECEPTACLE_SETTLE)
                    place_result = SkillResult(
                        success=True,
                        result_data={"diagnosis": "drop_release", "drop_at": [tx, ty, tz]},
                    )
                except Exception as exc:  # noqa: BLE001 — release is best-effort
                    logger.warning("[MOBILE-PLACE] drop-release gripper.open raised: %s", exc)
            else:
                logger.info(
                    "[MOBILE-PLACE] dock left EE OFF the receptacle (ee=%s, target=%.2f,%.2f) "
                    "-> NOT dropping (honest dock_off_receptacle)", ee_xy, tx, ty,
                )
                place_result = SkillResult(
                    success=False,
                    error_message="Jam-dock did not put the arm over the receptacle",
                    result_data={"diagnosis": "dock_off_receptacle", "ee_xy": list(ee_xy or ())},
                )

        # Step 8 — Return (propagate place failure or enrich success)
        mobile_meta = {
            "approach": [approach_x, approach_y, approach_yaw],
            "nav_distance": nav_distance,
            "skipped_navigate": already_reachable or skip_navigate,
        }
        if not place_result.success:
            # Propagate diagnosis from place; add mobile_place meta
            merged = {**place_result.result_data, "mobile_place": mobile_meta}
            return SkillResult(
                success=False,
                error_message=place_result.error_message,
                result_data=merged,
            )

        merged = {**place_result.result_data, "mobile_place": mobile_meta}
        return SkillResult(success=True, result_data=merged)

    # ------------------------------------------------------------------
    # Target resolution
    # ------------------------------------------------------------------

    def _resolve_target(
        self,
        params: dict,
        wm: object,
        base: object = None,
    ) -> tuple[float, float, float] | SkillResult:
        """Return (tx, ty, tz) or a failure SkillResult.

        Priority:
        1. target_xyz — explicit 3-float list.
        2. receptacle_id — ID in world model.
        3. the SCENE's place receptacle, self-resolved from the live geometry (D133)
           — so a bare-cli model routing mobile_place with no coords still places on it.
        4. Neither → missing_target.
        """
        if "target_xyz" in params:
            raw = params["target_xyz"]
            try:
                xyz = tuple(float(v) for v in raw)
            except (TypeError, ValueError):
                xyz = ()
            if len(xyz) != 3 or not all(math.isfinite(v) for v in xyz):
                return SkillResult(
                    success=False,
                    error_message=(
                        f"target_xyz must be 3 finite floats; got {raw!r}"
                    ),
                    result_data={"diagnosis": "invalid_target_xyz", "target_xyz": list(raw) if isinstance(raw, (list, tuple)) else raw},
                )
            return xyz  # type: ignore[return-value]

        if "receptacle_id" in params:
            rid: str = params["receptacle_id"]
            obj = wm.get_object(rid) if wm is not None else None
            if obj is None:
                return SkillResult(
                    success=False,
                    error_message=f"Receptacle {rid!r} not found in world model",
                    result_data={"diagnosis": "receptacle_not_found", "receptacle_id": rid},
                )
            return (float(obj.x), float(obj.y), float(obj.z))

        # 3. Self-resolve the scene's designated place receptacle (D133): the receptacle
        # is static furniture invisible to the model's perception, so a bare-cli place
        # command ("放到架子上") arrives with no coords — read the place_bin from the live
        # geometry (the same source the verify oracle uses) and place there.
        scene = _scene_place_target(base)
        if scene is not None:
            logger.info(
                "[MOBILE-PLACE] no target given -> scene place receptacle at %s", scene
            )
            return scene

        return SkillResult(
            success=False,
            error_message=(
                "Neither target_xyz nor receptacle_id provided and no scene place "
                "receptacle resolvable; cannot determine place location"
            ),
            result_data={"diagnosis": "missing_target"},
        )
