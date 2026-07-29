# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P2 + P3 — parallel read-only tool dispatch + actuator capability lock.

Research report §3 P2 (short-board C): a native turn dispatched a model reply's
multiple tool calls STRICTLY SERIALLY, even though independent READ-ONLY queries
(detect x3; robot_status + where) could fan out. P2 runs the turn's read-only calls
in a bounded thread pool and re-sequences results into the model's original order;
EFFECTING skills, verify and finish stay serial and mutually exclusive with the batch.

Research report §3 P3: an EFFECTING skill now declares the actuator RESOURCES it
occupies (``uses=`` / derived), and the native producer's ``CapabilityLock`` refuses
to run a skill whose resource is already held — a CLEAR rejection, never a deadlock,
released on every exit path (``finally``).

These tests are HERMETIC: a ``FakeToolScriptBackend`` replays scripted tool_use turns
through the REAL ``run_turn_native`` against duck-typed fakes. No network, no MuJoCo,
no hardware. Concurrency is proven DETERMINISTICALLY with a ``threading.Barrier`` (all
parties rendezvous ONLY if they run at once), not with flaky wall-clock timing.

Inv-1 is never touched: read-only tools open no step and record no StepRecord; the
capability lock is a pre-dispatch admission gate that computes no ``verified``.
"""
from __future__ import annotations

import threading

import pytest

from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
from tests.unit.vcli.test_native_loop import _make_agent, _make_engine, _session
from zeno.core.types import SkillResult
from zeno.vcli import native_loop
from zeno.vcli.capability_lock import CapabilityConflict, CapabilityLock


# ---------------------------------------------------------------------------
# Fakes — read-only "look" skills (no motor keywords) + a base-claiming action
# ---------------------------------------------------------------------------


class _LookSkill:
    """A READ-ONLY perception skill: no motor keywords -> ``is_read_only`` True, claims
    no capability. Optionally rendezvous on a shared barrier to PROVE concurrency."""

    parameters: dict = {}
    preconditions: list = []
    postconditions: list = []
    effects: dict = {}
    failure_modes: list = []
    barrier: "threading.Barrier | None" = None  # set per-test

    def __init__(self, name: str, marker: str) -> None:
        self.name = name
        self.description = "Report what the camera sees in the scene (read-only look)."
        self._marker = marker

    def execute(self, params, context):
        broke = False
        if _LookSkill.barrier is not None:
            try:
                _LookSkill.barrier.wait()
            except threading.BrokenBarrierError:
                broke = True
        return SkillResult(success=True, result_data={"marker": self._marker, "broke": broke})


class _BarrierWalkSkill:
    """An EFFECTING base skill (motor keyword -> claims ``{"base"}``) that rendezvous on
    a barrier to prove EFFECTING calls are NOT run concurrently (the barrier BREAKS)."""

    name = "bwalk"
    description = "Walk the base forward (moves the base)."
    parameters = {"distance": {"type": "number", "required": False, "default": 1.0}}
    preconditions = ["base"]
    postconditions: list = []
    effects = {"is_moving": False}
    failure_modes: list = []
    barrier: "threading.Barrier | None" = None

    def execute(self, params, context):
        broke = False
        if _BarrierWalkSkill.barrier is not None:
            try:
                _BarrierWalkSkill.barrier.wait()
            except threading.BrokenBarrierError:
                broke = True
        base = context.base
        if base is not None:
            base.walk(0.3, 0.0, 0.0, 1.0)
        return SkillResult(success=True, result_data={"broke": broke})


class _RaisingWalkSkill:
    """An EFFECTING base skill whose execute RAISES — to prove the capability lock is
    released on the exception path (``finally``)."""

    name = "boomwalk"
    description = "Walk the base forward (moves the base)."
    parameters: dict = {}
    preconditions = ["base"]
    postconditions: list = []
    effects = {"is_moving": False}
    failure_modes: list = []

    def execute(self, params, context):
        raise RuntimeError("boom")


def _agent_with_skills(*skills):
    """A duck-typed agent whose registry carries the walk skill PLUS *skills*."""
    agent, base = _make_agent(0.0, 0.0)
    for s in skills:
        agent._skill_registry.register(s)
    return agent, base


def _tool_results_in_order(recorder) -> list[str]:
    """Extract tool_result CONTENT strings, in order, from the LAST recorded request.

    Round N's tool_results ride in round N+1's messages, so the FINAL recorded request
    carries every prior round's tool_results exactly ONCE, in wire order — read that one
    request (reading every request would double-count the recurring history)."""
    contents: list[str] = []
    if not recorder.messages:
        return contents
    for m in recorder.messages[-1]:
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                contents.append(str(block.get("content", "")))
    return contents


class _Recorder(FakeToolScriptBackend):
    def __init__(self, turns) -> None:
        super().__init__(turns)
        self.messages: list = []

    def call(self, **kw):  # type: ignore[override]
        self.messages.append(kw["messages"])
        return super().call(**kw)


# ===========================================================================
# P3 — CapabilityLock unit behaviour (conflict, no-deadlock, finally-release)
# ===========================================================================


def test_caplock_second_claim_is_rejected_not_blocked() -> None:
    """A second holder of a held resource gets a CLEAR rejection (the holder's name),
    NOT a block — acquire returns immediately, so there is no deadlock."""
    lock = CapabilityLock()
    assert lock.acquire("navigate", {"base"}) is None  # first claim wins
    # Second claim on the SAME resource: returns the CURRENT holder, does not block.
    assert lock.acquire("walk", {"base"}) == "navigate"
    # The rejected claim took NOTHING — base is still held by navigate only.
    assert lock.held_by("base") == "navigate"
    # Release frees it; now the waiter can claim.
    lock.release("navigate", {"base"})
    assert lock.held_by("base") is None
    assert lock.acquire("walk", {"base"}) is None


def test_caplock_acquire_is_all_or_nothing() -> None:
    """A multi-resource claim is atomic: a partial conflict claims NOTHING."""
    lock = CapabilityLock()
    assert lock.acquire("grasp", {"arm", "gripper"}) is None
    # 'wave' wants {arm}; arm is held by grasp -> rejected, claims nothing.
    assert lock.acquire("wave", {"arm"}) == "grasp"
    assert lock.held_by("arm") == "grasp" and lock.held_by("gripper") == "grasp"
    # A DISJOINT claim still succeeds (base is free).
    assert lock.acquire("navigate", {"base"}) is None


def test_caplock_same_holder_reclaim_does_not_self_conflict() -> None:
    lock = CapabilityLock()
    assert lock.acquire("walk", {"base"}) is None
    assert lock.acquire("walk", {"base"}) is None  # idempotent self-claim


def test_caplock_claim_contextmanager_releases_on_exception() -> None:
    """The ``claim`` context manager releases the resource on the EXCEPTION path."""
    lock = CapabilityLock()
    with pytest.raises(ValueError):
        with lock.claim("walk", {"base"}):
            assert lock.held_by("base") == "walk"
            raise ValueError("mid-skill boom")
    assert lock.held_by("base") is None, "the lock is released in finally"


def test_caplock_claim_contextmanager_raises_on_conflict() -> None:
    lock = CapabilityLock()
    lock.acquire("navigate", {"base"})
    with pytest.raises(CapabilityConflict):
        with lock.claim("walk", {"base"}):
            pass  # never entered
    # The failed claim did not steal / release navigate's hold.
    assert lock.held_by("base") == "navigate"


def test_caplock_release_is_holder_scoped_and_idempotent() -> None:
    lock = CapabilityLock()
    lock.acquire("navigate", {"base"})
    lock.release("someone_else", {"base"})  # not the holder -> no-op
    assert lock.held_by("base") == "navigate"
    lock.release("navigate", {"base"})
    lock.release("navigate", {"base"})  # double release -> no-op
    assert lock.held_by("base") is None


# ===========================================================================
# P3 — capability lock WIRED into the runner's effecting dispatch
# ===========================================================================


def _make_runner(agent, engine):
    from zeno.vcli.cognitive.trace_store import verify_oracle_names

    verifier = native_loop._build_verifier(engine, agent)
    oracle_names = verify_oracle_names(agent, engine)
    motor_tools = native_loop._build_motor_tools(agent, engine)
    ctx = native_loop._build_tool_context(agent, _session(), None, engine)
    runner = native_loop.NativeStepRunner(agent, verifier, oracle_names, motor_tools, ctx)
    return runner, motor_tools


def test_walk_wrapper_claims_base_and_is_not_read_only() -> None:
    """The derived capability: a motor 'walk' claims {"base"} and is NOT read-only
    (so it can never join the concurrent batch)."""
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, _Recorder.from_tool_script([]))
    motor_tools = native_loop._build_motor_tools(agent, eng)
    walk = motor_tools["walk"]
    assert native_loop._tool_capabilities(walk) == frozenset({"base"})
    assert native_loop._tool_is_read_only(walk) is False


def test_dispatch_rejects_effecting_skill_when_resource_held() -> None:
    """When the base is already held (a would-be concurrent / background holder), an
    effecting dispatch is REJECTED with a clear message — not blocked, no step opened."""
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, _Recorder.from_tool_script([]))
    runner, _ = _make_runner(agent, eng)
    # Simulate another holder owning the base.
    runner._cap_lock.acquire("external_holder", {"base"})

    res = runner.dispatch_skill("walk", {"distance": 1.0, "speed": 0.3})
    assert res.is_error
    assert "base" in res.content and "external_holder" in res.content
    # No deadlock (returned promptly) and NO step opened (the reject fired before capture).
    assert runner.has_unverified_action is False
    # The external hold is intact — the rejected claim stole nothing.
    assert runner._cap_lock.held_by("base") == "external_holder"


def test_dispatch_releases_capability_on_skill_exception() -> None:
    """A skill that RAISES still releases the base — the lock never wedges."""
    agent, _base = _agent_with_skills(_RaisingWalkSkill())
    eng = _make_engine(agent, _Recorder.from_tool_script([]))
    runner, _ = _make_runner(agent, eng)

    res = runner.dispatch_skill("boomwalk", {})
    assert res.is_error and "raised" in res.content.lower()
    assert runner._cap_lock.held_by("base") is None, "released in finally after the raise"


def test_two_serial_effecting_calls_each_acquire_and_release() -> None:
    """Two effecting calls in one turn run SERIALLY and each acquires+releases the
    base — the lock does not wedge between them (finally release proven end-to-end)."""
    agent, base = _make_agent(0.0, 0.0)
    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("walk twice then verify", session=_session())
    # Both walks landed in ONE step's chain (serial dispatch through dispatch_skill),
    # and the base advanced by BOTH moves — the lock never blocked the second call.
    assert len(trace.steps) == 1
    assert trace.steps[0].strategy == "walk"
    assert base.get_position()[0] > 1.5


# ===========================================================================
# P2 — concurrent read-only fan-out
# ===========================================================================


def test_read_only_calls_run_concurrently_and_results_are_order_stable() -> None:
    """Three read-only looks in ONE turn rendezvous on a Barrier(3) — they PASS only if
    dispatched concurrently. Their tool_results are re-sequenced into the model's
    ORIGINAL order (A, B, C), regardless of thread completion order."""
    looks = [_LookSkill("look_a", "A"), _LookSkill("look_b", "B"), _LookSkill("look_c", "C")]
    agent, _base = _agent_with_skills(*looks)
    _LookSkill.barrier = threading.Barrier(3, timeout=5)
    try:
        backend = _Recorder.from_tool_script(
            [
                tool_turn(
                    ("look_a", {}), ("look_b", {}), ("look_c", {}),
                ),
                tool_turn(("finish", {})),
            ]
        )
        eng = _make_engine(agent, backend)
        trace = eng.run_turn_native("look around", session=_session())
    finally:
        _LookSkill.barrier = None

    # Concurrency proven: every look passed the 3-party barrier (a serial dispatch
    # would have timed out and BROKEN it -> broke=True in the content).
    contents = _tool_results_in_order(backend)
    markers = [c for c in contents if "marker" in c]
    assert len(markers) == 3
    assert all("'broke': False" in c for c in markers), "barrier rendezvous -> ran at once"
    # Order STABLE: results appear in the model's original A, B, C order.
    order = [c.split("'marker': '")[1][0] for c in markers]
    assert order == ["A", "B", "C"], "results re-sequenced into original tool-call order"
    # Read-only tools opened NO step -> the turn finished without a verify nudge and
    # the trace carries no action step (Inv-1: no StepRecord from a read-only query).
    assert len(trace.steps) == 0


def test_two_effecting_calls_are_not_run_concurrently() -> None:
    """Two effecting base skills in one turn must NOT be parallelized: a Barrier(2) they
    both wait on BREAKS (times out) because they are dispatched one-at-a-time."""
    agent, base = _agent_with_skills(_BarrierWalkSkill())
    _BarrierWalkSkill.barrier = threading.Barrier(2, timeout=0.4)
    try:
        backend = _Recorder.from_tool_script(
            [
                tool_turn(("bwalk", {}), ("bwalk", {})),
                tool_turn(("verify", {"expr": "at_position(0.6, 0.0, 1.0)"})),
                tool_turn(("finish", {})),
            ]
        )
        eng = _make_engine(agent, backend)
        eng.run_turn_native("walk walk", session=_session())
    finally:
        _BarrierWalkSkill.barrier = None

    contents = _tool_results_in_order(backend)
    walk_results = [c for c in contents if "'broke'" in c]
    assert len(walk_results) == 2
    # Serial dispatch -> neither call had a concurrent partner at the barrier -> BOTH broke.
    assert all("'broke': True" in c for c in walk_results), "effecting calls ran serially"


def test_single_read_only_call_still_works_serial_path() -> None:
    """A turn with ONE read-only call stays on the byte-identical serial path (the
    concurrent batch forms only at >= _MIN_CONCURRENT_READONLY) and still runs."""
    assert native_loop._MIN_CONCURRENT_READONLY == 2
    look = _LookSkill("look_a", "A")
    agent, _base = _agent_with_skills(look)  # barrier left None -> immediate return
    backend = _Recorder.from_tool_script(
        [tool_turn(("look_a", {})), tool_turn(("finish", {}))]
    )
    eng = _make_engine(agent, backend)
    eng.run_turn_native("look once", session=_session())
    contents = _tool_results_in_order(backend)
    markers = [c for c in contents if "marker" in c]
    assert len(markers) == 1 and "'marker': 'A'" in markers[0]


def test_mixed_turn_preserves_order_and_isolates_effecting() -> None:
    """A mixed turn [look_a, look_b, walk]: the two looks fan out concurrently, the walk
    stays serial; all three results are reported in ORIGINAL order."""
    looks = [_LookSkill("look_a", "A"), _LookSkill("look_b", "B")]
    agent, base = _agent_with_skills(*looks)
    _LookSkill.barrier = threading.Barrier(2, timeout=5)
    try:
        backend = _Recorder.from_tool_script(
            [
                tool_turn(("look_a", {}), ("look_b", {}), ("walk", {"distance": 1.0, "speed": 0.3})),
                tool_turn(("verify", {"expr": "at_position(1.0, 0.0, 1.0)"})),
                tool_turn(("finish", {})),
            ]
        )
        eng = _make_engine(agent, backend)
        trace = eng.run_turn_native("look twice and walk", session=_session())
    finally:
        _LookSkill.barrier = None

    contents = _tool_results_in_order(backend)
    # The two looks ran at once (barrier passed), the walk moved the base once.
    look_results = [c for c in contents if "marker" in c]
    assert [c.split("'marker': '")[1][0] for c in look_results] == ["A", "B"]
    assert all("'broke': False" in c for c in look_results)
    assert base.get_position()[0] > 0.5  # the effecting walk still ran
    # Exactly ONE action step (the walk); the looks recorded none.
    assert len(trace.steps) == 1 and trace.steps[0].strategy == "walk"
