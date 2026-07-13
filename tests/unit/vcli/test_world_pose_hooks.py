# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Kernel world-pose hooks — global-awareness plumbing (RED first).

CEO directive 2026-07-13 night: the agent must ALWAYS know its live global
pose. Two OPTIONAL, duck-typed world hooks (the supports_pose_reset /
disable_keyword_ladder plug-and-play pattern — absent hook = byte-identical
kernel behaviour):

* Hook A — ``world.world_context_ttl() -> float``: the engine's
  ``_build_world_context`` cache TTL. The kernel default (5.0 s) protects
  EXPENSIVE sensor/graph queries; a world whose pose read is a cached driver
  attribute (go2w_real) returns 0.0 so plan-time context is never stale
  (at 0.6 m/s a 5 s-stale pose is up to 3 m wrong). Absent/raising hook =
  the exact 5.0 s default.

* Hook B — ``world.live_status_line(agent) -> str | None``: ONE short line of
  live state the native loop refreshes before EVERY model call, appended as a
  single clearly-marked system-side block. EPHEMERAL by construction: the
  block is rebuilt per call (replace, never accumulate) and never enters the
  session messages. Absent/None/raising hook = the native loop passes the
  system prompt object UNCHANGED (byte-identical, pinned here).

Hermetic: fake worlds + the native-loop fakes (fake base, scripted backend);
no MuJoCo, no ROS, no network.
"""
from __future__ import annotations

from types import SimpleNamespace

from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
from tests.unit.vcli.test_native_loop import _make_agent, _make_engine, _session


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _MovingBase:
    """Minimal base for the engine world-context read: pose the test can move."""

    def __init__(self) -> None:
        self.x = 0.0

    def get_position(self) -> list[float]:
        return [self.x, 0.0, 0.0]

    def get_heading(self) -> float:
        return 0.0


class _NoHookWorld:
    """A world WITHOUT either pose hook (sim/dev shape) — kernel default path."""

    name = "no-hook"

    def is_robot(self) -> bool:
        return True


class _TtlZeroWorld(_NoHookWorld):
    """Hook A: zero-cost pose read — every context build must be fresh."""

    def world_context_ttl(self) -> float:
        return 0.0


class _TtlRaisesWorld(_NoHookWorld):
    """Hook A raising — the engine must fall back to the 5.0 s default."""

    def world_context_ttl(self) -> float:
        raise RuntimeError("boom")


def _context_engine(world) -> tuple:
    """A real engine wired with *world* + a movable fake base (no VGG needed)."""
    from zeno.vcli.engine import VectorEngine

    class _NeverCalledBackend:
        def call(self, **kw):  # pragma: no cover - guard
            raise AssertionError("backend must not be called by _build_world_context")

    eng = VectorEngine(backend=_NeverCalledBackend())
    base = _MovingBase()
    eng._world = world
    eng._vgg_agent = SimpleNamespace(_base=base, _spatial_memory=None)
    return eng, base


# ---------------------------------------------------------------------------
# Hook A — world_context_ttl()
# ---------------------------------------------------------------------------


def test_no_hook_keeps_the_5s_ttl_cache() -> None:
    """Absent hook: the 5.0 s default TTL caches — byte-identical kernel path."""
    eng, base = _context_engine(_NoHookWorld())
    assert eng._world_context_ttl == 5.0  # the kernel default is untouched
    first = eng._build_world_context()
    assert "Position: (0.0, 0.0)" in first
    base.x = 3.0
    second = eng._build_world_context()
    assert second == first, "within the default TTL the cached context must return"


def test_ttl_zero_hook_rebuilds_every_call() -> None:
    """Hook A honored: ttl 0.0 -> the driver is re-read on EVERY build."""
    eng, base = _context_engine(_TtlZeroWorld())
    first = eng._build_world_context()
    assert "Position: (0.0, 0.0)" in first
    base.x = 3.0
    second = eng._build_world_context()
    assert "Position: (3.0, 0.0)" in second, (
        "world_context_ttl()==0.0 must bypass the 5 s cache and see the live pose"
    )


def test_ttl_hook_raising_falls_back_to_default() -> None:
    """A raising hook fails safe to the kernel default (cached, never a crash)."""
    eng, base = _context_engine(_TtlRaisesWorld())
    first = eng._build_world_context()
    base.x = 3.0
    second = eng._build_world_context()
    assert second == first


# ---------------------------------------------------------------------------
# Hook B — live_status_line(agent), refreshed before EVERY native model call
# ---------------------------------------------------------------------------


class _SystemRecorder(FakeToolScriptBackend):
    """Scripted backend that records the ``system`` blocks of every call."""

    def __init__(self, turns) -> None:
        super().__init__(turns)
        self.systems: list = []

    def call(self, **kw):  # type: ignore[override]
        self.systems.append(kw["system"])
        return super().call(**kw)


def _live_marker() -> str:
    from zeno.vcli.native_loop import _LIVE_STATUS_PREFIX

    return _LIVE_STATUS_PREFIX


def _walk_script() -> list:
    return [
        tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
        tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
        tool_turn(("finish", {})),
    ]


def test_no_hook_native_system_prompt_byte_identical() -> None:
    """Absent hook: the native loop passes the system prompt UNCHANGED —
    same object every iteration, no live-state block (sim worlds untouched)."""
    backend = _SystemRecorder.from_tool_script(_walk_script())
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)  # RobotWorld — no live_status_line hook
    eng.run_turn_native("walk then verify", session=_session())

    assert len(backend.systems) >= 2
    assert all(s is backend.systems[0] for s in backend.systems), (
        "without the hook the SAME system prompt object must be passed each call"
    )
    marker = _live_marker()
    for system in backend.systems:
        assert all(marker not in b.get("text", "") for b in system)


def test_live_status_line_refreshed_before_every_model_call() -> None:
    """Hook B: ONE marked system-side block per call, re-read from the DRIVER
    between iterations (the fake base moves; the next call sees the new pose),
    never accumulating."""
    from zeno.vcli.worlds.robot import RobotWorld

    class _LiveWorld(RobotWorld):
        def live_status_line(self, agent):
            base = getattr(agent, "_base", None)
            return f"pose x={base._x:.2f} y={base._y:.2f}"

    backend = _SystemRecorder.from_tool_script(_walk_script())
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    eng._world = _LiveWorld()
    eng.run_turn_native("walk then verify", session=_session())

    marker = _live_marker()
    assert len(backend.systems) == 3
    sizes = set()
    for system in backend.systems:
        live_blocks = [b for b in system if marker in b.get("text", "")]
        assert len(live_blocks) == 1, "exactly ONE live-state block per model call"
        sizes.add(len(system))
    assert len(sizes) == 1, "the live block must REPLACE, never accumulate"
    # Iteration 1 sees the pre-walk pose; iteration 2 (after the walk moved the
    # driver 2 m) sees the NEW pose — the hook is re-read per model call.
    first_live = [b for b in backend.systems[0] if marker in b.get("text", "")][0]
    second_live = [b for b in backend.systems[1] if marker in b.get("text", "")][0]
    assert "x=0.00" in first_live["text"]
    assert "x=2.00" in second_live["text"]
    assert first_live["text"] != second_live["text"]


def test_live_status_hook_none_or_raising_adds_nothing() -> None:
    """A None-returning or raising hook degrades to the exact no-hook prompt."""
    from zeno.vcli.worlds.robot import RobotWorld

    class _NoneWorld(RobotWorld):
        def live_status_line(self, agent):
            return None

    class _RaisingWorld(RobotWorld):
        def live_status_line(self, agent):
            raise RuntimeError("sensor exploded")

    marker = _live_marker()
    for world in (_NoneWorld(), _RaisingWorld()):
        backend = _SystemRecorder.from_tool_script(_walk_script())
        agent, _base = _make_agent(0.0, 0.0)
        eng = _make_engine(agent, backend)
        eng._world = world
        eng.run_turn_native("walk then verify", session=_session())
        for system in backend.systems:
            assert all(marker not in b.get("text", "") for b in system)


def test_live_status_line_is_flattened_to_one_line() -> None:
    """A multi-line/whitespace-heavy hook return is flattened — the injection
    stays ONE token-cheap system-side line by construction."""
    from zeno.vcli.worlds.robot import RobotWorld

    class _SprawlingWorld(RobotWorld):
        def live_status_line(self, agent):
            return "  pose x=0.00\n  y=0.00\n\n  extra   spaces  "

    backend = _SystemRecorder.from_tool_script(_walk_script())
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    eng._world = _SprawlingWorld()
    eng.run_turn_native("walk then verify", session=_session())

    marker = _live_marker()
    live = [b for b in backend.systems[0] if marker in b.get("text", "")][0]
    assert "\n" not in live["text"]
    assert "pose x=0.00 y=0.00 extra spaces" in live["text"]
