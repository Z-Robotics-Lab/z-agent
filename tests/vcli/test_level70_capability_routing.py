# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 70 — Phase C.2: cross-capability routing by measured fit.

Acceptance criteria (docs/agent-kernel-phase-c-plan.md, C-2):
- a keyword-matched perception/planning step routes to a registered capability
  of that kind (else the classical skill — back-compat);
- two capabilities competing on one sub-goal pattern: after >= 3 attempts
  favouring one, the StrategySelector promotes it via the UNCHANGED get_rankings
  bandit (no stats schema change);
- strategy_stats.json round-trips capability records with the same schema.

Pure kernel logic — no robot, no network, no mujoco fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path

from vector_os_nano.vcli.cognitive.strategy_selector import StrategySelector
from vector_os_nano.vcli.cognitive.strategy_stats import StrategyStats
from vector_os_nano.vcli.cognitive.types import SubGoal


def _sg(name: str, desc: str) -> SubGoal:
    return SubGoal(name=name, description=desc, verify="True", strategy="")


# ---------------------------------------------------------------------------
# Keyword rule becomes capability-aware
# ---------------------------------------------------------------------------


def test_keyword_rule_routes_to_registered_capability() -> None:
    sel = StrategySelector(capability_names={"detect"})
    r = sel.select(_sg("detect_cup", "detect the red cup"))
    assert (r.executor_type, r.name) == ("capability", "detect")


def test_keyword_rule_falls_back_to_skill_without_capability() -> None:
    sel = StrategySelector()  # no capabilities registered
    r = sel.select(_sg("detect_cup", "detect the red cup"))
    assert (r.executor_type, r.name) == ("skill", "detect")  # unchanged behaviour


def test_observe_and_navigate_routes_respect_capabilities() -> None:
    sel = StrategySelector(capability_names={"look", "navigate"})
    assert sel.select(_sg("look_around", "observe the scene")).executor_type == "capability"
    assert sel.select(_sg("go_kitchen", "navigate to the kitchen")).name == "navigate"
    # without the capability, classical skill is preserved
    bare = StrategySelector()
    assert bare.select(_sg("look_around", "observe the scene")).executor_type == "skill"


# ---------------------------------------------------------------------------
# Cross-capability promotion by measured fit (the bandit)
# ---------------------------------------------------------------------------


def test_stats_promote_better_capability_across_kinds() -> None:
    stats = StrategyStats()
    # A second detector capability outperforms the rule default on this pattern.
    for _ in range(4):
        stats.record("yolo_detect", "detect_cup", success=True, duration_sec=0.1)

    sel = StrategySelector(stats=stats, capability_names={"detect", "yolo_detect"})
    r = sel.select(_sg("detect_cup", "detect the red cup"))

    # rule picks the default "detect" capability; stats promote the measured winner
    assert r.executor_type == "capability"
    assert r.name == "yolo_detect"


def test_stats_do_not_promote_below_threshold() -> None:
    stats = StrategyStats()
    # Only 2 attempts (< _STATS_MIN_ATTEMPTS=3) -> no override.
    for _ in range(2):
        stats.record("yolo_detect", "detect_cup", success=True, duration_sec=0.1)

    sel = StrategySelector(stats=stats, capability_names={"detect", "yolo_detect"})
    r = sel.select(_sg("detect_cup", "detect the red cup"))
    assert r.name == "detect"  # rule default, not promoted


def test_stats_promotion_respects_success_rate() -> None:
    stats = StrategyStats()
    # 5 attempts but mostly failures (rate < 0.5) -> no override.
    for ok in (True, False, False, False, False):
        stats.record("yolo_detect", "detect_cup", success=ok, duration_sec=0.1)

    sel = StrategySelector(stats=stats, capability_names={"detect", "yolo_detect"})
    assert sel.select(_sg("detect_cup", "detect the red cup")).name == "detect"


# ---------------------------------------------------------------------------
# Stats schema is unchanged by capability records
# ---------------------------------------------------------------------------


def test_capability_stats_roundtrip_same_schema(tmp_path: Path) -> None:
    path = str(tmp_path / "stats.json")
    s = StrategyStats(persist_path=path)
    s.record("detect", "detect_cup", success=True, duration_sec=0.2)
    s.record("yolo_detect", "detect_cup", success=False, duration_sec=0.3)
    s.save()

    raw = json.loads(Path(path).read_text())
    assert raw  # non-empty
    # exactly the pre-C schema keys — capability records add no new fields
    assert set(raw[0].keys()) == {
        "strategy_name", "sub_goal_pattern", "total_attempts", "successes",
        "total_duration_sec",
    }

    reloaded = StrategyStats(persist_path=path)
    rankings = reloaded.get_rankings("detect_*")
    names = {r.strategy_name for r in rankings}
    assert names == {"detect", "yolo_detect"}
