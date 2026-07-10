# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Verify-vocab integrity — the kernel must never TEACH or EVALUATE a predicate
the connected world does not serve (field forensics 2026-07-10, go2w_real REPL).

The failure family this pins shut:
  * ``_verify_tool_schema`` hardcoded ``at_position(x, y, tol)`` teaching text
    into EVERY world's verify tool — a phantom predicate on go2w_real (its
    arrival oracle is ``at``). The kernel itself taught the model a name that
    resolves to nothing.
  * ``NativeStepRunner.handle_verify`` evaluated ANY expr; a foreign predicate
    hit a leftover engine stub (``describe_scene``->'' etc.), evaluated falsy,
    and the step graded UNCAUSED/NOT_GRADED -> 'verdict 0/N grounded' with NO
    signal that the predicate was phantom.
  * ``engine._build_verifier_namespace`` unconditionally seeds sim-ish stubs
    BEFORE the world merge; the merge is additive-only so a hardware world
    could never REMOVE them — they leaked into ``verify_oracle_names`` and were
    advertised to the model as live oracles.
  * ``GoalDecomposer._FOREACH_EXAMPLE`` (teaching ``detect_objects()``) was
    appended to EVERY decompose prompt with no world override field.

CEO ruling 2026-07-10: fixes must be ADDITIVE; dev + go2w(sim) stay
byte-identical (no hook / no field set => exact current text + behavior);
verify only ever gets STRICTER (Inv-1). Hermetic: no sim, no ROS, no LLM.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

# Predicate sets shaped like the live worlds (names only — no world import here;
# the go2w_real wiring is pinned in tests/vcli/test_world_go2w_real_vocab_integrity.py).
GO2W_REAL_ORACLES = frozenset(
    {"at", "moved", "explore_finished", "explored_progress", "route_reached", "stack_ready"}
)
SIM_ORACLES = frozenset({"at_position", "facing", "holding_object"})
DEV_ORACLES = frozenset({"file_exists", "grep_count", "path_contains"})


def _schema_desc(names: frozenset[str]) -> str:
    from zeno.vcli.native_loop import _verify_tool_schema

    return _verify_tool_schema(names)["description"]


# ---------------------------------------------------------------------------
# 1. _verify_tool_schema — teach ONLY predicates present in the live oracle set
# ---------------------------------------------------------------------------


def test_schema_never_names_at_position_when_absent() -> None:
    """go2w_real-shaped set: the phantom ``at_position`` must not appear ANYWHERE
    in the description; the arrival-tol teaching binds to the PRESENT ``at``."""
    desc = _schema_desc(GO2W_REAL_ORACLES)
    assert "at_position" not in desc
    # tol semantics are taught for the arrival predicate that IS served.
    assert "at(x, y" in desc
    # The worked example uses a predicate from the live set.
    assert "e.g. at(2.0, 0.0)" in desc


def test_schema_sim_at_position_teaching_stays_byte_identical() -> None:
    """When ``at_position`` IS served (dev/go2w sim suites' worlds), the exact
    pre-fix teaching text is preserved — byte-identical behavior (CEO ruling)."""
    from zeno.vcli.native_loop import _at_position_tol

    tol = _at_position_tol()
    desc = _schema_desc(SIM_ORACLES)
    assert (
        f"at_position(x, y, tol={tol}) is True when the robot's planar position is "
        f"within tol metres of (x, y) (tol defaults to {tol}). "
        "Pass the FULL predicate as 'expr', e.g. at_position(2.0, 0.0)."
    ) in desc


def test_schema_dev_example_names_a_live_predicate() -> None:
    """A world with NEITHER arrival predicate gets an example naming one of ITS
    OWN oracles — never a predicate absent from the set."""
    desc = _schema_desc(DEV_ORACLES)
    assert "at_position" not in desc
    assert "file_exists" in desc  # sorted()[0] of the dev set


def test_schema_empty_set_teaches_nothing() -> None:
    desc = _schema_desc(frozenset())
    assert "at_position" not in desc
    assert "(none)" in desc


# ---------------------------------------------------------------------------
# 2. handle_verify — oracle allowlist (the SAME set the schema advertised)
# ---------------------------------------------------------------------------


