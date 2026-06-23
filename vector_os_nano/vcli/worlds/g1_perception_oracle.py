# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""g1 perception verify oracle — the HONEST GROUNDED for a camera-only embodiment.

R7. g1 (humanoid, head camera, NO arm) has no weld-causation path, so the only
honest GROUNDED for it is a GT-BACKED PERCEPTION MATCH: the learned detector
localizes an object on g1's camera (its box = the CLAIM), and the verify oracle
judges that claim against INDEPENDENT SIM ground truth the detector cannot author.

This is NOT the R4 self-read that minted a false green (D61). R4 bound
``detect_objects()`` over the detector's OWN stashed boxes and graded
``len(detect_objects()) > 0`` — the actor certifying itself (a tautology). Here:

  - the TRUTH is the SIM body xpos (``base.get_object_positions()`` — physics
    ground truth, never passed to the detector);
  - the CLAIM is the detector's box, obtained by running grounding-dino on the
    live RGB frame ONLY (the firewall: ``G1HeadPerception`` exposes only
    ``get_color_frame`` / ``get_camera_pose`` to the detector, never GT);
  - the oracle PROJECTS the GT world position onto g1's camera image plane (the
    exact camera pose + intrinsics, the same projection math the grasp uses) and
    returns True IFF a detected box CENTER lands within ``tol`` pixels of the GT's
    projected pixel.

So the oracle returns "the detector's localization MATCHES where the GT object
actually is" — not "the detector found something". A WRONG detection (a box on a
wall, or the wrong object, or g1 facing away so the object is out of view) lands
far from the GT projection → False → the step grades RAN/FAILED, never GROUNDED.
GROUNDED must be EARNED by a spatially-correct localization (the refutation proof).

Moat placement (kernel rule 2): this lives WORLD-side (``vcli.worlds``), bound into
the verify namespace by ``RobotWorld.build_verify_namespace``. The frozen
``vcli/cognitive/`` spine is BYTE-UNCHANGED — the oracle reaches GROUNDED purely by
being a STATE oracle the model compares against a constant
(``detection_matches_gt('red') == True``), which the existing
``evidence_classifier`` already grades GROUNDED. No spine list edit, no new
``_PREDICATE_ORACLES`` entry.

Fail-safe contract (same as the arm/go2 oracles): a missing base / perception /
detector, an un-imageable GT, or any read failure → the oracle returns ``False``
(never raises into the GoalVerifier sandbox, never a spurious True). Stricter-only.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Default pixel tolerance for the box-center↔GT-projection match. The g1 head
# render is 640×480; a freejoint cylinder (r≈3 cm) at ~0.9 m subtends ~40-60 px,
# so a correct box center sits within a few tens of px of the GT projection while a
# box on a wall / wrong object is hundreds of px away. 60 px is generous enough to
# absorb projection + box-center jitter yet far tighter than a wrong-object miss.
_DEFAULT_TOL_PX: float = 60.0

# Render resolution for the oracle's own detector run — matches G1HeadPerception's
# default so the box coordinates and the projection share the SAME image plane.
_RENDER_W: int = 640
_RENDER_H: int = 480

# g1 head camera vertical FOV (the compiled scene camera carries no fovy attribute,
# so MuJoCo's default 45° vfov applies). Single point of truth for the intrinsics.
_G1_CAM_VFOV_DEG: float = 45.0

# Colour token → the dominant RGBA channel that identifies a coloured object, used
# only as a NAME-FALLBACK resolver (the GT body names already encode colour:
# pickable_can_red / pickable_bottle_green / pickable_bottle_blue).
_COLOUR_TOKENS: tuple[str, ...] = ("red", "green", "blue", "yellow", "orange")
_COLOUR_ZH: dict[str, str] = {
    "红": "red", "红色": "red",
    "绿": "green", "绿色": "green",
    "蓝": "blue", "蓝色": "blue",
}


def _base_with_gt(agent: Any) -> Any | None:
    """Return the connected sim base exposing GT object positions, or None (fail-safe).

    The g1 base (MuJoCoG1) lives at ``agent._base`` and exposes
    ``get_object_positions`` (R7) + ``get_camera_pose``. Reached only via the
    duck-typed accessor — no embodiment import. None when absent / unusable.
    """
    if agent is None:
        return None
    base = getattr(agent, "_base", None)
    if base is None:
        return None
    if not callable(getattr(base, "get_object_positions", None)):
        return None
    if not callable(getattr(base, "get_camera_pose", None)):
        return None
    return base


