# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""A BYO skill-registry whose ``match()`` raises must NOT be silently swallowed.

Plug-and-play (Inv-4 bring-a-skill): ``IntentRouter.should_use_vgg`` consults
``skill_registry.match(user_message)`` to force a matched command onto the VGG
planning path. ``skill_registry`` is a BYO surface — a bring-a-skill world may
ship its own registry / skills whose ``match`` raises (pathological alias,
overridden matcher, broken metadata). The routing gate caught the raise with a
bare ``except Exception: pass`` — degrading routing to the downstream heuristics
with ZERO signal (the E183 persona silent-swallow vein, on the ROUTE pillar).

This is NOT a verify fail-open (routing is not the verify oracle; the fall-through
semantics stay byte-identical). It is the global coding-style floor: never
silently swallow on a control path. The fix logs a WARNING per swallow; behaviour
is unchanged. These tests pin BOTH: the warning fires, and routing is identical
to the no-registry path.
"""
from __future__ import annotations

import logging

import pytest

from vector_os_nano.vcli.intent_router import IntentRouter


class _RaisingRegistry:
    """A BYO skill registry whose match() raises — the pathological case."""

    def match(self, user_input: str):  # noqa: ANN001, ANN201
        raise RuntimeError("BYO skill registry match blew up")


@pytest.fixture
def router() -> IntentRouter:
    return IntentRouter()


def test_raising_registry_logs_a_warning(router, caplog):
    """A swallowed skill_registry.match failure MUST leave an observable WARNING."""
    with caplog.at_level(logging.WARNING, logger="vector_os_nano.vcli.intent_router"):
        router.should_use_vgg("请给我拿一下东西", skill_registry=_RaisingRegistry())
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "a raising skill_registry.match must log a WARNING, not pass silently"
    assert any("skill_registry" in r.getMessage() for r in warnings)


@pytest.mark.parametrize(
    "msg",
    [
        "去厨房",          # motor command → True via downstream motor check
        "为什么这么慢",     # question → False downstream
        "hello",           # greeting → False downstream
        "巡逻",            # motor pattern → True downstream
    ],
)
def test_routing_identical_to_no_registry_when_match_raises(router, msg):
    """Swallowing must be behaviour-preserving: fall-through == the no-registry path."""
    baseline = router.should_use_vgg(msg)  # no registry → pure heuristics
    with_raise = router.should_use_vgg(msg, skill_registry=_RaisingRegistry())
    assert with_raise == baseline


def test_healthy_registry_does_not_warn(router, caplog):
    """A registry that returns None (no match) must NOT spam a warning."""

    class _NoMatch:
        def match(self, user_input: str):  # noqa: ANN001, ANN201
            return None

    with caplog.at_level(logging.WARNING, logger="vector_os_nano.vcli.intent_router"):
        router.should_use_vgg("hello", skill_registry=_NoMatch())
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
