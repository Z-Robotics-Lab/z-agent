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

from zeno.core.skill import SkillContext, skill
from zeno.core.types import SkillResult
from zeno.skills.utils.approach_pose import compute_approach_pose

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
_NAV_RETRIES: int = 1            # extra approach-nav attempts on a transient walk/timeout miss.
# navigate_to fast-fails (planner=None, no walk) on a GENUINELY unreachable target, so a retry is
# ~free there and honest failure is preserved (nav_failed after all attempts); it only recovers the
# transient timeout/walk-stall flake that made mobile_place return False, which the brain then
# "recovered" by improvising an UNREACHABLE navigate(10.8,3.0) -> R247/E56 refuted the courtyard
# PLACE composite on exactly that surfaced flake even though the physical place succeeded.
_DROP_XY_TOL: float = 0.30       # m; drop-release only when the EE is within this of the target xy
# (over the receptacle). The flat place receptacle is ~0.36 x 0.80 m, so 0.30 keeps the drop on it.
_STABLE_MAX_SPEED: float = 0.05  # m/s — dog counts as stable below this
_STABLE_SETTLE: float = 1.0      # seconds to remain stable
_STABLE_TIMEOUT: float = 5.0     # maximum seconds to wait for stability
_RECEPTACLE_BODY: str = "place_bin"  # the scene's designated flat place receptacle
_RECEPTACLE_OBJECT_HALF_Z: float = 0.04  # rest centre = receptacle top + object half-height
# Post-drop settle: the dropped object is waited to REST via _wait_object_at_rest (GT-polled, see
# below), NOT a fixed sleep. (R12's fixed 2.5->4.5 s bump was refuted D158; D159 replaced the fixed
# wait with the at-rest poll after sim-isolating a genuine placement graded RAN purely on timing.)


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


def _navigate_to_approach(
    base: object,
    approach_x: float,
    approach_y: float,
    is_scene_receptacle: bool,
) -> bool:
    """One full approach-nav attempt; returns the main navigate_to result.

    Re-reads the dog pose so the L-nav leg-1 corridor uses the CURRENT y — a retry
    after a partial walk starts from where the dog actually stalled, not the stale
    pre-attempt pose.
    """
    dog_pos = base.get_position()
    # For the scene receptacle's -X approach, navigate in TWO legs (an L-path): first -X to the
    # approach x at the dog's CURRENT y (a clear corridor -X of the receptacle), THEN +Y to the
    # approach point. A single diagonal leg cuts the corner and STALLS against the receptacle/
    # furniture inflation for some grasp poses (blue stalled 0.37 m short, D137) — the L-path keeps
    # the dog -X of the obstruction the whole way, making the controlled approach colour-agnostic.
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
    return bool(base.navigate_to(approach_x, approach_y, timeout=_NAV_TIMEOUT))


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


_AT_REST_SPEED: float = 0.05  # m/s — mirrors arm_sim_oracle._AT_REST_SPEED (the at-rest gate the
# verify oracle uses). The post-drop settle waits for THIS condition (read from GT), not a fixed time.
_SETTLE_POLL_DT: float = 0.2  # s between at-rest polls
_SETTLE_CAP: float = 12.0     # s — hard cap so a perpetually-rolling/lost object can't hang the skill.
# Bumped 5->12 (R15/D161): after the R14 central-drop killed roll-off (D160), the residual RAN is 100%
# SETTLING — a round bottle dropped from carry-z bounces/rolls on the flat bin top and is still moving
# (speed 0.075-0.16 > the 0.05 at-rest gate) at the 5s cap. The restored rim walls CONTAIN it, so it
# reaches rest given time; 12s lets the contained bounce die out before the verdict. Still bounded.


