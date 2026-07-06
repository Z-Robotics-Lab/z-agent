# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2a PART A — VerdictReport is built ONLY from the existing evidence gate.

The honest verdict the engine computes — ``evidence_passed(trace,
verify_oracle_names(agent, engine))`` — must escape cli.main as a machine signal
that can ONLY AGREE with that gate, never a second opinion. These tests pin:

(1) CONTRACT: ``VerdictReport.from_trace(trace, oracle).verified`` equals
    ``evidence_passed(trace, oracle)`` for grounded, ran, failed, and empty-oracle
    traces — the machine signal IS the moat, not a re-derivation.
(2) per-step evidence equals ``classify_step_evidence`` for every step.
(3) the exit-code contract: ``verified == (exit_code() == 0)``; RAN -> 2; NO_TRACE -> 1.
(4) the sentinel line round-trips to a dict carrying the contract fields.

Pure kernel logic on deterministic StepRecord/SubGoal — no cli.main, no LLM.
"""
from __future__ import annotations

import json

from zeno.vcli.cognitive.trace_store import (
    classify_step_evidence,
    evidence_passed,
)
from zeno.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from zeno.vcli.verdict import (
    EVIDENCE_FAILED,
    EVIDENCE_GROUNDED,
    EVIDENCE_NO_TRACE,
    EVIDENCE_RAN,
    LEGACY_VERDICT_SENTINEL,
    VERDICT_SENTINEL,
    VerdictReport,
)

# A robot oracle set including at_position (mirrors verify_oracle_names live keys).
ORACLES = frozenset({"at_position", "facing", "visited", "arm_at_home"})


def _trace(verify: str, success: bool, verify_result: bool, goal: str = "g") -> ExecutionTrace:
    sg = SubGoal(name="s1", description="d", verify=verify, strategy="walk_forward")
    step = StepRecord(
        sub_goal_name="s1",
        strategy="walk_forward",
        success=success,
        verify_result=verify_result,
        duration_sec=0.1,
    )
    tree = GoalTree(goal=goal, sub_goals=(sg,))
    return ExecutionTrace(goal_tree=tree, steps=(step,), success=success, total_duration_sec=0.1)


# ---------------------------------------------------------------------------
# (1) CONTRACT — verified IS evidence_passed, never re-derived
# ---------------------------------------------------------------------------


def test_verdict_matches_evidence_passed_grounded() -> None:
    # A real oracle predicate, true post-state -> GROUNDED -> verified.
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    assert report.verified == evidence_passed(trace, ORACLES)
    assert report.verified is True
    assert report.evidence == EVIDENCE_GROUNDED
    assert report.n_grounded == 1


def test_verdict_matches_evidence_passed_ran_sentinel() -> None:
    # The RED case the spec demands: a "succeeded" step whose verify is the
    # sentinel "True" carries NO grounded evidence -> RAN -> verified False, even
    # though the trace "succeeded".
    trace = _trace("True", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    assert report.verified == evidence_passed(trace, ORACLES)
    assert report.verified is False
    assert report.evidence == EVIDENCE_RAN
    assert report.n_grounded == 0


def test_verdict_matches_evidence_passed_failed() -> None:
    trace = _trace("at_position(2.0, 0.0)", success=False, verify_result=False)
    report = VerdictReport.from_trace(trace, ORACLES)
    assert report.verified == evidence_passed(trace, ORACLES)
    assert report.verified is False
    assert report.evidence == EVIDENCE_FAILED


def test_verdict_matches_evidence_passed_empty_oracle_fails_closed() -> None:
    # Empty oracle set -> every predicate classifies RAN -> verified False
    # (fail closed, moat only stricter).
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, frozenset())
    assert report.verified == evidence_passed(trace, frozenset())
    assert report.verified is False


# ---------------------------------------------------------------------------
# (2) per-step evidence equals classify_step_evidence
# ---------------------------------------------------------------------------


def test_per_step_evidence_equals_classifier() -> None:
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    assert len(report.per_step) == 1
    sg = trace.goal_tree.sub_goals[0]
    step = trace.steps[0]
    assert report.per_step[0].evidence == classify_step_evidence(step, sg, ORACLES)
    assert report.per_step[0].name == "s1"
    assert report.per_step[0].verify == "at_position(2.0, 0.0)"


# ---------------------------------------------------------------------------
# (3) exit-code contract: verified == (exit == 0)
# ---------------------------------------------------------------------------


def test_exit_code_verified_is_zero() -> None:
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    assert report.exit_code() == 0
    assert report.verified == (report.exit_code() == 0)


def test_exit_code_ran_not_verified_is_two() -> None:
    trace = _trace("True", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    assert report.exit_code() == 2
    assert report.verified == (report.exit_code() == 0)


def test_exit_code_no_trace_is_one() -> None:
    report = VerdictReport.no_trace(goal="chat only", error="no trace")
    assert report.evidence == EVIDENCE_NO_TRACE
    assert report.verified is False
    assert report.exit_code() == 1
    assert report.verified == (report.exit_code() == 0)


# ---------------------------------------------------------------------------
# (4) sentinel line round-trips to the contract dict
# ---------------------------------------------------------------------------


def test_sentinel_line_roundtrips() -> None:
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    line = report.to_sentinel_line()
    assert line.startswith(VERDICT_SENTINEL + " ")
    payload = json.loads(line[len(VERDICT_SENTINEL) + 1 :])
    # Contract fields all present.
    for key in (
        "verified", "success", "evidence", "goal",
        "n_steps", "n_grounded", "oracle_names", "per_step",
    ):
        assert key in payload
    assert payload["verified"] is True
    assert payload["goal"] == "g"
    assert isinstance(payload["oracle_names"], list)
    assert isinstance(payload["per_step"], list)
    assert payload["per_step"][0]["evidence"] == "GROUNDED"


# ---------------------------------------------------------------------------
# (4b) sentinel identity transition — D184: ZENO_VERDICT primary,
#      VECTOR_VERDICT dual-emitted legacy alias. The contract is the LITERAL
#      string an external scanner greps, so these pins are literals on purpose.
# ---------------------------------------------------------------------------


def test_sentinel_identity_transition_literals() -> None:
    assert VERDICT_SENTINEL == "ZENO_VERDICT"
    assert LEGACY_VERDICT_SENTINEL == "VECTOR_VERDICT"


def test_sentinel_lines_dual_emit_identical_payload() -> None:
    # Both transition lines carry ONE identical payload: primary FIRST, legacy
    # LAST (a pre-rename consumer splitting the whole stdout on the legacy
    # prefix must see only trailing whitespace after the JSON).
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    lines = report.to_sentinel_lines()
    assert len(lines) == 2
    primary, legacy = lines
    assert primary.startswith("ZENO_VERDICT ")
    assert legacy.startswith("VECTOR_VERDICT ")
    p_payload = json.loads(primary[len("ZENO_VERDICT ") :])
    l_payload = json.loads(legacy[len("VECTOR_VERDICT ") :])
    assert p_payload == l_payload == report.to_dict()
    # to_sentinel_line() stays the PRIMARY line (single-line callers get ZENO).
    assert report.to_sentinel_line() == primary


def test_legacy_scanner_still_matches_dual_emit() -> None:
    # A pre-transition scanner (grep 'VECTOR_VERDICT ' per line) applied to the
    # dual-emitted stdout still finds exactly ONE line and parses the SAME
    # payload — the external contract survives the rename.
    trace = _trace("at_position(2.0, 0.0)", success=True, verify_result=True)
    report = VerdictReport.from_trace(trace, ORACLES)
    stdout = "\n".join(report.to_sentinel_lines()) + "\n"
    matches = [ln for ln in stdout.splitlines() if "VECTOR_VERDICT " in ln]
    assert len(matches) == 1
    payload = json.loads(matches[0].split("VECTOR_VERDICT ", 1)[1])
    assert payload == report.to_dict()


# ---------------------------------------------------------------------------
# (5) DIAGNOSIS — informational per-step failure code, never feeds `verified`
# ---------------------------------------------------------------------------


def _trace_with_step(*, success, verify_result, result_data=None, failure_class=""):
    sg = SubGoal(name="s1", description="d", verify="holding_object('x')", strategy="perception_grasp")
    step = StepRecord(
        sub_goal_name="s1",
        strategy="perception_grasp",
        success=success,
        verify_result=verify_result,
        duration_sec=0.1,
        result_data=result_data or {},
        failure_class=failure_class,
    )
    tree = GoalTree(goal="把瓶子拿过来", sub_goals=(sg,))
    return ExecutionTrace(goal_tree=tree, steps=(step,), success=success, total_duration_sec=0.1)


def test_diagnosis_surfaces_skill_result_data_code() -> None:
    """A failed step's result_data['diagnosis'] reaches StepVerdict.diagnosis."""
    trace = _trace_with_step(success=False, verify_result=False, result_data={"diagnosis": "no_detections"})
    rep = VerdictReport.from_trace(trace, ORACLES)
    assert rep.per_step[0].diagnosis == "no_detections"
    assert rep.to_dict()["per_step"][0]["diagnosis"] == "no_detections"  # serialized on the contract line


