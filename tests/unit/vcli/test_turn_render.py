# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.3 verdict card — pure display renderers (docs/CLI_UX_REDESIGN.md §4 P1.3).

Contract pinned here:
- ``turn_render`` NEVER recomputes verified/evidence — it renders VerdictReport
  fields verbatim (the card contains no second ``verified=`` opinion; that word
  belongs to the existing pinned verdict line printed by cli.py).
- Honest timing display: an unmeasured duration (<= 0) renders as an em dash,
  NEVER as a fabricated "0.0s"; a tiny real one renders "<0.1s".
- Every reachable (evidence, actor, verify_result) combo has a non-empty human
  explanation (the 2026-07-13 predicate-role-map semantics enumeration).
- Explanations attach only to non-GROUNDED rows; an all-GROUNDED report that is
  still verified=False (turn-level gates, e.g. STEP-15/D17 on sim worlds) gets
  the turn-gate fallback explanation.
"""
from __future__ import annotations

import pytest

from zeno.vcli.cognitive.actor_causation import ActorCaused
from zeno.vcli.cognitive.types import ExecutionTrace, GoalTree, StepRecord, SubGoal
from zeno.vcli.turn_render import explain_step, fmt_duration, render_verdict_card
from zeno.vcli.verdict import StepVerdict, VerdictReport


# ---------------------------------------------------------------------------
# fmt_duration — never fabricate a timing
# ---------------------------------------------------------------------------


def test_fmt_duration_unmeasured_is_dash_never_zero() -> None:
    assert fmt_duration(0.0) == "—"
    assert fmt_duration(-3.0) == "—"


def test_fmt_duration_tiny_real_is_lt_marker() -> None:
    assert fmt_duration(0.04) == "<0.1s"


def test_fmt_duration_normal() -> None:
    assert fmt_duration(3.42) == "3.4s"
    assert fmt_duration(61.0) == "61.0s"


# ---------------------------------------------------------------------------
# explain_step — full combo enumeration, honest one-liners
# ---------------------------------------------------------------------------

_COMBOS = [
    ("GROUNDED", "CAUSED", True, "walk", "", "完全验证"),
    ("GROUNDED", "NOT_GRADED", True, "standup", "", "因果评级"),
    ("GROUNDED", "UNCAUSED", True, "", "", "观察"),  # grounded observation (2026-07-13)
    ("RAN", "UNCAUSED", True, "walk", "", "未导致"),  # teleport / no-op downgrade
    ("RAN", "UNCAUSED", False, "", "", "为假"),
    ("RAN", "CAUSED", False, "walk", "", "未确认"),
    ("RAN", "CAUSED", True, "walk", "", "落地证据"),  # not a valid grounding predicate
    ("RAN", "NOT_GRADED", True, "walk", "", "证据"),
    ("RAN", "NOT_GRADED", False, "walk", "", "为假"),
    ("FAILED", "NOT_GRADED", False, "walk", "timeout", "超时"),
    ("FAILED", "CAUSED", False, "walk", "verify_fail", "验证失败"),
]


@pytest.mark.parametrize("evidence,actor,vres,strategy,diag,keyword", _COMBOS)
def test_explain_step_nonempty_for_all_reachable_combos(
    evidence: str, actor: str, vres: bool, strategy: str, diag: str, keyword: str
) -> None:
    text = explain_step(evidence, actor, vres, strategy, diag)
    assert isinstance(text, str) and text.strip(), (evidence, actor, vres)
    assert keyword in text, (evidence, actor, vres, keyword, text)


def test_explain_downgrade_names_the_cause() -> None:
    # Teleport / satisfied-at-baseline behind a commanded action.
    text = explain_step("RAN", "UNCAUSED", True, "walk", "")
    assert "动作" in text and ("未导致" in text or "降级" in text)


def test_explain_grounded_observation() -> None:
    text = explain_step("GROUNDED", "UNCAUSED", True, "", "")
    assert "观察" in text


def test_explain_ungrounded_check_names_evidence_gap() -> None:
    text = explain_step("RAN", "NOT_GRADED", True, "walk", "")
    assert "证据" in text


def test_explain_failed_maps_diagnosis() -> None:
    assert "超时" in explain_step("FAILED", "NOT_GRADED", False, "walk", "timeout")
    assert "工具" in explain_step("FAILED", "NOT_GRADED", False, "walk", "tool_error")


def test_explain_unknown_combo_still_honest_nonempty() -> None:
    # Fail-safe: an unforeseen combo must never render an empty/None cell.
    text = explain_step("RAN", "???", True, "walk", "")
    assert isinstance(text, str) and text.strip()


# ---------------------------------------------------------------------------
# render_verdict_card — pure projection of VerdictReport (+trace metadata)
# ---------------------------------------------------------------------------


def _report(per_step: tuple[StepVerdict, ...], verified: bool) -> VerdictReport:
    n_grounded = sum(1 for s in per_step if s.evidence == "GROUNDED")
    return VerdictReport(
        verified=verified,
        success=True,
        evidence="GROUNDED" if verified else "RAN",
        goal="test goal",
        n_steps=len(per_step),
        n_grounded=n_grounded,
        oracle_names=("turned", "moved"),
        per_step=per_step,
    )


def _trace_for(per_step: tuple[StepVerdict, ...], durations: list[float], actors: list[ActorCaused]) -> ExecutionTrace:
    subs = tuple(
        SubGoal(name=s.name, description="d", verify=s.verify, strategy=s.strategy)
        for s in per_step
    )
    steps = tuple(
        StepRecord(
            sub_goal_name=s.name,
            strategy=s.strategy,
            success=s.success,
            verify_result=s.verify_result,
            duration_sec=durations[i],
            actor_caused=actors[i],
        )
        for i, s in enumerate(per_step)
    )
    return ExecutionTrace(
        goal_tree=GoalTree(goal="test goal", sub_goals=subs),
        steps=steps,
        success=True,
        total_duration_sec=sum(durations),
    )


def _grounded_step(name: str = "native_step_0", strategy: str = "turn") -> StepVerdict:
    return StepVerdict(
        name=name, strategy=strategy, success=True,
        verify="turned(18)", verify_result=True, evidence="GROUNDED",
    )


def _ran_step(name: str = "native_step_1", strategy: str = "walk") -> StepVerdict:
    return StepVerdict(
        name=name, strategy=strategy, success=True,
        verify="moved(2.0)", verify_result=True, evidence="RAN",
    )


def test_card_renders_rows_with_evidence_and_duration() -> None:
    per_step = (_grounded_step(),)
    report = _report(per_step, verified=True)
    trace = _trace_for(per_step, [3.42], [ActorCaused.NOT_GRADED])
    lines = render_verdict_card(report, trace)
    text = "\n".join(lines)
    assert "turn" in text and "turned(18)" in text
    assert "GROUNDED" in text
    assert "NOT_GRADED" in text
    assert "3.4s" in text


def test_card_never_prints_fabricated_zero_seconds() -> None:
    per_step = (_grounded_step(),)
    report = _report(per_step, verified=True)
    trace = _trace_for(per_step, [0.0], [ActorCaused.NOT_GRADED])
    text = "\n".join(render_verdict_card(report, trace))
    assert "0.0s" not in text
    assert "—" in text


def test_card_explains_only_non_grounded_rows() -> None:
    per_step = (_grounded_step(), _ran_step())
    report = _report(per_step, verified=False)
    trace = _trace_for(
        per_step, [1.0, 1.0], [ActorCaused.NOT_GRADED, ActorCaused.UNCAUSED]
    )
    lines = render_verdict_card(report, trace)
    info = [l for l in lines if "ⓘ" in l]
    assert len(info) == 1  # one non-GROUNDED row -> exactly one explanation
    assert "2" in info[0]  # names the step number


def test_card_all_grounded_verified_has_no_info_lines() -> None:
    per_step = (_grounded_step(),)
    report = _report(per_step, verified=True)
    trace = _trace_for(per_step, [1.0], [ActorCaused.NOT_GRADED])
    lines = render_verdict_card(report, trace)
    assert not [l for l in lines if "ⓘ" in l]


def test_card_turn_gate_fallback_when_all_grounded_but_unverified() -> None:
    # Reachable via turn-level gates (STEP-15/D17) on sim worlds: every step
    # GROUNDED yet verified=False. The card must explain at the TURN level and
    # never second-guess the report.
    per_step = (_grounded_step(),)
    report = _report(per_step, verified=False)
    trace = _trace_for(per_step, [1.0], [ActorCaused.CAUSED])
    text = "\n".join(render_verdict_card(report, trace))
    assert "回合级" in text


def test_card_contains_no_second_verified_opinion() -> None:
    per_step = (_grounded_step(), _ran_step())
    report = _report(per_step, verified=False)
    trace = _trace_for(
        per_step, [1.0, 1.0], [ActorCaused.NOT_GRADED, ActorCaused.UNCAUSED]
    )
    text = "\n".join(render_verdict_card(report, trace))
    assert "verified=" not in text  # that word belongs to the pinned verdict line


def test_card_empty_report_renders_nothing() -> None:
    report = VerdictReport.no_trace(goal="g")
    assert render_verdict_card(report, None) == []


def test_card_survives_missing_trace_metadata() -> None:
    # /trace replay or -p callers may lack a live trace: actor/duration degrade
    # to em dashes, the card still renders.
    per_step = (_grounded_step(),)
    report = _report(per_step, verified=True)
    lines = render_verdict_card(report, None)
    text = "\n".join(lines)
    assert "GROUNDED" in text and "—" in text
