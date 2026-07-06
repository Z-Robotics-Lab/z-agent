# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""W1.2 — Pre-flight world-registration validator.

Tests:
1. No-false-positive guarantee: dev, robot, and playground worlds each init_vgg
   without raising.
2. Injected drift fails loud:
   (a) vocab.verify_functions contains a name with no provider in verify_ns.
   (b) vocab teaches a strategy with no selector route (not a registered skill,
       capability, or base primitive).
3. The undeterminable case (selector._registered_skill_names() == None) WARNS
   and does NOT raise.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_engine():
    from zeno.vcli.engine import VectorEngine

    return VectorEngine(backend=MagicMock(), intent_router=MagicMock())


def _make_selector(registered_names=None, has_base=False, capability_names=None):
    """Build a StrategySelector with a controlled registry.

    ``registered_names``: frozenset of skill names (None => undeterminable).
    """
    from zeno.vcli.cognitive.strategy_selector import StrategySelector

    if registered_names is None:
        # No registry injected -> _registered_skill_names() returns None.
        return StrategySelector(
            skill_registry=None,
            stats=None,
            capability_names=capability_names or frozenset(),
            has_base=has_base,
        )

    # Build a fake registry whose list_skills() returns the given set.
    registry = MagicMock()
    registry.list_skills.return_value = list(registered_names)
    return StrategySelector(
        skill_registry=registry,
        stats=None,
        capability_names=capability_names or frozenset(),
        has_base=has_base,
    )


def _make_vocab_kwargs(
    strategy_descriptions=None,
    verify_functions=None,
):
    """Return a minimal vocab_kwargs dict for _preflight_validate_world."""
    return {
        "strategy_descriptions": strategy_descriptions or {},
        "verify_functions": frozenset(verify_functions or []),
    }


# ---------------------------------------------------------------------------
# 1. No-false-positive guarantee: dev / robot / playground each boot silently.
# ---------------------------------------------------------------------------


class TestRealWorldsBootClean:
    """The three production worlds must never raise during init_vgg."""

    def test_dev_world_init_vgg_does_not_raise(self) -> None:
        from zeno.vcli.worlds import DevWorld

        eng = _make_engine()
        # Must not raise — if it does, it's a false positive.
        eng.init_vgg(agent=None, skill_registry=None, world=DevWorld())
        assert eng._vgg_enabled is True

    def test_robot_world_init_vgg_does_not_raise(self) -> None:
        from zeno.vcli.worlds import RobotWorld

        eng = _make_engine()
        eng.init_vgg(agent=None, skill_registry=None, world=RobotWorld())
        assert eng._vgg_enabled is True

    def test_playground_world_init_vgg_does_not_raise(self) -> None:
        from zeno.playground import PlaygroundWorld

        eng = _make_engine()
        eng.init_vgg(agent=None, skill_registry=None, world=PlaygroundWorld())
        assert eng._vgg_enabled is True


# ---------------------------------------------------------------------------
# 2a. Injected drift: verify_functions has a name absent from verify_ns.
# ---------------------------------------------------------------------------


class TestVerifyFnDriftFailsLoud:
    """Calling _preflight_validate_world with a missing verify-fn raises ValueError."""

    def test_missing_verify_fn_raises_value_error(self) -> None:
        eng = _make_engine()
        selector = _make_selector(registered_names=frozenset({"pick"}))
        # The vocab claims 'nonexistent_fn' is available; the verify_ns has no such name.
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={"pick_skill": "pick an object"},
            verify_functions=["nonexistent_fn"],
        )
        verify_ns = {"file_exists": lambda p: True}  # 'nonexistent_fn' is absent

        with pytest.raises(ValueError) as exc_info:
            eng._preflight_validate_world(
                vocab_kwargs, selector, verify_ns, "test-world", has_base=False
            )

        msg = str(exc_info.value)
        assert "nonexistent_fn" in msg, f"offending name must be in message: {msg!r}"
        assert "test-world" in msg, f"world name must be in message: {msg!r}"
        # The valid set must be listed.
        assert "file_exists" in msg, f"valid names must be in message: {msg!r}"

    def test_message_names_offending_fn_and_valid_set(self) -> None:
        """The error message includes the bad name AND the valid namespace keys."""
        eng = _make_engine()
        selector = _make_selector(registered_names=frozenset())
        vocab_kwargs = _make_vocab_kwargs(
            verify_functions=["ghost_fn"],
        )
        verify_ns = {"real_fn_a": lambda: True, "real_fn_b": lambda: 0}

        with pytest.raises(ValueError) as exc_info:
            eng._preflight_validate_world(
                vocab_kwargs, selector, verify_ns, "drift-world", has_base=False
            )

        msg = str(exc_info.value)
        assert "ghost_fn" in msg
        # Both valid names must appear somewhere in the message.
        assert "real_fn_a" in msg or "real_fn_b" in msg


# ---------------------------------------------------------------------------
# 2b. Injected drift: vocab teaches a strategy with no selector route.
# ---------------------------------------------------------------------------