def _wait_object_at_rest(arm: object, target_xy: tuple[float, float]) -> bool:
    """Block until the dropped object NEAREST ``target_xy`` reports a finite speed below
    ``_AT_REST_SPEED``, or ``_SETTLE_CAP`` elapses. Returns True iff it reached rest.

    Replaces the old fixed ``time.sleep(_RECEPTACLE_SETTLE)``: the verdict's
    ``resting_on_receptacle`` requires the object to be AT REST, and a freshly-dropped object is
    still moving for a variable time (sim-verified: a genuine in-region placement was graded RAN
    purely because it was still rolling at the fixed 2.5 s mark, D159). Polling the SAME GT at-rest
    condition the oracle checks converts those genuine placements without blindly inflating EVERY
    place (R12's fixed 4.5 s bump, refuted D158). Honest by construction: an object that rolls OUT
    of the receptacle never becomes ``resting`` no matter how long we wait, so this only ever lets a
    correctly-placed object settle — it cannot manufacture a success. Reads GT velocity; never
    raises into the place path (fails to a short fixed wait if velocities are unavailable).
    """
    deadline = time.monotonic() + _SETTLE_CAP
    get_vel = getattr(arm, "get_object_velocities", None)
    get_pos = getattr(arm, "get_object_positions", None)
    if get_vel is None or get_pos is None:
        time.sleep(min(_SETTLE_CAP, 2.5))  # no GT velocity -> fall back to a bounded fixed wait
        return False
    # require SUSTAINED rest (two consecutive sub-threshold reads) — a dropped object bounces, so a
    # single sub-threshold reading can be a transient lull mid-bounce; returning on it leaves the
    # object still moving at the verdict (sim-seen: resting=0 at verdict then 1 by +2 s, D159).
    consecutive = 0
    while time.monotonic() < deadline:
        try:
            positions = get_pos()
            velocities = get_vel()
        except Exception:  # noqa: BLE001 — GT read failed this tick; retry until the cap
            time.sleep(_SETTLE_POLL_DT)
            continue
        # the object closest to the drop xy is the one we just released
        name = None
        best = float("inf")
        for nm, p in (positions or {}).items():
            try:
                d = _dist_xy(float(p[0]), float(p[1]), target_xy[0], target_xy[1])
            except (TypeError, ValueError, IndexError):
                continue
            if d < best:
                best, name = d, nm
        v = (velocities or {}).get(name) if name is not None else None
        if v is not None:
            try:
                speed = math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)
            except (TypeError, ValueError, IndexError):
                speed = float("inf")
            if math.isfinite(speed) and speed < _AT_REST_SPEED:
                consecutive += 1
                if consecutive >= 2:
                    return True
                time.sleep(_SETTLE_POLL_DT)
                continue
        consecutive = 0
        time.sleep(_SETTLE_POLL_DT)
    return False


_CENTER_XY_TOL: float = 0.03  # m — EE already this close to the bin centre xy → no reposition


def _center_over_receptacle(arm: object, geom) -> None:
    """Before the drop-release, nudge the held object HORIZONTALLY toward the receptacle
    CENTRE at the current carry height, so it drops onto the MIDDLE of the narrow bin instead
    of the near third (D159 root cause: the jam-dock lands the EE in the near third — EE
    x~10.80 on a bin whose top is x∈[10.77,11.13] — so a dropped round bottle rolls off the
    near edge). Lands central → maximal margin to every edge + (with the restored rim walls)
    can't escape.

    Carry-z ONLY — never descends (a descent could drive the gripper into the rim walls and is
    why the precise low place IK is unreachable here, D123). Tries top-down IK first (keeps the
    held object upright; the weld is safe), then position-only IK as a fallback. Best-effort and
    HONEST by construction: it only REPOSITIONS the arm; the existing safe-drop guard then
    RE-READS the EE via fk and still refuses to drop if it is not over the receptacle, so this
    can never manufacture a placement — at worst it is a no-op and the old near-third drop stands.
    Never raises into the place path.
    """
    if geom is None:
        return
    try:
        cx, cy = float(geom[0]), float(geom[1])
        cur = arm.get_joint_positions()
        ee_pos, _rot = arm.fk(cur)
        ex, ey, ez = float(ee_pos[0]), float(ee_pos[1]), float(ee_pos[2])
    except Exception as exc:  # noqa: BLE001 — can't read the arm → leave the dock pose as-is
        logger.debug("[MOBILE-PLACE] center-over-receptacle read failed: %s", exc)
        return
    if _dist_xy(ex, ey, cx, cy) <= _CENTER_XY_TOL:
        return  # already central
    target = (cx, cy, ez)  # same carry height, centred xy
    try:
        q = arm.ik_top_down(target, current_joints=cur)
        if q is None and hasattr(arm, "ik"):
            q = arm.ik(target, current_joints=cur)
        if q is not None:
            arm.move_joints(q, duration=1.5)
            logger.info(
                "[MOBILE-PLACE] centred EE over receptacle: (%.2f,%.2f)->(%.2f,%.2f)",
                ex, ey, cx, cy,
            )
        else:
            logger.info(
                "[MOBILE-PLACE] center-over-receptacle IK unreachable; keeping dock pose"
            )
    except Exception as exc:  # noqa: BLE001 — reposition is best-effort
        logger.debug("[MOBILE-PLACE] center-over-receptacle move raised: %s", exc)


