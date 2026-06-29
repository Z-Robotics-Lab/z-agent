# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""D17 — goal-authenticity for OBJECT (grasp/pick) goals.

The fakeable-grasp false-green: a bare ``vector-cli`` + NL "抓前面的东西" let the model
satisfy a PHYSICAL grasp by ``file_write('grabbed.txt')`` then verifying
``file_exists('grabbed.txt')``. ``file_exists`` is a PREDICATE oracle (classifies
GROUNDED) AND a non-robot predicate (never actor-causation-graded), so every prior gate
failed OPEN and the turn graded GROUNDED — a physical grasp satisfied by touching a file.

These tests pin the turn-level gate (the object-goal analogue of the D15/D16 coordinate
turn gate): a grasp goal grades GROUNDED ONLY when a GT manipulation oracle
(``holding_object`` / ``placed_count``) NECESSARILY gates a GROUNDED step; a fabricated
grasp verified by ``file_exists`` / ``describe_scene`` / ``path_contains`` grades RAN.
Stricter-only (rule 5): real grasp -> GROUNDED, fake grasp -> RAN, every non-grasp turn
(coordinate nav / place-only / dev / g1-detect) UNCHANGED."""
from __future__ import annotations

import pytest

from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused
from vector_os_nano.vcli.cognitive.object_goal import (
    goal_has_object_intent,
    has_necessary_manip_oracle,
)
from vector_os_nano.vcli.cognitive.trace_store import evidence_passed
from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)

# A go2+arm (manipulation) world's live oracle set — ``holding_object`` present.
_ARM_ORACLES = frozenset(
    {
        "holding_object", "at_position", "facing", "arm_at_home", "detect_objects",
        "describe_scene", "placed_count", "file_exists", "path_contains",
    }
)
# A go2-only (coordinate) world — NO arm, so the object-goal gate must never fire.
_GO2_ORACLES = frozenset({"at_position", "facing", "visited", "file_exists", "path_contains"})
# A dev world — code tools only.
_DEV_ORACLES = frozenset({"file_exists", "path_contains"})


# ---------------------------------------------------------------------------
# Pure helpers — intent detection + manipulation-oracle necessity.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "goal, expected",
    [
        ("抓前面的东西", True),
        ("把香蕉抓起来", True),
        ("pick up the banana", True),
        ("grasp the red cube", True),
        ("grab it", True),
        ("拿起杯子", True),
        ("把香蕉抓起来放到盒子里", True),     # pick-and-place still has grasp intent
        # non-grasp goals fail OPEN:
        ("走到坐标 (11,3)", False),
        ("导航到客厅", False),
        ("explore the room", False),
        ("detect the red object", False),
        ("把两个放到盒子里", False),           # place-only, no grasp verb
        ("turn left", False),
        ("", False),
        (None, False),
    ],
)
def test_goal_has_object_intent(goal, expected) -> None:
    assert goal_has_object_intent(goal) is expected


@pytest.mark.parametrize(
    "goal",
    [
        # THE moat hole: the EXACT primary fetch commands the gate failed to fire on.
        "把绿色的瓶子拿过来",
        "把绿色的瓶子拿给我",
        "拿给我那个瓶子",
        "带过来",
        "把那个杯子取过来",
        "去取那个杯子",
        "去把红色杯子拿来",
        "bring me the bottle",
        "give me the cup",
    ],
)
def test_fetch_commands_are_object_intent(goal) -> None:
    """A 拿/带过来/取过来/bring/give-me FETCH commands a physical possession -> must gate (True).

    Before this fix ``_OBJECT_INTENT_RE`` only matched 拿起/拿住, so the primary fetch
    phrasings ("把绿色的瓶子拿过来") slipped the gate — a moat hole an actor could exploit
    by routing a real grasp through a weaker (non-manip) predicate. Stricter-only."""
    assert goal_has_object_intent(goal) is True


@pytest.mark.parametrize(
    "goal",
    [
        # possession-free commands MUST stay False (gate fails open, classification stands).
        "把瓶子放到盒子里",
        "放好",
        "去厨房",
        "place it on the table",
        "go to the kitchen",
        "navigate to the door",
        # OVER-MATCH GUARDS (adversarial review): bare 取/带 used to over-fire on these
        # non-possession compounds, wrongly forcing the holding_object oracle on a
        # nav/perception turn (-> false RED). The directional anchoring must keep them False.
        "读取文件内容",      # 读取 (read) — not a grasp
        "获取传感器数据",    # 获取 (acquire data) — not a grasp
        "获取房间地图",      # perception/mapping — not a grasp
        "取消任务",          # 取消 (cancel) — not a grasp
        "选取区域",          # 选取 (select) — not a grasp
        "带领机器人去客厅",  # 带领 (lead) — pure nav
        "带我去客厅",        # 带我去 (take me to) — pure nav, not object possession
    ],
)
def test_non_possession_commands_not_object_intent(goal) -> None:
    """No grasp/fetch verb -> False (fail-open). Guards against the new verbs over-firing."""
    assert goal_has_object_intent(goal) is False


@pytest.mark.parametrize(
    "expr, expected",
    [
        ("holding_object('banana')", True),
        ("holding_object()", True),
        ("holding_object('banana') and arm_at_home()", True),  # and-conjunct gates
        ("placed_count() == 1", True),                          # place verify gates
        ("not holding_object()", True),                         # release-completion gates
        # NOT a manipulation oracle -> the fabrication vectors:
        ("file_exists('grabbed.txt')", False),
        ("len(describe_scene()) > 0", False),
        ("path_contains('grabbed.txt', 'x')", False),
        ("len(read_file('grabbed.txt')) > 0", False),
        # present-but-not-necessary decoy:
        ("holding_object('banana') or True", False),
        ("at_position(1, 2)", False),
        ("", False),
    ],
)
def test_has_necessary_manip_oracle(expr, expected) -> None:
    assert has_necessary_manip_oracle(expr) is expected


# ---------------------------------------------------------------------------
# Turn-level gate — the un-fakeable contract.
# ---------------------------------------------------------------------------


def _step(name: str, verify: str, strategy: str, actor=ActorCaused.NOT_GRADED, vr=True):
    sg = SubGoal(name=name, description=name, verify=verify, strategy=strategy)
    rec = StepRecord(
        sub_goal_name=name, strategy=strategy, success=True,
        verify_result=vr, duration_sec=0.0, actor_caused=actor,
    )
    return sg, rec


def _trace(goal: str, *steps):
    return ExecutionTrace(
        goal_tree=GoalTree(goal=goal, sub_goals=tuple(s[0] for s in steps)),
        steps=tuple(s[1] for s in steps),
        success=True,
        total_duration_sec=0.0,
    )


def test_fake_grasp_via_file_exists_grades_ran() -> None:
    """THE regression: a "抓" goal verified by file_exists(...) must grade RAN, not GROUNDED."""
    sg, rec = _step("s0", "file_exists('grabbed.txt')", "file_write")
    trace = _trace("抓前面的东西", (sg, rec))
    assert evidence_passed(trace, _ARM_ORACLES) is False


@pytest.mark.parametrize(
    "verify",
    [
        "file_exists('grabbed.txt')",
        "len(describe_scene()) > 0",
        "path_contains('grabbed.txt', 'grabbed')",
    ],
)
def test_fake_grasp_other_self_authored_verifies_grade_ran(verify) -> None:
    sg, rec = _step("s0", verify, "file_write")
    trace = _trace("grab the banana", (sg, rec))
    assert evidence_passed(trace, _ARM_ORACLES) is False


def test_real_grasp_via_holding_object_stays_grounded() -> None:
    """A real perception_grasp -> holding_object weld (CAUSED) must stay GROUNDED."""
    sg, rec = _step("s0", "holding_object('banana')", "perception_grasp", ActorCaused.CAUSED)
    trace = _trace("抓前面的东西", (sg, rec))
    assert evidence_passed(trace, _ARM_ORACLES) is True


@pytest.mark.parametrize(
    "goal, verify, strategy, actor",
    [
        # pick-and-place terminating on placed_count -> honest, stays GROUNDED
        ("把香蕉抓起来放到盒子里", "placed_count() == 1", "place", ActorCaused.NOT_GRADED),
        # pick-and-place terminating on release -> honest, stays GROUNDED
        ("抓起香蕉放下", "not holding_object()", "place", ActorCaused.NOT_GRADED),
        # generic pick proven by holding anything
        ("pick up the cube", "holding_object()", "pick", ActorCaused.CAUSED),
        # grasp + return-home chain
        ("抓香蕉回家", "holding_object('banana') and arm_at_home()", "perception_grasp", ActorCaused.CAUSED),
    ],
)
def test_honest_manipulation_goals_stay_grounded(goal, verify, strategy, actor) -> None:
    sg, rec = _step("s0", verify, strategy, actor)
    trace = _trace(goal, (sg, rec))
    assert evidence_passed(trace, _ARM_ORACLES) is True


@pytest.mark.parametrize(
    "goal, verify, strategy, actor, oracles",
    [
        # place-only goal (no grasp word) — gate fails open, unchanged
        ("把两个放到盒子里", "placed_count() == 2", "place", ActorCaused.NOT_GRADED, _ARM_ORACLES),
        # coordinate nav (go2, no holding_object oracle) — gate never fires
        ("走到坐标 (11,3)", "at_position(11, 3)", "navigate", ActorCaused.CAUSED, _GO2_ORACLES),
        # dev file task — gate never fires (no holding_object oracle)
        ("create out.txt containing ready", "path_contains('out.txt', 'ready')", "file_write", ActorCaused.NOT_GRADED, _DEV_ORACLES),
    ],
)
def test_non_grasp_turns_unchanged(goal, verify, strategy, actor, oracles) -> None:
    sg, rec = _step("s0", verify, strategy, actor)
    trace = _trace(goal, (sg, rec))
    assert evidence_passed(trace, oracles) is True
