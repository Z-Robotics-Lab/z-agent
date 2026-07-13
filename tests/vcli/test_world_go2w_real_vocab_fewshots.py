# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real decompose few-shots + self-knowledge (v2 vocab, RED first).

Field traces 2026-07-10..13, bare-zeno REPL on the real Go2W:

1. COMPOUND UTTERANCES lost a clause. "启动导航栈,打开 rviz,站起来" decomposed
   to bringup + standup — the RViz half was silently DROPPED. A compound
   request must become a COMPLETE multi-step plan; no clause vanishes.
2. MOTION-ONLY commands must NOT grow a bringup step. "左转90度" is one
   turn_skill step (odometry already flows) — never gated behind bringup.
3. 掉头 = a single 180° turn_skill step, verified with turned(108) (the wrapped
   heading delta caps at 180°, so the hint is ~60% of the request, not 180).

These pin the few-shots the planner sees (REAL_DECOMPOSE_EXAMPLES) plus the
capability card's self-knowledge (multi-part rule + fast-status note).

Hermetic: pure string/markdown assertions on shipped content — no LLM, no ROS,
no sim.
"""

from __future__ import annotations

from pathlib import Path


def _examples() -> str:
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES

    return REAL_DECOMPOSE_EXAMPLES


def _capabilities_md() -> str:
    import zeno.vcli.worlds.go2w_real as w

    return Path(w.__file__).with_name("go2w_real_capabilities.md").read_text(
        encoding="utf-8")


def _task_segment(text: str, marker: str, span: int = 900) -> str:
    """The slice of REAL_DECOMPOSE_EXAMPLES for the few-shot introduced by
    ``marker``, up to (but not into) the NEXT ``Task:`` block."""
    assert marker in text, f"few-shot {marker!r} missing from the vocab"
    after = text.split(marker, 1)[1]
    nxt = after.find("Task:")
    return after[: nxt if 0 <= nxt <= span else span]


# ---------------------------------------------------------------------------
# (a) Compound utterance -> a COMPLETE multi-step plan (no clause dropped)
# ---------------------------------------------------------------------------


def test_multipart_fewshot_exists_with_all_three_clauses():
    seg = _task_segment(
        _examples(), 'Task: "启动导航栈,打开 rviz,站起来"', span=1400)
    # all three clauses become their OWN step — none silently dropped
    assert "bringup_skill" in seg
    assert "open_viz_skill" in seg
    assert "standup_skill" in seg


def test_multipart_fewshot_has_exactly_three_steps():
    seg = _task_segment(
        _examples(), 'Task: "启动导航栈,打开 rviz,站起来"', span=1400)
    # three sub_goals => three "strategy": entries, one per clause
    assert seg.count('"strategy"') == 3, "compound utterance must be 3 steps"


def test_multipart_fewshot_chains_with_depends_on():
    seg = _task_segment(
        _examples(), 'Task: "启动导航栈,打开 rviz,站起来"', span=1400)
    # the plan is an ordered chain, not three orphan steps
    assert "depends_on" in seg
    assert '"bringup_stack"' in seg  # a later step depends on the bringup step


# ---------------------------------------------------------------------------
# (b) 左转90度 -> ONE turn_skill step, verify turned(54), NO bringup
# ---------------------------------------------------------------------------


def test_turn_left_fewshot_is_one_turn_step_no_bringup():
    seg = _task_segment(_examples(), 'Task: "左转90度"')
    assert "turn_skill" in seg
    assert seg.count('"strategy"') == 1, "左转90度 is a single motion step"
    assert "bringup_skill" not in seg, "motion never needs bringup"


def test_turn_left_fewshot_names_the_turned_54_hint():
    seg = _task_segment(_examples(), 'Task: "左转90度"')
    assert "turned(54)" in seg  # 0.6 * 90 = 54
    assert '"direction": "left"' in seg
    assert '"degrees": 90' in seg


# ---------------------------------------------------------------------------
# (c) 掉头 -> ONE turn_skill step, 180 degrees, verify turned(108)
# ---------------------------------------------------------------------------


def test_uturn_fewshot_is_one_turn_step_180_degrees():
    seg = _task_segment(_examples(), 'Task: "掉头"')
    assert "turn_skill" in seg
    assert seg.count('"strategy"') == 1
    assert '"degrees": 180' in seg
    assert "bringup_skill" not in seg


def test_uturn_fewshot_names_the_turned_108_hint():
    seg = _task_segment(_examples(), 'Task: "掉头"')
    assert "turned(108)" in seg  # 0.6 * 180 = 108


# ---------------------------------------------------------------------------
# Self-knowledge — the capability card documents the operating rules
# ---------------------------------------------------------------------------


def test_capability_md_documents_multipart_rule():
    text = _capabilities_md()
    low = text.lower()
    # the multi-part rule must name the anti-pattern: never drop a clause
    assert "drop" in low, "md must warn against silently dropping a clause"
    assert "启动导航" in text and "rviz" in low, (
        "md must cite the compound-command example (启动导航 + rviz)")


def test_capability_md_documents_fast_status_note():
    low = _capabilities_md().lower()
    # status answers instantly from driver facts when odometry is fresh
    assert "instant" in low or "<1s" in low or "< 1s" in low
    assert "fresh" in low and "odometry" in low
