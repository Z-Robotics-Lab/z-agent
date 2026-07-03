# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: perception_grasp's single-shot far-fetch recovery (_far_localize_and_approach).

When a colour target is beyond the 2m front-workspace HSV gate it perceives as
'no_detections'; the un-gated open-vocab localizer can still see it, so the skill localizes
+ drives to the 0.95m standoff ONCE and re-perceives. These pin the DECISION logic with
fakes (no sim): steerable-base guard, empty/too-close/too-far rejection, in-band drive, and
the single-sourced standoff. The end-to-end grounding is the REAL-VERIFY (bare cli + eyes).
"""
from __future__ import annotations

import math

import pytest

from vector_os_nano.skills import perception_grasp as pg


class _FakeBase:
    def __init__(self, pos=(10.0, 3.0), heading=0.0, nav_ok=True):
        self._pos = pos
        self._h = heading
        self._nav_ok = nav_ok
        self.nav_calls: list[tuple[float, float]] = []
        self.walk_calls: list[dict] = []

    def get_position(self):
        return (self._pos[0], self._pos[1], 0.35)

    def get_heading(self):
        return self._h

    def navigate_to(self, x, y, *a, **k):
        self.nav_calls.append((x, y))
        return self._nav_ok

    def walk(self, vx=0.0, vy=0.0, vyaw=0.0, duration=0.0):
        # Record + crudely integrate heading so _grasp_ready_repose's yaw deadband
        # converges in one turn step (real driver turns the body).
        self.walk_calls.append({"vx": vx, "vy": vy, "vyaw": vyaw, "duration": duration})
        self._h += vyaw * duration


class _NoNavBase:  # missing navigate_to -> not steerable
    def get_position(self):
        return (10.0, 3.0, 0.35)

    def get_heading(self):
        return 0.0


def _patch_localize(monkeypatch, pts):
    import vector_os_nano.perception.object_localizer as ol
    monkeypatch.setattr(ol, "localize_objects_3d", lambda perception, queries: pts)


def test_far_target_localizes_and_drives_to_standoff(monkeypatch):
    """3.88m-ahead bottle (in band) -> localize + drive to a 0.95m standoff -> True."""
    _patch_localize(monkeypatch, [("green bottle", 13.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0))
    assert pg._far_localize_and_approach(object(), base, "green bottle") is True
    assert len(base.nav_calls) == 1
    sx, sy = base.nav_calls[0]
    assert sx == pytest.approx(13.88 - 0.95, abs=0.05)  # standoff on the dog's side
    assert sy == pytest.approx(3.0, abs=0.05)


def test_far_recovery_faces_target_when_arrival_heading_is_off(monkeypatch):
    """FAR's navigate_to has no terminal-heading control: the dog can arrive at the
    standoff facing AWAY from the bottle, and the re-perceive's one-directional ~200deg
    scan then misses it (the dominant far-fetch reliability variance). Since the seed
    gives the KNOWN target xy, the recovery must TURN TO FACE it after driving."""
    _patch_localize(monkeypatch, [("green bottle", 13.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0), heading=math.pi)  # facing -X, AWAY from the +X bottle
    assert pg._far_localize_and_approach(object(), base, "green bottle") is True
    assert len(base.nav_calls) == 1
    turns = [c for c in base.walk_calls if abs(c["vyaw"]) > 1e-6]
    assert turns, "recovery must turn to face the (known) target after driving to the standoff"


def test_far_recovery_closes_the_loop_on_heading(monkeypatch):
    """The repose turn is OPEN-LOOP and undershoots a large turn (~12deg residual observed),
    enough to miss the bottle at the close standoff. The recovery must then CLOSE THE LOOP via
    _face_object so the final heading faces the (known) target within _FACE_TOL_RAD."""
    _patch_localize(monkeypatch, [("green bottle", 13.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0), heading=math.pi)  # 180deg off
    assert pg._far_localize_and_approach(object(), base, "green bottle") is True
    # Base stays at (10,3) (the fake's navigate_to doesn't move it); bearing to the +X bottle ~0.
    bearing = math.atan2(3.0 - base._pos[1], 13.88 - base._pos[0])
    err = abs(math.atan2(math.sin(bearing - base._h), math.cos(bearing - base._h)))
    assert err < pg._FACE_TOL_RAD, f"final heading must face the target (err={err:.3f} >= {pg._FACE_TOL_RAD})"


def test_far_recovery_face_is_benign_when_already_head_on(monkeypatch):
    """Idempotent: when the dog already faces the +X bottle, the facing repose issues
    no turn (yaw error below the deadband) — no regression to the spawn-facing path."""
    _patch_localize(monkeypatch, [("green bottle", 13.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0), heading=0.0)  # already facing +X
    assert pg._far_localize_and_approach(object(), base, "green bottle") is True
    turns = [c for c in base.walk_calls if abs(c["vyaw"]) > 1e-6]
    assert not turns, "already head-on -> the facing repose must not issue a turn"


def test_non_steerable_base_returns_false():
    assert pg._far_localize_and_approach(object(), _NoNavBase(), "green bottle") is False


def test_empty_localize_returns_false(monkeypatch):
    _patch_localize(monkeypatch, [])
    base = _FakeBase()
    assert pg._far_localize_and_approach(object(), base, "green bottle") is False
    assert base.nav_calls == []


def test_close_but_blind_target_reposes_to_standoff(monkeypatch):
    """R234/E54 warehouse fix: recovery fires ONLY after the scan already failed
    no_detections (the caller gates it), so a close target here means the dog arrived
    ~0.88m away but MIS-ORIENTED/occluded (front_object_mask=0px, observed in the compact
    warehouse enclosure). The old code SKIPPED d<1.6m as 'the self-approach's job' — but the
    self-approach cannot recover a target it can't see. Since the un-gated localize KNOWS the
    xy, back off to the 0.95m standoff and FACE it, then let the caller re-perceive. This is
    the same localize->standoff->face mechanism, just widened to cover the too-close case."""
    _patch_localize(monkeypatch, [("green bottle", 10.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0))  # dog at 10.0, target 10.88 -> d=0.88m, close-but-blind
    assert pg._far_localize_and_approach(object(), base, "green bottle") is True
    assert len(base.nav_calls) == 1
    sx, sy = base.nav_calls[0]
    assert sx == pytest.approx(10.88 - 0.95, abs=0.05)  # backed off to the dog-side standoff
    assert sy == pytest.approx(3.0, abs=0.05)


def test_degenerate_on_top_of_target_is_rejected(monkeypatch):
    """A d<~0.3m localize is a degenerate self-detection (dog basically on the target) —
    below _RECOVERY_MIN_M, reject so we don't thrash on a phantom zero-distance seed."""
    _patch_localize(monkeypatch, [("green bottle", 10.1, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0))  # d=0.1m
    assert pg._far_localize_and_approach(object(), base, "green bottle") is False
    assert base.nav_calls == []


def test_implausibly_far_target_is_rejected(monkeypatch):
    """20m away -> beyond _FAR_RECOVERY_MAX_M -> implausible localize, honest no_detections."""
    _patch_localize(monkeypatch, [("green bottle", 30.0, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0))
    assert pg._far_localize_and_approach(object(), base, "green bottle") is False
    assert base.nav_calls == []


def test_nav_failure_propagates_false(monkeypatch):
    _patch_localize(monkeypatch, [("green bottle", 13.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0), nav_ok=False)
    assert pg._far_localize_and_approach(object(), base, "green bottle") is False
    assert len(base.nav_calls) == 1  # it tried, then reported honest failure


def test_standoff_single_sourced_with_navigate_to_object():
    """The recovery standoff must not drift from navigate_to_object's (Rule 11)."""
    from vector_os_nano.skills.navigate_to_object import _VICINITY_CLEARANCE_M
    assert pg._FAR_STANDOFF_M == _VICINITY_CLEARANCE_M