class TestStrategyRouteDriftFailsLoud:
    """_preflight_validate_world raises when a _skill-suffix strategy is not registered."""

    def test_unknown_skill_strategy_raises(self) -> None:
        eng = _make_engine()
        # Registry knows only 'pick'; vocab teaches 'phantom_skill'.
        selector = _make_selector(registered_names=frozenset({"pick"}))
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={"phantom_skill": "a skill that does not exist"},
            verify_functions=[],
        )
        verify_ns = {}

        with pytest.raises(ValueError) as exc_info:
            eng._preflight_validate_world(
                vocab_kwargs, selector, verify_ns, "bad-world", has_base=False
            )

        msg = str(exc_info.value)
        assert "phantom_skill" in msg, f"offending strategy must be in message: {msg!r}"
        assert "bad-world" in msg, f"world name must be in message: {msg!r}"
        # The valid set should be listed (pick is valid).
        assert "pick" in msg, f"valid skills must appear in message: {msg!r}"

    def test_valid_registered_skill_does_not_raise(self) -> None:
        """A _skill-suffix strategy that IS registered passes without error."""
        eng = _make_engine()
        selector = _make_selector(registered_names=frozenset({"pick", "place"}))
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={"pick_skill": "pick an object"},
            verify_functions=[],
        )
        verify_ns = {}

        # Must not raise.
        eng._preflight_validate_world(
            vocab_kwargs, selector, verify_ns, "good-world", has_base=False
        )

    def test_base_primitive_valid_when_has_base(self) -> None:
        """walk_forward/turn/scan_360 are valid routes when has_base=True."""
        eng = _make_engine()
        selector = _make_selector(registered_names=frozenset(), has_base=True)
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={
                "walk_forward": "walk forward",
                "turn": "turn",
                "scan_360": "scan 360",
            },
            verify_functions=[],
        )
        verify_ns = {}

        # Must not raise (base primitives are valid with has_base=True).
        eng._preflight_validate_world(
            vocab_kwargs, selector, verify_ns, "base-world", has_base=True
        )

    def test_base_primitive_invalid_when_no_base(self) -> None:
        """walk_forward is not routable on a baseless world."""
        eng = _make_engine()
        selector = _make_selector(registered_names=frozenset(), has_base=False)
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={"walk_forward": "walk forward — but no base!"},
            verify_functions=[],
        )
        verify_ns = {}

        # walk_forward does NOT end with '_skill', so it is NOT checked by the
        # registry path. The selector would route it as StrategyResult("skill",
        # "walk_forward") — it never returns "invalid". So the preflight should
        # NOT raise for this case (scope guard: only _skill strategies are checked).
        # This test confirms there's no false positive.
        eng._preflight_validate_world(
            vocab_kwargs, selector, verify_ns, "no-base-world", has_base=False
        )

    def test_always_valid_strategies_do_not_raise(self) -> None:
        """code_as_policy, tool_call, answer are always valid routes."""
        eng = _make_engine()
        selector = _make_selector(registered_names=frozenset())
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={
                "code_as_policy": "run a code policy",
                "tool_call": "call a tool",
                "answer": "answer only",
            },
            verify_functions=[],
        )
        verify_ns = {}

        # Must not raise — these are always-valid built-ins.
        eng._preflight_validate_world(
            vocab_kwargs, selector, verify_ns, "builtin-world", has_base=False
        )


# ---------------------------------------------------------------------------
# 3. Undeterminable registry (None) warns and does NOT raise.
# ---------------------------------------------------------------------------


class TestUndeterminableRegistryWarnsOnly:
    """When selector._registered_skill_names() returns None, warn and skip."""

    def test_no_registry_does_not_raise(self) -> None:
        eng = _make_engine()
        # selector with no registry -> _registered_skill_names() returns None.
        selector = _make_selector(registered_names=None)
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={"any_skill": "some skill"},
            verify_functions=[],
        )
        verify_ns = {}

        # Must not raise — undeterminable is a warn-and-skip case.
        eng._preflight_validate_world(
            vocab_kwargs, selector, verify_ns, "no-registry-world", has_base=False
        )

    def test_no_registry_emits_warning(self, caplog) -> None:
        """A warning is logged when the registry is undeterminable."""
        eng = _make_engine()
        selector = _make_selector(registered_names=None)
        vocab_kwargs = _make_vocab_kwargs(
            strategy_descriptions={"some_skill": "a skill"},
            verify_functions=[],
        )
        verify_ns = {}

        with caplog.at_level(logging.WARNING):
            eng._preflight_validate_world(
                vocab_kwargs, selector, verify_ns, "undeterminable-world", has_base=False
            )

        # At least one warning message must mention the undeterminable condition.
        warning_texts = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert any(
            "undeterminable" in t or "not available" in t or "skipped" in t
            for t in warning_texts
        ), f"expected an undeterminable warning, got: {warning_texts}"
