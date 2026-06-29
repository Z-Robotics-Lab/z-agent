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

import pytest

from vector_os_nano.skills import perception_grasp as pg


class _FakeBase:
    def __init__(self, pos=(10.0, 3.0), heading=0.0, nav_ok=True):
        self._pos = pos
        self._h = heading
        self._nav_ok = nav_ok
        self.nav_calls: list[tuple[float, float]] = []

    def get_position(self):
        return (self._pos[0], self._pos[1], 0.35)

    def get_heading(self):
        return self._h

    def navigate_to(self, x, y, *a, **k):
        self.nav_calls.append((x, y))
        return self._nav_ok


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


def test_non_steerable_base_returns_false():
    assert pg._far_localize_and_approach(object(), _NoNavBase(), "green bottle") is False


def test_empty_localize_returns_false(monkeypatch):
    _patch_localize(monkeypatch, [])
    base = _FakeBase()
    assert pg._far_localize_and_approach(object(), base, "green bottle") is False
    assert base.nav_calls == []


def test_too_close_target_is_not_a_far_recovery(monkeypatch):
    """0.88m ahead -> within the 1.6m self-approach radius -> the in-reach path handles it."""
    _patch_localize(monkeypatch, [("green bottle", 10.88, 3.0, 0.32)])
    base = _FakeBase(pos=(10.0, 3.0))
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