class _RecordingVerifier:
    """Fake GoalVerifier that records every expr it is asked to evaluate."""

    def __init__(self, result: bool = True) -> None:
        self.calls: list[str] = []
        self._result = result

    def verify(self, expr: str) -> bool:
        self.calls.append(expr)
        return self._result


def _runner(oracles: frozenset[str]):
    from zeno.vcli.native_loop import NativeStepRunner

    verifier = _RecordingVerifier()
    runner = NativeStepRunner(
        agent=None,
        verifier=verifier,
        oracle_names=oracles,
        motor_tools={},
        tool_context=SimpleNamespace(),
    )
    return runner, verifier


def test_foreign_predicate_is_rejected_with_corrective_error() -> None:
    """A verify calling a name OUTSIDE the live oracle set is REJECTED loudly:
    corrective is_error result naming the allowed predicates (model self-repairs),
    verifier NOT invoked, NO StepRecord minted, latest-verify state untouched."""
    runner, verifier = _runner(GO2W_REAL_ORACLES)
    res = runner.handle_verify("at_position(2.0, 0.0)")
    assert res.is_error is True
    assert "at_position" in res.content  # names the offender
    assert "moved" in res.content and "explore_finished" in res.content  # the fix
    assert verifier.calls == []  # never evaluated against a stub
    assert runner.build_trace("g").steps == ()  # no step recorded
    assert runner.last_verify_result is None  # verify state untouched


def test_in_set_predicate_still_evaluates_and_records_one_step() -> None:
    runner, verifier = _runner(GO2W_REAL_ORACLES)
    res = runner.handle_verify("at(2.0, 0.0)")
    assert res.is_error is False
    assert verifier.calls == ["at(2.0, 0.0)"]
    assert len(runner.build_trace("g").steps) == 1


def test_sandbox_builtins_are_not_gated() -> None:
    """Builtin-safe names (len/str/abs/...) follow the GoalVerifier sandbox rules
    — only PREDICATE call names are gated."""
    runner, verifier = _runner(GO2W_REAL_ORACLES)
    res = runner.handle_verify("len(str(moved(0.1))) > 0")
    assert res.is_error is False
    assert verifier.calls == ["len(str(moved(0.1))) > 0"]


def test_unparseable_expr_falls_through_to_the_sandbox() -> None:
    """Malformed input stays the sandbox's business (its SyntaxError handling is
    the single authority) — the allowlist gate never masks it."""
    runner, verifier = _runner(GO2W_REAL_ORACLES)
    res = runner.handle_verify("at(2.0,")
    assert res.is_error is False  # recorded as a normal (sandbox-graded) verify
    assert verifier.calls == ["at(2.0,"]


def test_run_turn_native_rejected_verify_records_nothing_then_repairs() -> None:
    """Loop-level: a foreign verify yields the corrective tool_result and NO step;
    the model's corrected verify then records the ONLY step of the trace."""
    from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
    from zeno.vcli.native_loop import run_turn_native

    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("verify", {"expr": "at_position(1.0, 2.0)"})),  # phantom
            tool_turn(("verify", {"expr": "moved(0.1)"})),  # self-repair
            tool_turn(("finish", {})),
        ]
    )
    engine = SimpleNamespace(
        _backend=backend,
        _max_tokens=256,
        _build_verifier_namespace=lambda agent: {"moved": lambda min_m=0.1: True},
    )
    trace = run_turn_native(engine, "走一下然后核实", agent=None, session=None)
    assert len(trace.steps) == 1
    assert trace.goal_tree.sub_goals[0].verify == "moved(0.1)"
    assert trace.steps[0].verify_result is True


# ---------------------------------------------------------------------------
# 3. engine._build_verifier_namespace — additive world deny hook (post-merge)
# ---------------------------------------------------------------------------


def _engine():
    from zeno.vcli.engine import VectorEngine

    return VectorEngine(backend=SimpleNamespace())


def _based_agent():
    base = SimpleNamespace(
        get_position=lambda: [0.0, 0.0, 0.0], get_heading=lambda: 0.0
    )
    return SimpleNamespace(_base=base, _arm=None, _spatial_memory=None)


class _DenyWorld:
    name = "deny-test"

    def build_verify_namespace(self, agent):
        return {"at": lambda *a, **k: True}

    def verify_namespace_deny(self):
        return frozenset({"describe_scene", "detect_objects", "get_position"})


