# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real verify-vocab integrity — the REAL world's wiring of the kernel's
verify-vocab seams (field forensics 2026-07-10, real-robot REPL).

What broke on hardware: the engine unconditionally seeds sim-ish stubs
(``describe_scene``->'' , ``detect_objects``->[], ``certainty``->0.0, ...) plus
``get_position``/``get_heading`` into the verifier namespace BEFORE the world
merge; the merge is additive-only, so go2w_real could never remove them. They
leaked into ``verify_oracle_names`` -> the verify tool schema + decompose
prompts advertised phantom oracles -> the model verified against stub-falsy
predicates -> 'verdict 0/N grounded'. The class-default foreach example
additionally taught ``detect_objects()`` in EVERY decompose prompt.

Pinned here (GREEN = the world now owns its verify vocabulary):
  * ``verify_namespace_deny()`` declares the full sim-stub set (and never
    denies the world's own oracles).
  * The ENGINE namespace + ``verify_oracle_names`` on go2w_real are clean —
    exactly the world's odometry oracles + the kernel dev predicates.
  * The native verify tool schema built from that live set teaches ``at`` (the
    real arrival oracle), never ``at_position``.
  * The decompose prompt contains NO foreign predicate — the foreach example
    is suppressed (this world has no list-producing detect step to loop over).

Hermetic: fake Go2WHardware stand-in, no ROS env, no LLM, no sim.
"""
from __future__ import annotations

from types import SimpleNamespace


# The engine-seeded names that are sim/perception vocabulary go2w_real does NOT
# serve. get_position/get_heading are included ON PURPOSE: the world-context
# display (engine._build_world_context) and actor-causation both read the BASE
# object directly, never the verifier namespace — the only namespace consumers
# are verify eval + the advertised oracle set, where a raw-pose read invites the
# model to bypass the calibrated at()/moved() odometry oracles.
_SIM_STUB_NAMES = frozenset(
    {
        "describe_scene",
        "detect_objects",
        "certainty",
        "last_seen",
        "objects_in_room",
        "find_object",
        "room_coverage",
        "predict_navigation",
        "at_position",
        "facing",
        "get_position",
        "get_heading",
    }
)

_REAL_ORACLES = frozenset(
    {"at", "moved", "explore_finished", "explored_progress", "route_reached", "stack_ready"}
)


class _FakeHW:
    """Stand-in Go2WHardware exposing the surface the engine/world bind against."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self._x, self._y = x, y

    def get_position(self):
        return (self._x, self._y, 0.0)

    def get_heading(self) -> float:
        return 0.0


def _world():
    from zeno.vcli.worlds import resolve_world_named

    return resolve_world_named("go2w_real")


def _engine_with_real_world():
    from zeno.vcli.engine import VectorEngine

    eng = VectorEngine(backend=SimpleNamespace())
    eng._world = _world()
    agent = SimpleNamespace(_base=_FakeHW(), _arm=None, _spatial_memory=None)
    return eng, agent


def test_world_declares_the_sim_stub_deny_set() -> None:
    world = _world()
    hook = getattr(world, "verify_namespace_deny", None)
    assert callable(hook), "go2w_real must declare verify_namespace_deny()"
    deny = frozenset(hook())
    assert _SIM_STUB_NAMES <= deny, f"missing: {sorted(_SIM_STUB_NAMES - deny)}"
    # The deny hook must NEVER remove the world's own oracles (stricter-only).
    own = frozenset(world.build_verify_namespace(None).keys())
    assert not (deny & own), f"world denies its own oracles: {sorted(deny & own)}"


def test_engine_namespace_is_clean_on_go2w_real() -> None:
    eng, agent = _engine_with_real_world()
    ns = eng._build_verifier_namespace(agent)
    for stub in sorted(_SIM_STUB_NAMES):
        assert stub not in ns, f"sim stub {stub!r} leaked into the go2w_real namespace"
    for oracle in sorted(_REAL_ORACLES):
        assert oracle in ns, f"real oracle {oracle!r} missing from the namespace"


def test_verify_oracle_names_advertises_only_served_predicates() -> None:
    from zeno.vcli.cognitive.trace_store import verify_oracle_names

    eng, agent = _engine_with_real_world()
    names = verify_oracle_names(agent, eng)
    assert _REAL_ORACLES <= names
    assert not (_SIM_STUB_NAMES & names), (
        f"stub names advertised: {sorted(_SIM_STUB_NAMES & names)}"
    )


def test_native_verify_schema_teaches_at_not_at_position() -> None:
    """The synthetic verify tool built from the LIVE go2w_real oracle set must
    teach the real arrival oracle ``at`` and never the phantom ``at_position``."""
    from zeno.vcli.cognitive.trace_store import verify_oracle_names
    from zeno.vcli.native_loop import _verify_tool_schema

    eng, agent = _engine_with_real_world()
    names = verify_oracle_names(agent, eng)
    desc = _verify_tool_schema(names)["description"]
    assert "at_position" not in desc
    assert "e.g. at(2.0, 0.0)" in desc


def test_decompose_vocab_suppresses_the_foreach_example() -> None:
    """go2w_real has NO list-producing detect step — a loop example would have to
    invent foreign predicates (the class default teaches ``detect_objects()``).
    The world sets foreach_example='' so the section is suppressed entirely."""
    vocab = _world().decompose_vocab()
    assert vocab is not None
    assert vocab.foreach_example == ""


def test_decompose_prompt_contains_no_foreign_predicates() -> None:
    """End-to-end: the RENDERED go2w_real decompose prompt names none of the sim
    vocabulary — no detect_objects, no at_position, no Loop Example section."""
    from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer

    vocab = _world().decompose_vocab()
    dec = GoalDecomposer(SimpleNamespace(), **vocab.as_kwargs())
    text = dec._build_system_prompt()[0]["text"]
    assert "## Loop Example" not in text
    assert "detect_objects" not in text
    assert "at_position" not in text
    assert "describe_scene" not in text
    # The world's own vocabulary is still fully taught.
    for oracle in sorted(_REAL_ORACLES):
        assert oracle in text
