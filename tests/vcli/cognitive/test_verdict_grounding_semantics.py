# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Verdict grounding semantics — the PREDICATE-ROLE MAP (field fix 2026-07-13).

Field reality (every real-robot go2w_real session, 2026-07-13): the REPL showed
``▸ bringup_skill → verify stack_ready() ✓ (actor=NOT_GRADED)`` and then
``verdict RAN verified=False (0/1 grounded)`` — the verify predicate RAN and
PASSED on a world-served ground-truth oracle (fresh odometry, Inv-1), yet the
turn reported unverified. Root cause: the R1 evidence classifier's bare-call
grounding keyed on a KERNEL-hardcoded ``_PREDICATE_ORACLES`` list (at_position/
facing/...), so a world-registered predicate oracle (``stack_ready``/``at``/
``turned``/...) could NEVER classify GROUNDED — the honest-verify moat read
broken exactly when it worked.

CEO-gated semantics change (Yusen, 2026-07-13) pinned here:

1. PREDICATE-ROLE MAP — a world marks its goal-conditioned bool verify callables
   as predicate oracles (``evidence_classifier.predicate_oracle``); the role set
   is collected from the SAME live namespace as ``oracle_names`` (rule 3, never
   a hand-authored second list) and threaded additively (default ``frozenset()``
   == the old kernel-only behavior, fail-closed).
2. A step whose predicate RAN and passed on a world-served oracle is GROUNDED
   with actor-causation ``NOT_GRADED`` (annotation only). ``UNCAUSED`` still
   downgrades an ACTION step (teleport/no-op strictness preserved) but a
   VERIFY-ONLY step (no action strategy) with a passing predicate is a grounded
   OBSERVATION — it can never mask a failed action step because evidence_passed
   still requires EVERY checked step to ground.
3. verified == all predicates passed on world oracles: N/N grounded => True;
   any failed / never-run predicate still fails the turn.