class _NoDenyWorld:
    name = "no-deny-test"

    def build_verify_namespace(self, agent):
        return {}


def test_world_deny_hook_removes_stub_names_after_merge() -> None:
    eng = _engine()
    eng._world = _DenyWorld()
    ns = eng._build_verifier_namespace(_based_agent())
    assert "at" in ns  # world contribution survives
    assert "describe_scene" not in ns  # engine stub denied
    assert "detect_objects" not in ns  # engine stub denied
    assert "get_position" not in ns  # base binding denied
    assert "certainty" in ns  # NOT denied -> untouched (remove-only hook)
    assert "get_heading" in ns  # NOT denied -> untouched


def test_absent_deny_hook_is_byte_identical() -> None:
    """A world WITHOUT the hook (dev / go2w sim / robot today) keeps the exact
    current namespace — stubs and all (CEO byte-identical requirement)."""
    eng = _engine()
    eng._world = _NoDenyWorld()
    ns = eng._build_verifier_namespace(_based_agent())
    for stub in ("describe_scene", "detect_objects", "certainty", "get_position"):
        assert stub in ns, f"{stub} must remain without a deny hook"


def test_raising_deny_hook_is_ignored() -> None:
    class _BrokenDeny(_NoDenyWorld):
        def verify_namespace_deny(self):
            raise RuntimeError("boom")

    eng = _engine()
    eng._world = _BrokenDeny()
    ns = eng._build_verifier_namespace(_based_agent())
    assert "describe_scene" in ns  # fail-safe: namespace unchanged


def test_verify_oracle_names_reflects_the_post_deny_set() -> None:
    """The advertised oracle set (schema + allowlist + evidence gate all read it)
    is the POST-deny namespace — all three compose off one source."""
    from zeno.vcli.cognitive.trace_store import verify_oracle_names

    eng = _engine()
    eng._world = _DenyWorld()
    names = verify_oracle_names(_based_agent(), eng)
    assert "at" in names
    assert "describe_scene" not in names
    assert "detect_objects" not in names
    assert "get_position" not in names


# ---------------------------------------------------------------------------
# 4. GoalDecomposer foreach_example — world-overridable loop example
# ---------------------------------------------------------------------------


def _decomposer(**kw):
    from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer

    return GoalDecomposer(SimpleNamespace(), **kw)


def _prompt_text(dec) -> str:
    return dec._build_system_prompt()[0]["text"]


def test_default_foreach_example_stays_byte_identical() -> None:
    """No override (and the explicit None) render the EXACT current prompt."""
    base = _prompt_text(_decomposer())
    assert "## Loop Example" in base
    assert "detect_objects()" in base  # the world-neutral class default
    assert _prompt_text(_decomposer(foreach_example=None)) == base


def test_empty_foreach_example_suppresses_the_loop_section() -> None:
    text = _prompt_text(_decomposer(foreach_example=""))
    assert "## Loop Example" not in text
    assert "## Example" in text  # the rest of the prompt is intact


def test_custom_foreach_example_replaces_the_default() -> None:
    text = _prompt_text(_decomposer(foreach_example="LOOPSHAPE-SENTINEL"))
    assert "## Loop Example" in text
    assert "LOOPSHAPE-SENTINEL" in text
    assert "detect_items" not in text  # the default worked example is gone


def test_decompose_vocab_grows_foreach_example_last_and_defaulted() -> None:
    """Frozen-dataclass discipline (Inv-7): new field LAST, with a default; the
    default flows through as_kwargs as None (= keep the class default)."""
    import dataclasses

    from zeno.vcli.worlds.base import DecomposeVocab

    fields = dataclasses.fields(DecomposeVocab)
    assert fields[-1].name == "foreach_example"
    vocab = DecomposeVocab(planner_intro="i", verify_functions=frozenset({"f"}))
    assert vocab.foreach_example is None
    assert vocab.as_kwargs()["foreach_example"] is None
    # An explicit empty string survives as_kwargs (it means SUPPRESS, not default).
    vocab2 = DecomposeVocab(
        planner_intro="i", verify_functions=frozenset({"f"}), foreach_example=""
    )
    assert vocab2.as_kwargs()["foreach_example"] == ""
