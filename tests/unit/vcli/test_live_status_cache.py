# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P3.11 — live-status TTL cache (owner: 'cli 整个交互很卡').

The composer footer re-renders on EVERY keystroke and every 0.5s refresh, and
each redraw read the world's live_status_line hook — three real driver reads
on hardware. Under the persistent composer's high-frequency transcript prints
that is dozens of driver reads/sec, which stalls typing. A short TTL cache
makes redraws memory-cheap; odom never needs sub-200ms UI freshness.
"""
from __future__ import annotations

from zeno.vcli.cli import _live_status_cached


class _World:
    def __init__(self) -> None:
        self.calls = 0

    def live_status_line(self, agent):  # noqa: ANN001
        self.calls += 1
        return f"pose read #{self.calls}"


def _state(world):
    return {"world": world}


def test_repeated_redraws_within_ttl_hit_cache() -> None:
    world = _World()
    state = _state(world)
    clock = [1000.0]
    # 100 redraws in a 50ms burst -> ONE hook call.
    for _ in range(100):
        clock[0] += 0.0005
        _live_status_cached(state, now=lambda: clock[0], ttl=0.2)
    assert world.calls == 1


def test_cache_refreshes_after_ttl() -> None:
    world = _World()
    state = _state(world)
    clock = [1000.0]
    out1 = _live_status_cached(state, now=lambda: clock[0], ttl=0.2)
    clock[0] += 0.25  # past TTL
    out2 = _live_status_cached(state, now=lambda: clock[0], ttl=0.2)
    assert world.calls == 2
    assert out1 != out2  # fresh value surfaced


def test_cache_value_matches_direct_read() -> None:
    world = _World()
    state = _state(world)
    val = _live_status_cached(state, now=lambda: 5.0, ttl=0.2)
    assert val == "pose read #1"


def test_no_world_returns_none_without_caching_error() -> None:
    assert _live_status_cached({}, now=lambda: 1.0, ttl=0.2) is None