"""
from __future__ import annotations

from types import SimpleNamespace

from zeno.vcli.cognitive.actor_causation import ActorCaused
from zeno.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from zeno.vcli.verdict import VerdictReport

# The go2w_real live verify namespace names (post-deny) as of 2026-07-13, plus
# the kernel dev predicates that ride along; explored_progress is a STATE oracle
# (float) and must NOT get the predicate role.
_ORACLES = frozenset({
    "at", "moved", "turned", "stack_ready", "route_reached",
    "explore_finished", "explored_progress", "file_exists", "course_locked",
})
_PRED_ROLES = frozenset({
    "at", "moved", "turned", "stack_ready", "route_reached", "explore_finished",
    "course_locked",  # heading-intent (course) alignment — bool predicate
})


def _row(
    name: str,
    verify: str,
    strategy: str,
    verify_result: bool = True,
    actor: ActorCaused = ActorCaused.NOT_GRADED,
) -> tuple[SubGoal, StepRecord]:
    sg = SubGoal(name=name, description=name, verify=verify, strategy=strategy)
    st = StepRecord(
        sub_goal_name=name,
        strategy=strategy,
        success=True,
        verify_result=verify_result,
        duration_sec=0.0,
        actor_caused=actor,
    )
    return sg, st


def _trace(goal: str, rows: list[tuple[SubGoal, StepRecord]]) -> ExecutionTrace:
    tree = GoalTree(goal=goal, sub_goals=tuple(sg for sg, _ in rows))
    return ExecutionTrace(
        goal_tree=tree,
        steps=tuple(st for _, st in rows),
        success=True,
        total_duration_sec=0.0,
    )


# ---------------------------------------------------------------------------
# Field shape 1 — the single bringup step (stack_ready ✓ / actor=NOT_GRADED)
# ---------------------------------------------------------------------------


def test_bringup_stack_ready_passed_not_graded_is_verified_1_of_1() -> None:
    """Today's exact field shape: bringup → verify stack_ready() ✓ (NOT_GRADED)
    must report verified=True (1/1 grounded), never RAN 0/1."""
    trace = _trace("启动导航栈", [_row("bringup", "stack_ready()", "bringup_skill")])
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified is True
    assert report.evidence == "GROUNDED"
    assert (report.n_grounded, report.n_steps) == (1, 1)
    assert report.per_step[0].evidence == "GROUNDED"
    assert report.exit_code() == 0


def test_verdict_still_delegates_to_evidence_passed() -> None:
    """Contract: verified is evidence_passed verbatim under the SAME role map."""
    from zeno.vcli.cognitive.trace_store import evidence_passed

    trace = _trace("启动导航栈", [_row("bringup", "stack_ready()", "bringup_skill")])
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified == evidence_passed(
        trace, _ORACLES, predicate_names=_PRED_ROLES
    )


# ---------------------------------------------------------------------------
# Field shape 2 — a five-step all-green plan reports 5/5
# ---------------------------------------------------------------------------


def _five_rows(fail_at: int | None = None) -> list[tuple[SubGoal, StepRecord]]:
    rows = [
        ("bringup", "stack_ready()", "bringup_skill"),
        ("nav1", "at(3.0, 1.0)", "navigate_skill"),
        ("turn", "turned(54.0)", "turn_skill"),
        ("fwd", "moved(1.5)", "move_relative_skill"),
        ("route", "route_reached()", "route_via_skill"),
    ]
    return [
        _row(n, v, s, verify_result=(i != fail_at))
        for i, (n, v, s) in enumerate(rows)
    ]


def test_five_step_all_green_is_verified_5_of_5() -> None:
    trace = _trace("巡检一圈", _five_rows())
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified is True
    assert report.evidence == "GROUNDED"
    assert (report.n_grounded, report.n_steps) == (5, 5)


def test_one_failed_predicate_fails_the_turn() -> None:
    """Any failed predicate still fails: 4/5 grounded, verified=False, exit 2."""
    trace = _trace("巡检一圈", _five_rows(fail_at=2))
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified is False
    assert report.n_grounded == 4
    assert report.exit_code() == 2


# ---------------------------------------------------------------------------
# Actor-causation stays an annotation; its STRICTNESS is preserved for actions
# ---------------------------------------------------------------------------


def test_verify_only_uncaused_observation_grounds() -> None:
    """A VERIFY-ONLY step (no action strategy) whose predicate passed is a
    grounded OBSERVATION even when graded UNCAUSED (the actor observed world
    truth; it cannot 'cause' a reading)."""
    from zeno.vcli.cognitive.trace_store import classify_step_evidence

    sg, st = _row("check", "stack_ready()", "", actor=ActorCaused.UNCAUSED)
    assert (
        classify_step_evidence(st, sg, _ORACLES, predicate_names=_PRED_ROLES)
        == "GROUNDED"
    )
    trace = _trace("导航栈还开着吗", [(sg, st)])
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified is True


def test_uncaused_action_step_still_downgrades_to_ran() -> None:
    """R2b strictness preserved: an ACTION step graded UNCAUSED (teleport /
    satisfied-at-baseline no-op behind a commanded strategy) stays RAN."""
    from zeno.vcli.cognitive.trace_store import classify_step_evidence

    sg, st = _row("nav", "at(2.0, 0.0)", "navigate_skill", actor=ActorCaused.UNCAUSED)
    assert (
        classify_step_evidence(st, sg, _ORACLES, predicate_names=_PRED_ROLES)
        == "RAN"
    )
    trace = _trace("去 (2,0)", [(sg, st)])
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified is False


def test_observation_never_masks_a_failed_action_step() -> None:
    """A passing UNCAUSED observation must not rescue a turn whose action step's
    predicate FAILED (all checked steps must still ground)."""
    rows = [
        _row("nav", "at(5.0, 5.0)", "navigate_skill", verify_result=False),
        _row("check", "stack_ready()", "", actor=ActorCaused.UNCAUSED),
    ]
    trace = _trace("去 (5,5)", rows)
    report = VerdictReport.from_trace(trace, _ORACLES, predicate_names=_PRED_ROLES)
    assert report.verified is False
    assert report.n_grounded == 1  # the observation grounds; the failed nav never can


# ---------------------------------------------------------------------------
# Fail-closed defaults + role-map discipline (the sandbox gets NO looser)
# ---------------------------------------------------------------------------


def test_default_empty_role_map_is_old_behavior() -> None:
    """Without a predicate-role map the kernel-only classification is byte-
    identical (fail closed): stack_ready() stays RAN, verified=False."""
    trace = _trace("启动导航栈", [_row("bringup", "stack_ready()", "bringup_skill")])
    report = VerdictReport.from_trace(trace, _ORACLES)
    assert report.verified is False
    assert (report.n_grounded, report.n_steps) == (0, 1)


def test_role_map_requires_live_oracle_membership() -> None:
    """A role-mapped name NOT served by the live namespace can never ground
    (the role map may only recognize served oracles, never add one)."""
    from zeno.vcli.cognitive.evidence_classifier import classify_verify_expr

    assert (
        classify_verify_expr("stack_ready()", frozenset(), predicate_names=_PRED_ROLES)
        == "RAN"
    )


def test_role_map_does_not_loosen_structural_guards() -> None:
    """The truthy-constant short-circuit and bare STATE oracles stay RAN with
    the role map applied — predicate evaluation gets NO looser."""
    from zeno.vcli.cognitive.evidence_classifier import classify_verify_expr

    assert (
        classify_verify_expr("stack_ready() or True", _ORACLES, predicate_names=_PRED_ROLES)
        == "RAN"
    )
    assert (
        classify_verify_expr("explored_progress()", _ORACLES, predicate_names=_PRED_ROLES)
        == "RAN"
    )
    # STATE oracle vs constant stays GROUNDED exactly as before.
    assert (
        classify_verify_expr("explored_progress() > 5.0", _ORACLES, predicate_names=_PRED_ROLES)
        == "GROUNDED"
    )


def test_kernel_predicates_unaffected_by_empty_role_map() -> None:
    from zeno.vcli.cognitive.evidence_classifier import classify_verify_expr

    assert (
        classify_verify_expr("at_position(2.0, 0.0)", frozenset({"at_position"}))
        == "GROUNDED"
    )


# ---------------------------------------------------------------------------
# Single-sourcing — the role map comes from the live namespace, never a copy
# ---------------------------------------------------------------------------


def test_go2w_real_world_marks_its_predicate_oracles() -> None:
    """The go2w_real world's bool oracles carry the predicate role; the float
    STATE oracle (explored_progress) does not."""
    from zeno.vcli.cognitive.evidence_classifier import (
        predicate_names_from_namespace,
    )
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    agent = SimpleNamespace(_base=None, _explore=None)
    ns = Go2WRealWorld().build_verify_namespace(agent)
    marked = predicate_names_from_namespace(ns)
    assert marked == _PRED_ROLES
    assert "explored_progress" not in marked


def test_verify_predicate_names_reads_the_live_namespace() -> None:
    """verify_predicate_names mirrors verify_oracle_names: same namespace
    builder, marked names only, fail-closed to empty."""
    from zeno.vcli.cognitive.evidence_classifier import predicate_oracle
    from zeno.vcli.cognitive.trace_store import verify_predicate_names

    def _pred() -> bool:
        return True

    def _state() -> float:
        return 1.0

    ns = {"stack_ready": predicate_oracle(_pred), "explored_progress": _state}
    engine = SimpleNamespace(_build_verifier_namespace=lambda agent: dict(ns))
    assert verify_predicate_names(None, engine) == frozenset({"stack_ready"})
    assert verify_predicate_names(None, None) == frozenset()
