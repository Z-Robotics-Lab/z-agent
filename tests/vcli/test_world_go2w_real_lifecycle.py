# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real lifecycle skill + VGG seam fallback — first-REPL-contact fixes.

Field findings (bare-zeno first contact, 2026-07-10):
1. "启动导航栈" decomposed to standup_skill (no bringup strategy existed) and
   the robot tried to stand with the stack down.
2. VGG's engine-built SkillContext carries no world services — explore/route
   skills reported "No explore manager" despite live managers. Managers must
   also ride the driver (context.base), which BOTH producer paths wire.
"""

from __future__ import annotations

from types import SimpleNamespace


class _FakeHW:
    def __init__(self) -> None:
        self.explore_manager = None
        self.route_manager = None


def _ctx(base=None, services=None):
    return SimpleNamespace(base=base, services=services or {})


# ---------------------------------------------------------------------------
# VGG seam: manager lookup falls back to the driver
# ---------------------------------------------------------------------------


def test_explore_skill_finds_manager_via_driver_fallback():
    from zeno.vcli.worlds.go2w_real_skills import _explore_mgr_of
    hw = _FakeHW()
    hw.explore_manager = object()
    # engine-built context: NO 'explore' service, but base is wired
    assert _explore_mgr_of(_ctx(base=hw)) is hw.explore_manager


def test_route_skill_finds_manager_via_driver_fallback():
    from zeno.vcli.worlds.go2w_real_route_skills import _route_mgr_of
    hw = _FakeHW()
    hw.route_manager = object()
    assert _route_mgr_of(_ctx(base=hw)) is hw.route_manager


def test_services_entry_still_wins_over_driver():
    from zeno.vcli.worlds.go2w_real_skills import _explore_mgr_of
    hw = _FakeHW()
    hw.explore_manager = object()
    svc = object()
    assert _explore_mgr_of(_ctx(base=hw, services={"explore": svc})) is svc


def test_embodiment_attaches_managers_to_driver():
    from zeno.vcli.worlds.go2w_real import Go2WRealEmbodiment
    emb = Go2WRealEmbodiment()
    assert getattr(emb._base, "explore_manager", None) is emb._explore
    assert getattr(emb._base, "route_manager", None) is emb._route


# ---------------------------------------------------------------------------
# bringup skill (the missing "启动导航栈" strategy)
# ---------------------------------------------------------------------------


def _bringup(runner_rc=0, ready=True):
    from zeno.vcli.worlds.go2w_real_lifecycle import RealBringupSkill
    calls: list[list[str]] = []

    def runner(argv, timeout):  # noqa: ARG001
        calls.append(list(argv))
        return SimpleNamespace(returncode=runner_rc, stdout="", stderr="")

    skill = RealBringupSkill(runner=runner, ready_poller=lambda hw, t: ready)
    return skill, calls


def test_bringup_start_runs_nav_sh_and_waits_ready():
    skill, calls = _bringup()
    result = skill.execute({"action": "start"}, _ctx(base=_FakeHW()))
    assert result.success
    assert calls and calls[0][0] == "bash" and calls[0][-1] == "start"


def test_bringup_start_fails_honestly_when_not_ready():
    skill, _ = _bringup(ready=False)
    result = skill.execute({"action": "start"}, _ctx(base=_FakeHW()))
    assert not result.success
    assert "ready" in (result.error_message or "").lower()


def test_bringup_stop_maps_to_nav_sh_stop():
    skill, calls = _bringup()
    result = skill.execute({"action": "stop"}, _ctx(base=_FakeHW()))
    assert result.success
    assert calls[0][-1] == "stop"


def test_bringup_rejects_unknown_action():
    skill, _ = _bringup()
    assert not skill.execute({"action": "fly"}, _ctx(base=_FakeHW())).success


def test_bringup_runner_failure_is_honest():
    skill, _ = _bringup(runner_rc=1)
    assert not skill.execute({"action": "start"}, _ctx(base=_FakeHW())).success


# ---------------------------------------------------------------------------
# vocab: 启动导航栈 routes to bringup, never standup
# ---------------------------------------------------------------------------


def test_vocab_has_bringup_strategy_and_stack_ready_verify():
    from zeno.vcli.worlds import resolve_world_named
    vocab = resolve_world_named("go2w_real").decompose_vocab()
    assert "bringup_skill" in vocab.strategies
    assert "bringup_skill" in vocab.strategy_descriptions
    assert "stack_ready" in vocab.verify_functions


def test_decompose_examples_disambiguate_bringup_from_standup():
    from zeno.vcli.worlds.go2w_real_vocab import REAL_DECOMPOSE_EXAMPLES
    text = REAL_DECOMPOSE_EXAMPLES
    assert "启动导航栈" in text and "bringup_skill" in text
    # the bringup few-shot must NOT route through standup
    seg = text.split("启动导航栈", 1)[1][:220]
    assert "bringup_skill" in seg
    assert "standup_skill" not in seg


def test_stack_ready_predicate_is_fail_safe():
    from zeno.vcli.worlds.go2w_real_verify import make_stack_ready
    fn = make_stack_ready(SimpleNamespace(_base=None))
    assert fn() is False  # no driver -> False, never raises
