# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""The go2-SIM keyword ladder must not fabricate strategies on a BYO base world.

Field forensics (2026-07-10, real-robot REPL audit, secondary #3):
``StrategySelector`` has a GO2 keyword ladder gated ONLY behind ``has_base``. But
go2w_real ALSO has a base — so when a decomposed step arrives with an EMPTY strategy
and a keyword matches, the ladder resolves to SIM strategy names / param shapes that
do not match go2w_real:

  - '去/到/navigate' -> skill 'navigate' with {'room': ...}   (RealNavigateSkill wants {x, y})
  - 'look'/'detect'  -> skills that do not exist on go2w_real
  - 'stand'          -> skill 'stand'                          (go2w_real has 'standup')
  - 'walk'/'turn'    -> primitives walk_forward/turn           (go2w_real has none)
  - 'stop'           -> primitive 'stop'                       (go2w_real has a stop SKILL)

The ladder encodes the robot / go2-SIM vocabulary. A BYO world that owns its own
skill names + param schemas must route empty-strategy steps by its OWN registry
(Priority 3), never by the hardcoded sim ladder.

Fix (additive, worlds-untouched-stay-identical): an OPT-OUT constructor flag
``enable_go2_keyword_ladder`` (default True => robot / go2-SIM byte-identical). The
engine sets it False for a world that declares ``disable_keyword_ladder() -> True``
(go2w_real). With the ladder off, empty-strategy steps fall through to the skill-
registry alias match — the world's REAL names — or the loud fallback. Strictly
stricter: it never invents a target this world cannot serve.
"""

from __future__ import annotations

from typing import Any

from zeno.vcli.cognitive.strategy_selector import StrategySelector
from zeno.vcli.cognitive.types import SubGoal


# ---------------------------------------------------------------------------
# Fake skill registries
# ---------------------------------------------------------------------------


class _RegistryMatch:
    def __init__(self, skill_name: str) -> None:
        self.skill_name = skill_name


class _RealRegistry:
    """Stands in for go2w_real's registry — real names + alias match."""

    _NAMES = [
        "navigate", "move_relative", "standup", "liedown", "stop",
        "explore", "stop_explore", "route_via", "stop_route",
        "bringup", "resume",
    ]
    # Alias -> skill (subset that the tests exercise).
    _ALIASES = {
        "去": "navigate", "到": "navigate", "navigate": "navigate",
        "站起来": "standup", "stand": "standup",
        "往前走": "move_relative", "move forward": "move_relative",
        "停": "stop", "stop": "stop",
    }

    def list_skills(self) -> list[str]:
        return list(self._NAMES)

    def match(self, description: str) -> Any:
        text = description.lower()
        for alias, name in self._ALIASES.items():
            if alias.lower() in text:
                return _RegistryMatch(name)
        return None


def _sub(name: str, desc: str, **kw: Any) -> SubGoal:
    return SubGoal(name=name, description=desc, verify="True", **kw)


# ---------------------------------------------------------------------------
# 1. Default behaviour is UNCHANGED (robot / go2-SIM byte-identical)
# ---------------------------------------------------------------------------


def test_ladder_on_by_default_navigate_room() -> None:
    """A has_base selector with no flag keeps the sim ladder (navigate {room})."""
    sel = StrategySelector(has_base=True)
    res = sel.select(_sub("nav", "navigate to the kitchen"))
    assert res.name == "navigate"
    assert "room" in res.params  # the sim ladder shape


def test_ladder_on_by_default_stand_and_walk() -> None:
    sel = StrategySelector(has_base=True)
    assert sel.select(_sub("s", "stand up")).name == "stand"
    walk = sel.select(_sub("w", "walk forward"))
    assert walk.executor_type == "primitive" and walk.name == "walk_forward"


# ---------------------------------------------------------------------------
# 2. Ladder OFF: no fabricated sim names/params; registry-alias match wins
# ---------------------------------------------------------------------------


def test_ladder_off_navigate_does_not_fabricate_room_param() -> None:
    """With the ladder disabled, 'navigate' must NOT carry a {room} the world rejects."""
    sel = StrategySelector(
        skill_registry=_RealRegistry(),
        has_base=True,
        enable_go2_keyword_ladder=False,
    )
    res = sel.select(_sub("nav", "去 the kitchen"))
    # Routed via registry alias -> the world's real navigate, with NO {room} param.
    assert res.name == "navigate"
    assert "room" not in res.params, (
        "the disabled ladder must not inject a {room} param RealNavigateSkill can't consume"
    )


def test_ladder_off_stand_routes_to_real_standup() -> None:
    """'stand up' must resolve to the world's real 'standup', not the sim 'stand'."""
    sel = StrategySelector(
        skill_registry=_RealRegistry(),
        has_base=True,
        enable_go2_keyword_ladder=False,
    )
    res = sel.select(_sub("s", "站起来"))
    assert res.name == "standup", "must route to the real skill name, not sim 'stand'"


def test_ladder_off_walk_does_not_fabricate_primitive() -> None:
    """'walk forward' must NOT resolve to a walk_forward primitive go2w_real lacks."""
    sel = StrategySelector(
        skill_registry=_RealRegistry(),
        has_base=True,
        enable_go2_keyword_ladder=False,
    )
    res = sel.select(_sub("w", "往前走 2 米"))
    assert res.name != "walk_forward", "no phantom walk_forward primitive on go2w_real"
    assert res.name == "move_relative"  # its real alias route


def test_ladder_off_look_detect_do_not_fabricate_phantom_skills() -> None:
    """'look'/'detect' have no real skill here -> loud fallback, not a phantom skill."""
    sel = StrategySelector(
        skill_registry=_RealRegistry(),
        has_base=True,
        enable_go2_keyword_ladder=False,
    )
    look = sel.select(_sub("o", "look around"))
    assert look.executor_type == "fallback", "no phantom 'look' skill on go2w_real"
    detect = sel.select(_sub("d", "detect the chair"))
    assert detect.executor_type == "fallback", "no phantom 'detect' skill on go2w_real"


def test_ladder_off_still_honours_explicit_strategy() -> None:
    """Disabling the ladder never touches EXPLICIT strategies (Priority 1)."""
    sel = StrategySelector(
        skill_registry=_RealRegistry(),
        has_base=True,
        enable_go2_keyword_ladder=False,
    )
    res = sel.select(_sub("n", "去厨房", strategy="navigate_skill",
                          strategy_params={"x": 2.0, "y": 0.0}))
    assert res.executor_type == "skill" and res.name == "navigate"
    assert res.params == {"x": 2.0, "y": 0.0}


# ---------------------------------------------------------------------------
# 3. World hook + engine wiring
# ---------------------------------------------------------------------------


def test_go2w_real_world_disables_keyword_ladder() -> None:
    from zeno.vcli.worlds.go2w_real import Go2WRealWorld

    world = Go2WRealWorld()
    assert hasattr(world, "disable_keyword_ladder")
    assert world.disable_keyword_ladder() is True


def test_sim_go2w_world_does_not_disable_ladder_byte_identical() -> None:
    """The Isaac (sim) go2w world must NOT gain the opt-out — its ladder stays on."""
    from zeno.vcli.worlds.go2w import IsaacGo2WWorld

    assert not hasattr(IsaacGo2WWorld(), "disable_keyword_ladder")


def test_dev_world_does_not_disable_ladder_byte_identical() -> None:
    from zeno.vcli.worlds.dev import DevWorld

    assert not hasattr(DevWorld(), "disable_keyword_ladder")
