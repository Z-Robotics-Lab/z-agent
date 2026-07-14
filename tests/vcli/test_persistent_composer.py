# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P3.7 wiring — persistent composer mode in the REPL (owner ask 2026-07-13).

- Gate: default ON; ZENO_COMPOSER_SYNC in {1,true,on,yes} restores the
  alternating prompt (reversible escape hatch, same pattern as REPL_NATIVE).
- Native turn under a runner: ChainView streams to the transcript (⌂ header
  first, node lines as they complete) and the post-turn duplicate ⌂ tree is
  SKIPPED; pinned step/verdict/card/footer lines unchanged.
"""
from __future__ import annotations

from zeno.vcli import cli
from zeno.vcli.turn_runner import ComposerInterjectQueue, TurnRunner

from tests.vcli.test_chain_view_repl import _EventFakeEngine
from tests.vcli.test_repl_native_cutover import (
    _FakeConsole,
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)


def test_gate_default_on(monkeypatch) -> None:
    monkeypatch.delenv("ZENO_COMPOSER_SYNC", raising=False)
    monkeypatch.delenv("ZENO_COMPOSER_SYNC", raising=False)
    assert cli._persistent_composer_enabled() is True


def test_gate_escape_hatch(monkeypatch) -> None:
    monkeypatch.setenv("ZENO_COMPOSER_SYNC", "1")
    assert cli._persistent_composer_enabled() is False


def test_native_turn_streams_tree_and_skips_duplicate(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    engine = _EventFakeEngine(trace)
    console = _FakeConsole()
    runner = TurnRunner(
        run_turn=lambda _t: None, interject_queue=ComposerInterjectQueue(), echo=lambda _s: None
    )
    app_state: dict = {"turn_runner": runner}

    assert cli._repl_attempt_native(engine, "走到坐标 (11,3)", _FakeSession(), app_state, console)
    # Streamed: the ⌂ header appears BEFORE the verify/step block…
    tree_idx = next(i for i, l in enumerate(console.lines) if "⌂" in l)
    step_idx = next(i for i, l in enumerate(console.lines) if "→ verify" in l)
    assert tree_idx < step_idx
    # …and exactly ONE ⌂ header (no duplicate post-turn tree).
    assert sum(1 for l in console.lines if "⌂" in l) == 1
    # Pinned lines unchanged.
    assert "verified=True" in console.text and "grounded)" in console.text