def _resolve_target_name(target: str, gt: dict[str, list[float]]) -> str | None:
    """Map an NL ``target`` (colour or name) to the GT object body name (fail-safe).

    Resolution order (deterministic, language-neutral, NEVER reads the detector):
      1. exact body-name match (case-insensitive);
      2. substring on the body name (``'red'`` ⊂ ``'pickable_can_red'``;
         ``'can'`` ⊂ ``'pickable_can_red'``);
      3. a Chinese colour word mapped to its English token, then substring.
    Returns the single matching body name, or None if zero / ambiguous (the oracle
    then fails safe to False — it must judge ONE GT object, never guess).
    """
    if not gt:
        return None
    q = str(target or "").strip().lower()
    if not q:
        return None
    names = list(gt.keys())

    # 1. exact
    for n in names:
        if n.lower() == q:
            return n

    # 3. (pre-substring) map a Chinese colour word to its English token
    tokens = [q]
    for zh, en in _COLOUR_ZH.items():
        if zh in target:
            tokens.append(en)

    # 2. substring on the body name, for any candidate token
    for tok in tokens:
        hits = [n for n in names if tok and tok in n.lower()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            # ambiguous (e.g. token matched two bodies) — fail safe, never guess
            logger.debug(
                "detection_matches_gt: target %r ambiguous over %s", target, hits
            )
            return None
    return None


def _detector_boxes(agent: Any, base: Any, query: str) -> list[tuple[float, float, float, float]]:
    """Run the LEARNED detector on g1's live RGB ONLY → list of xyxy boxes (the CLAIM).

    The firewall: the frame source is the perception adapter's ``get_color_frame()``
    (the rendered RGB), and the detector is the SAME shared grounding-dino singleton
    the bare-cli detect tool uses — its whole input is pixels + the text query, NEVER
    a GT pose. Fail-safe to [] on any failure (no detector / no frame / model error).
    """
    # Frame source — prefer the bound perception adapter (firewalled surface), else the
    # base's raw camera. Either way the detector sees ONLY pixels.
    perception = getattr(agent, "_perception", None)
    rgb = None
    if perception is not None and callable(getattr(perception, "get_color_frame", None)):
        try:
            rgb = perception.get_color_frame()
        except Exception as exc:  # noqa: BLE001
            logger.debug("detection_matches_gt: perception.get_color_frame failed: %s", exc)
    if rgb is None and callable(getattr(base, "get_camera_frame", None)):
        try:
            rgb = base.get_camera_frame(_RENDER_W, _RENDER_H)
        except Exception as exc:  # noqa: BLE001
            logger.debug("detection_matches_gt: base.get_camera_frame failed: %s", exc)
    if rgb is None:
        return []
    try:
        from vector_os_nano.perception.grounding_dino import get_shared_detector

        detector = get_shared_detector()
        detections = detector.detect(rgb, query)
    except Exception as exc:  # noqa: BLE001
        logger.debug("detection_matches_gt: detector run failed: %s", exc)
        return []
    boxes: list[tuple[float, float, float, float]] = []
    for d in detections:
        bbox = getattr(d, "bbox", None)
        if bbox is None or len(bbox) != 4:
            continue
        try:
            boxes.append((float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])))
        except (TypeError, ValueError):
            continue
    return boxes


def make_detection_matches_gt(agent: Any) -> Callable[..., bool]:
    """Build ``detection_matches_gt(target, tol=60.0)`` bound to *agent*.

    True IFF the LEARNED detector's box for *target* on g1's live camera lands within
    *tol* pixels of where the INDEPENDENT SIM GT for that object PROJECTS onto the
    image. The truth is the GT (``base.get_object_positions``); the detection is the
    claim being judged. Fails safe to False (no base / no GT object / un-imageable /
    no box / detector error) — never raises, never a spurious True.
    """

    def detection_matches_gt(target: Any = None, tol: float = _DEFAULT_TOL_PX) -> bool:
        base = _base_with_gt(agent)
        if base is None:
            return False
        try:
            gt = base.get_object_positions()
        except Exception as exc:  # noqa: BLE001
            logger.debug("detection_matches_gt: get_object_positions failed: %s", exc)
            return False

        name = _resolve_target_name(str(target or ""), gt)
        if name is None:
            logger.debug("detection_matches_gt: no single GT object for target %r", target)
            return False
        gt_pos = gt[name]

        # Camera pose (exact world pose of g1's head camera) + intrinsics.
        try:
            cam_xpos, cam_xmat = base.get_camera_pose()
        except Exception as exc:  # noqa: BLE001
            logger.debug("detection_matches_gt: get_camera_pose failed: %s", exc)
            return False
        from vector_os_nano.perception.depth_projection import (
            mujoco_intrinsics,
            world_to_pixel,
        )

        intr = mujoco_intrinsics(_RENDER_W, _RENDER_H, vfov_deg=_G1_CAM_VFOV_DEG)
        proj = world_to_pixel(
            float(gt_pos[0]), float(gt_pos[1]), float(gt_pos[2]),
            intr, cam_xpos, cam_xmat,
        )
        if proj is None:
            # GT object is BEHIND the camera — not imageable → cannot match. (This is
            # exactly the refutation case where g1 faces away from the object.)
            logger.debug("detection_matches_gt: GT %s behind camera (not imageable)", name)
            return False
        gu, gv, _depth = proj
        # The GT must project INSIDE the frame; an off-frame projection cannot be
        # matched by any in-frame box.
        if not (0.0 <= gu < _RENDER_W and 0.0 <= gv < _RENDER_H):
            logger.debug(
                "detection_matches_gt: GT %s projects off-frame (%.1f, %.1f)", name, gu, gv
            )
            return False

        # The CLAIM: the detector's boxes (run on RGB only).
        boxes = _detector_boxes(agent, base, str(target or ""))
        if not boxes:
            return False

        # GROUNDED iff SOME box center is within tol px of the GT projection.
        best = None
        for x1, y1, x2, y2 in boxes:
            cx = 0.5 * (x1 + x2)
            cy = 0.5 * (y1 + y2)
            dist = ((cx - gu) ** 2 + (cy - gv) ** 2) ** 0.5
            if best is None or dist < best:
                best = dist
        match = best is not None and best <= float(tol)
        logger.info(
            "[G1-PERCEPT-ORACLE] target=%r gt=%s proj=(%.1f,%.1f) "
            "nearest_box_center_dist=%.1f tol=%.1f -> %s",
            target, name, gu, gv, best if best is not None else -1.0, tol, match,
        )
        return bool(match)

    return detection_matches_gt
