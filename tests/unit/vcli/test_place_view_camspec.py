# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""The verdict-snapshot camera frames the RECEPTACLE on a PLACE turn (R281/E78).

Frontier finding: the single verdict frame TRACKS the robot (side view, az 270, dist 2.4),
which centres the dog but pushes the place receptacle (shelf/bin) to the frame EDGE or
off-frame on a place — so the eyes vlm-judge reads ``workspace_in_frame=no`` and ABSTAINs
(a false-neg that blocks eyes-place corroboration, see var/evidence/R278/eyes_seq2.png).

These GL-free tests pin the PURE camera-selection math:
  * ``select_place_camspec`` returns a place-framing CamSpec ONLY when a place happened
    (``place_active`` — an object rests on the receptacle, the place-verdict GT), so a FETCH (object
    in the gripper, nothing on the bin) keeps the proven robot side-view; no regression, else ``None``.
  * ``place_view_camspec`` frames BOTH bodies: lookat at their midpoint, distance covering the
    separation (a seq place can leave the dog ~2 m from the bin — both must still fit). It only AIMS
    the camera — it never reads or touches the verdict (honesty).
"""
from __future__ import annotations

import math

from vector_os_nano.acceptance import capture


# go2_room.xml: pick_table (10.95, 3.0), place_bin (10.95, 4.60); ~1.6 m apart.
# A place standoff sits the dog ~0.7 m south of the bin; a fetch sits it at the pick table
# ~2.5 m from the bin. extent = (region=(x_min,y_min,x_max,y_max), rest_z).
_BIN_EXTENT = ((10.80, 4.45, 11.10, 4.75), 0.35)
_BIN_CX, _BIN_CY = 10.95, 4.60


def test_select_returns_none_on_a_fetch():
    """No object on the bin (a fetch — object is in the gripper) -> robot side-view (None),
    EVEN when the robot happens to be near the receptacle."""
    near_pose = (10.95, 3.90, 0.0)
    assert capture.select_place_camspec(near_pose, _BIN_EXTENT, place_active=False) is None


def test_select_returns_place_camspec_when_place_active():
    """An object rests on the bin -> a place-framing CamSpec, regardless of robot distance
    (a seq place can leave the dog ~2 m away — the workspace must still be framed)."""
    for pose in ((10.95, 3.90, 0.0), (10.95, 2.20, 0.0)):
        cam = capture.select_place_camspec(pose, _BIN_EXTENT, place_active=True)
        assert cam is not None
        assert isinstance(cam, capture.CamSpec)


def test_select_none_on_missing_inputs():
    assert capture.select_place_camspec(None, _BIN_EXTENT, place_active=True) is None
    assert capture.select_place_camspec((10.95, 3.90, 0.0), None, place_active=True) is None


def test_place_camspec_lookat_is_the_midpoint():
    """The frame is centred BETWEEN robot and receptacle so BOTH are in it (not robot-only)."""
    place_pose = (10.95, 3.90, 0.0)
    cam = capture.place_view_camspec(place_pose, (_BIN_CX, _BIN_CY, 0.35))
    exp_x = (place_pose[0] + _BIN_CX) / 2.0
    exp_y = (place_pose[1] + _BIN_CY) / 2.0
    assert math.isclose(cam.lookat[0], exp_x, abs_tol=1e-6)
    assert math.isclose(cam.lookat[1], exp_y, abs_tol=1e-6)


def test_place_camspec_distance_covers_the_separation():
    """Distance must exceed the robot<->receptacle separation so both fit in the frame
    (the seq2 bug was dist 2.4 tracking the robot -> the bin cropped off the edge)."""
    place_pose = (10.95, 3.90, 0.0)
    sep = math.hypot(place_pose[0] - _BIN_CX, place_pose[1] - _BIN_CY)
    cam = capture.place_view_camspec(place_pose, (_BIN_CX, _BIN_CY, 0.35))
    assert cam.distance > sep
    # A far separation must not blow the distance past a sane ceiling (VLM needs the bodies big).
    far = capture.place_view_camspec((10.95, 0.0, 0.0), (_BIN_CX, _BIN_CY, 0.35))
    assert far.distance <= 5.0


def test_place_camspec_is_pure_no_agent_no_verdict():
    """Honesty: the framing math is a pure function of poses — it cannot read a VerdictReport."""
    import inspect

    params = list(inspect.signature(capture.place_view_camspec).parameters)
    assert params == ["pose", "recept_center"]