def _dump_place_diag(base: object, arm: object, target: tuple, geom) -> None:
    """Diagnostic-only: append one JSON line of post-dock geometry to ``$VECTOR_PLACE_DIAG``.

    No-op unless that env var names a writable path. Records the dog's final base pose, the
    end-effector xy (where the held object hangs), and the receptacle centre/region — so a place
    reliability round can size the nav/dock miss (dog-to-receptacle and EE-to-receptacle) without a
    heavy ``--verbose`` run. Reads the same fk/region the verify oracle uses; never raises into the
    place path and never affects the verdict.
    """
    import os

    path = os.environ.get("VECTOR_PLACE_DIAG")
    if not path:
        return
    try:
        tx, ty, _tz = target
        dog = base.get_position()
        rec = {
            "tgt": [round(float(tx), 3), round(float(ty), 3)],
            "dog": [round(float(dog[0]), 3), round(float(dog[1]), 3)],
            "dog_d2tgt": round(_dist_xy(float(dog[0]), float(dog[1]), float(tx), float(ty)), 3),
        }
        try:
            ee_pos, _rot = arm.fk(arm.get_joint_positions())
            ex, ey = float(ee_pos[0]), float(ee_pos[1])
            rec["ee"] = [round(ex, 3), round(ey, 3)]
            rec["ee_d2tgt"] = round(_dist_xy(ex, ey, float(tx), float(ty)), 3)
            if geom is not None:
                rx0, ry0, rx1, ry1 = geom[3]
                rec["ee_in_region"] = bool(rx0 <= ex <= rx1 and ry0 <= ey <= ry1)
        except Exception:  # noqa: BLE001
            rec["ee"] = None
        with open(path, "a") as f:
            f.write(__import__("json").dumps(rec) + "\n")
    except Exception:  # noqa: BLE001 — diagnostics must never break the place path
        pass


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
        "object_lost_in_transport",
    ]
    # The bare-cli verdict grades a PLACE by this predicate (D106/D116 moat-proven
    # oracle, wired into the verify namespace in robot.py from the live receptacle
    # geometry, D130). Zero-arg: the oracle is pre-bound to the scene's place
    # receptacle, so the model authors verify="resting_on_receptacle() >= 1" with no
    # coordinates to guess (consumed by vocab_from_registry via schema["verify_hint"]).
    verify_hint: str = "resting_on_receptacle() >= 1"

    def __init__(self) -> None:
        from zeno.skills.place_top_down import PlaceTopDownSkill
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

        # Step 5 — Navigate (if needed), retrying a transient miss internally so it never
        # surfaces to the brain as a False (R247/E56: the brain "recovers" a surfaced nav-False by
        # improvising an UNREACHABLE navigate to the pick location, ungrounding the composite even
        # though the physical place succeeds). A genuinely unreachable approach fast-fails on every
        # attempt (planner=None, no walk) -> nav_failed is still returned honestly.
        if not already_reachable and not skip_navigate:
            nav_ok = False
            for attempt in range(_NAV_RETRIES + 1):
                nav_ok = _navigate_to_approach(
                    base, approach_x, approach_y, is_scene_receptacle
                )
                if nav_ok:
                    break
                if attempt < _NAV_RETRIES:
                    logger.warning(
                        "[MOBILE-PLACE] approach nav miss (attempt %d/%d) — retrying "
                        "internally so a transient walk/timeout flake stays inside the skill",
                        attempt + 1, _NAV_RETRIES + 1,
                    )
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
                from zeno.skills.perception_grasp import (
                    _approach_object,
                    _face_object,
                    _grasp_ready_repose,
                )
                _grasp_ready_repose(base, (tx, ty))
                _approach_object(base, (tx, ty))
                _face_object(base, (tx, ty))
            except Exception as exc:  # noqa: BLE001 — dock is best-effort; the place IK still runs
                logger.warning("[MOBILE-PLACE] dock approach raised (continuing): %s", exc)

        # Diagnostic-only (env-gated, no behaviour change): record where the dog + EE ended up
        # relative to the receptacle right after the dock, so a place reliability round can size
        # the nav/dock miss magnitude without a heavy --verbose run. Reads the same fk/region the
        # verify oracle uses. Writes one JSON line to $VECTOR_PLACE_DIAG. Never affects the verdict.
        _dump_place_diag(base, arm, (tx, ty, tz), _scene_place_geom(base))

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
            # CENTRAL-DROP (D160): nudge the held object to the bin CENTRE before releasing, so it
            # drops onto the middle of the narrow top (not the near third the jam-dock leaves it at)
            # and can't roll off an edge. Best-effort, carry-z only; the safe-drop guard below
            # re-reads the resulting EE, so this can only improve the landing, never fake a place.
            _center_over_receptacle(arm, _scene_place_geom(base))

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
            # HONESTY GATE (D159): the held object can be LOST IN TRANSPORT — the grasp weld breaks
            # while the dog walks to the bin, and the bottle ends on the floor short of the
            # receptacle (sim-verified: bottle at y=3.74,z=0.03 while the EE docked clean over the
            # bin). Opening an empty gripper over the bin still "succeeds", so a transport-loss was
            # being reported as a drop_release SUCCESS the bare-cli model would trust. Read the GT
            # weld (gripper.is_holding — READ, never AUTHORED, the same oracle the grasp-retry gates
            # on); if nothing is held at drop time, do NOT fake a place — report honestly so the
            # diagnosis points at the real failure (transport), not a phantom drop.
            holding_now = True
            try:
                holding_now = bool(gripper.is_holding())
            except Exception as exc:  # noqa: BLE001 — cannot read weld -> assume held, drop as before
                logger.debug("[MOBILE-PLACE] is_holding read failed pre-drop: %s", exc)
            if over_receptacle and not holding_now:
                logger.info(
                    "[MOBILE-PLACE] EE over receptacle but NOTHING HELD (lost in transport) "
                    "-> honest fail, no phantom drop"
                )
                place_result = SkillResult(
                    success=False,
                    error_message="Held object lost in transport before the place drop",
                    result_data={"diagnosis": "object_lost_in_transport"},
                )
            elif over_receptacle:
                logger.info(
                    "[MOBILE-PLACE] EE over receptacle (%.2f,%.2f ~ %.2f,%.2f) -> DROP-RELEASE",
                    ee_xy[0], ee_xy[1], tx, ty,
                )
                try:
                    gripper.open()
                    # Wait for the dropped object to come to REST before returning (the verdict
                    # checks resting_on_receptacle right after, and that oracle requires AT-REST).
                    # Poll the SAME GT at-rest condition instead of a fixed sleep — converts a
                    # genuine in-region placement that was still rolling at a fixed mark, without
                    # inflating every place (D158/D159).
                    _wait_object_at_rest(arm, (tx, ty))
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
            if obj is not None:
                return (float(obj.x), float(obj.y), float(obj.z))
            # The model often authors mobile_place(receptacle_id='shelf'/'table') for a
            # receptacle that is NOT in the world model (it is static furniture, invisible
            # to perception — D133). Rather than fail receptacle_not_found, FALL THROUGH to
            # the scene's designated place receptacle below, so the bare-cli place still
            # grounds whether the model passes no target, a bad receptacle_id, or coords.
            logger.info(
                "[MOBILE-PLACE] receptacle_id %r not in world model -> scene receptacle", rid
            )

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