def test_diagnosis_prefers_deterministic_failure_class() -> None:
    """The bounded failure_class wins over a raw result_data code."""
    trace = _trace_with_step(
        success=False, verify_result=False, failure_class="ik_fail", result_data={"diagnosis": "low_z"}
    )
    assert VerdictReport.from_trace(trace, ORACLES).per_step[0].diagnosis == "ik_fail"


def test_diagnosis_empty_on_success_and_is_bounded() -> None:
    """A successful step carries no diagnosis; an over-long code is truncated."""
    ok = _trace_with_step(success=True, verify_result=True)
    assert VerdictReport.from_trace(ok, ORACLES).per_step[0].diagnosis == ""
    longcode = "x" * 200
    bad = _trace_with_step(success=False, verify_result=False, result_data={"diagnosis": longcode})
    assert len(VerdictReport.from_trace(bad, ORACLES).per_step[0].diagnosis) <= 64


def test_diagnosis_never_changes_verified() -> None:
    """The moat invariant: adding a diagnosis NEVER flips verified vs evidence_passed."""
    trace = _trace_with_step(success=False, verify_result=False, result_data={"diagnosis": "no_detections"})
    rep = VerdictReport.from_trace(trace, ORACLES)
    assert rep.verified == evidence_passed(trace, ORACLES)
    assert rep.verified is False
