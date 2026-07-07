# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w decompose-vocab ↔ skill seam — 2026-07-06 live-REPL regression suite.

Two live failures on ``zeno --world go2w`` (see DEBUG.md):

1. "往前走几米" → ``no strategy matched for 'unmatched'`` — the world had no
   relative-movement route at all (only absolute go2w_navigate(x, y)).
2. Same turn, step 2 → ``strategy 'navigate' is not a skill in this world
   (valid: ['explore','navigate','pick'])`` — self-contradictory: the valid
   list names ``navigate`` while the lookup rejects it. Root cause: go2w's
   PARTIAL DecomposeVocab passed ``strategies=frozenset()`` (empty ≠ None)
   into GoalDecomposer, emptying KNOWN_STRATEGIES and the prompt's strategy
   list, so the model improvised bare names that the validator then cleared.

The W1.2-style consistency contract pinned here: EVERY strategy the vocab
teaches must resolve through a real StrategySelector to a skill registered in
THIS world. Offline and LLM-free: the HTTP bridge and wall clock are faked.
"""

from __future__ import annotations

import io
import json
import math
from typing import Any

import pytest

from zeno.vcli.cognitive.goal_decomposer import GoalDecomposer
from zeno.vcli.cognitive.strategy_selector import StrategySelector
from zeno.vcli.cognitive.types import SubGoal
from zeno.vcli.worlds import go2w as go2w_mod
from zeno.vcli.worlds import resolve_world_named


class _FailBackend:
    """LLM backend stand-in — decompose tests here never reach the model."""

    def call(self, **kwargs: Any) -> Any:  # noqa: ANN401
        raise AssertionError("no LLM call expected in this test")


# ---------------------------------------------------------------------------
# Fixtures — fake bridge (pose converges to the last waypoint) + fake clock
# ---------------------------------------------------------------------------


class _FakeResp(io.BytesIO):
    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class _FakeTime:
    """Deterministic stand-in for go2w's ``_time`` module (no real sleeps)."""

    def __init__(self) -> None:
        self._now = 0.0

    def time(self) -> float:
        return self._now

    def sleep(self, seconds: float) -> None:
        self._now += float(seconds)


@pytest.fixture
def fake_bridge(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Bridge stub: records requests; /waypoint teleports pose to the target.

    Instant convergence keeps the blocking drive loops to a couple of (faked)
    sleeps. ``gt`` mirrors ``pose`` (zero SLAM offset).
    """
    waypoints: list[dict[str, float]] = []
    state = {"pose": {"x": 1.0, "y": 2.0, "yaw": math.pi / 2}}

    def _urlopen(url_or_req: Any, *a: Any, **k: Any) -> _FakeResp:
        url = url_or_req if isinstance(url_or_req, str) else url_or_req.full_url
        if url.endswith("/waypoint"):
            body = json.loads(url_or_req.data.decode())
            waypoints.append(body)
            state["pose"] = {"x": body["x"], "y": body["y"],
                             "yaw": state["pose"]["yaw"]}
            return _FakeResp(json.dumps({"ok": True}).encode())
        if url.endswith("/pose") or url.endswith("/gt"):
            return _FakeResp(json.dumps(state["pose"]).encode())
        raise AssertionError(f"unexpected bridge URL: {url}")

    monkeypatch.setattr(go2w_mod.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(go2w_mod, "_time", _FakeTime())
    return {"waypoints": waypoints, "state": state}


def _build_go2w_stack() -> tuple[Any, GoalDecomposer, StrategySelector]:
    """Assemble registry + decomposer + selector exactly as engine.init_vgg does."""
    world = resolve_world_named("go2w")
    registry = world.build_embodiment()._skill_registry
    vocab = world.decompose_vocab()
    assert vocab is not None
    decomposer = GoalDecomposer(
        _FailBackend(), skill_registry=registry, has_base=True, **vocab.as_kwargs()
    )
    selector = StrategySelector(skill_registry=registry, has_base=True)
    return registry, decomposer, selector


# ---------------------------------------------------------------------------
# 1. Consistency contract: every taught strategy resolves to a real skill
# ---------------------------------------------------------------------------


def test_go2w_vocab_teaches_a_nonempty_strategy_set() -> None:
    """The vocab must TEACH strategies — an empty set left the live planner
    improvising bare names that all failed validation (live 2026-07-06)."""
    _, decomposer, _ = _build_go2w_stack()
    assert decomposer.KNOWN_STRATEGIES, (
        "go2w KNOWN_STRATEGIES is empty — the partial DecomposeVocab wiped the "
        "strategy vocabulary (strategies=frozenset() is not None)"
    )


def test_every_taught_strategy_resolves_to_a_registered_skill() -> None:
    """W1.2-style seam contract: vocab-taught strategy → selector → THIS world's
    skill registry. No 'invalid', no 'fallback', no base primitives the go2w
    embodiment does not implement."""
    registry, decomposer, selector = _build_go2w_stack()
    skills = set(registry.list_skills())
    for strategy in sorted(decomposer.KNOWN_STRATEGIES):
        sub_goal = SubGoal(
            name="step", description="step", verify="True", strategy=strategy
        )
        result = selector.select(sub_goal)
        assert result.executor_type == "skill", (
            f"strategy {strategy!r} routed to {result.executor_type!r} — every "
            f"go2w vocab strategy must resolve to a skill in this world"
        )
        assert result.name in skills, (
            f"strategy {strategy!r} resolved to skill {result.name!r} which is "
            f"not registered (valid: {sorted(skills)})"
        )


def test_prompt_advertises_every_known_strategy_and_verify_fn() -> None:
    """The decompose prompt must actually SHOW what the validator accepts —
    live, the KNOWN_STRATEGIES / VERIFY_FUNCTIONS blocks were empty."""
    _, decomposer, _ = _build_go2w_stack()
    prompt = decomposer._build_system_prompt()[0]["text"]
    for strategy in decomposer.KNOWN_STRATEGIES:
        assert strategy in prompt, f"strategy {strategy!r} missing from prompt"
    for fn in ("go2w_at", "explored_volume", "holding_object"):
        assert fn in prompt, f"verify fn {fn!r} missing from prompt"


def test_vocab_strategies_match_registry_exactly() -> None:
    """Drift tripwire both ways: vocab teaches {<skill>_skill} for exactly the
    registered skills — adding/removing a skill without updating the vocab (or
    vice versa) fails here."""
    registry, decomposer, _ = _build_go2w_stack()
    expected = {f"{name}_skill" for name in registry.list_skills()}
    assert decomposer.KNOWN_STRATEGIES == frozenset(expected)


# ---------------------------------------------------------------------------
# 2. Bare-name normalization — the "'navigate' is not a skill (valid:
#    [...'navigate'...])" self-contradiction
# ---------------------------------------------------------------------------


def test_bare_navigate_strategy_normalizes_to_navigate_skill() -> None:
    """An LLM that drops the ``_skill`` suffix (the executor's own error message
    lists BARE registry names as 'valid', actively teaching that form on
    replan) must be normalized, not cleared."""
    _, decomposer, selector = _build_go2w_stack()
    sub_goal = decomposer._validate_sub_goal(
        {
            "name": "goto",
            "description": "导航到 (2.0, 3.0)",
            "verify": "go2w_at(2.0, 3.0)",
            "strategy": "navigate",
            "strategy_params": {"x": 2.0, "y": 3.0},
        },
        valid_names={"goto"},
    )
    assert sub_goal is not None
    assert sub_goal.strategy == "navigate_skill", (
        f"bare 'navigate' must normalize to 'navigate_skill', got "
        f"{sub_goal.strategy!r} (cleared={sub_goal.cleared_strategy!r})"
    )
    assert sub_goal.cleared_strategy == ""
    result = selector.select(sub_goal)
    assert (result.executor_type, result.name) == ("skill", "navigate")
    assert result.params == {"x": 2.0, "y": 3.0}


def test_genuine_hallucination_still_fails_loud() -> None:
    """Normalization must NOT weaken rule-8 fail-loud: a phantom strategy is
    still cleared and routed to the selector's 'invalid' path."""
    _, decomposer, selector = _build_go2w_stack()
    sub_goal = decomposer._validate_sub_goal(
        {
            "name": "p",
            "description": "巡逻",
            "verify": "True",
            "strategy": "patrol",
            "strategy_params": {},
        },
        valid_names={"p"},
    )
    assert sub_goal is not None
    assert sub_goal.strategy == ""
    assert sub_goal.cleared_strategy == "patrol"
    assert selector.select(sub_goal).executor_type == "invalid"


# ---------------------------------------------------------------------------
# 3. move_relative — the missing relative-movement route ("往前走几米")
# ---------------------------------------------------------------------------


def test_move_relative_is_registered_and_taught() -> None:
    registry, decomposer, selector = _build_go2w_stack()
    assert "move_relative" in registry.list_skills()
    assert "move_relative_skill" in decomposer.KNOWN_STRATEGIES
    result = selector.select(
        SubGoal(name="s", description="s", verify="True",
                strategy="move_relative_skill",
                strategy_params={"distance": 2.0, "direction": "forward"})
    )
    assert (result.executor_type, result.name) == ("skill", "move_relative")


def test_move_relative_alias_matches_chinese_relative_phrases() -> None:
    """'往前走几米' / '前进两米' must alias-match move_relative (the live phrase
    matched nothing: no keyword-ladder hit, no alias hit → 'unmatched')."""
    registry, _, _ = _build_go2w_stack()
    for phrase in ("往前走几米", "前进两米", "向前走 3 米"):
        match = registry.match(phrase)
        assert match is not None, f"{phrase!r} must alias-match a skill"
        assert match.skill_name == "move_relative", (
            f"{phrase!r} matched {match.skill_name!r}, expected move_relative"
        )


def test_move_relative_forward_computes_map_target_from_yaw(
    fake_bridge: dict[str, Any],
) -> None:
    """pose (1, 2, yaw=π/2) + forward 3 m → waypoint ≈ (1, 5): the skill does
    the heading trig at runtime from the LIVE pose — the planner never has to."""
    skill = go2w_mod.Go2WMoveRelativeSkill()
    result = skill.execute({"distance": 3.0, "direction": "forward"}, None)
    assert result.success, result.error_message
    first = fake_bridge["waypoints"][0]
    assert first["x"] == pytest.approx(1.0, abs=0.05)
    assert first["y"] == pytest.approx(5.0, abs=0.05)
    # The result carries the computed map-frame target for the verify hint.
    assert result.result_data["target_x"] == pytest.approx(1.0, abs=0.05)
    assert result.result_data["target_y"] == pytest.approx(5.0, abs=0.05)


def test_move_relative_backward_and_right(fake_bridge: dict[str, Any]) -> None:
    """backward = yaw+π, right = yaw−π/2 (yaw=π/2 → backward (1,-1), right (3,2))."""
    skill = go2w_mod.Go2WMoveRelativeSkill()
    result = skill.execute({"distance": 3.0, "direction": "backward"}, None)
    assert result.success, result.error_message
    assert fake_bridge["waypoints"][0]["x"] == pytest.approx(1.0, abs=0.05)
    assert fake_bridge["waypoints"][0]["y"] == pytest.approx(-1.0, abs=0.05)

    fake_bridge["state"]["pose"] = {"x": 1.0, "y": 2.0, "yaw": math.pi / 2}
    fake_bridge["waypoints"].clear()
    result = skill.execute({"distance": 2.0, "direction": "right"}, None)
    assert result.success, result.error_message
    assert fake_bridge["waypoints"][0]["x"] == pytest.approx(3.0, abs=0.05)
    assert fake_bridge["waypoints"][0]["y"] == pytest.approx(2.0, abs=0.05)


def test_move_relative_defaults_to_forward_couple_of_meters(
    fake_bridge: dict[str, Any],
) -> None:
    """'往前走几米' carries no numbers: default = forward 2.0 m, never a crash."""
    skill = go2w_mod.Go2WMoveRelativeSkill()
    result = skill.execute({}, None)
    assert result.success, result.error_message
    assert fake_bridge["waypoints"][0]["x"] == pytest.approx(1.0, abs=0.05)
    assert fake_bridge["waypoints"][0]["y"] == pytest.approx(4.0, abs=0.05)


def test_move_relative_rejects_unknown_direction(
    fake_bridge: dict[str, Any],
) -> None:
    """An explicit-but-unknown direction fails LOUD (never guesses forward)."""
    skill = go2w_mod.Go2WMoveRelativeSkill()
    result = skill.execute({"distance": 1.0, "direction": "sideways-ish"}, None)
    assert not result.success
    assert "direction" in (result.error_message or "")
    assert not fake_bridge["waypoints"], "no waypoint may be sent on bad input"


# ---------------------------------------------------------------------------
# 4. Kernel skill-call convention — skill.execute(params, context)
# ---------------------------------------------------------------------------


def test_navigate_skill_accepts_kernel_positional_convention(
    fake_bridge: dict[str, Any],
) -> None:
    """GoalExecutor._execute_skill and SkillWrapperTool both call
    ``skill.execute(params, context)`` positionally; the old
    ``execute(context=None, **kw)`` signature raised TypeError."""
    skill = go2w_mod.Go2WNavigateSkill()
    result = skill.execute({"x": 4.0, "y": 6.0}, None)
    assert result.success, result.error_message
    assert fake_bridge["waypoints"][0] == {"x": 4.0, "y": 6.0}


# ---------------------------------------------------------------------------
# 5. Engine preflight — the `strategies` set is validated, not only the
#    strategy_descriptions keys (go2w's empty descriptions bypassed W1.2)
# ---------------------------------------------------------------------------


def test_preflight_validates_strategies_set_not_only_descriptions() -> None:
    """A vocab whose ``strategies`` set names a phantom ``*_skill`` must fail
    loud at init even when strategy_descriptions is empty."""
    from unittest.mock import MagicMock

    from zeno.vcli.engine import VectorEngine

    engine = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    registry = MagicMock()
    registry.list_skills.return_value = ["navigate", "explore", "pick"]
    selector = StrategySelector(skill_registry=registry, has_base=True)
    vocab_kwargs = {
        "strategies": frozenset({"phantom_skill"}),
        "strategy_descriptions": {},
        "verify_functions": frozenset(),
    }
    with pytest.raises(ValueError, match="phantom_skill"):
        engine._preflight_validate_world(
            vocab_kwargs, selector, {}, "go2w-test", True
        )
