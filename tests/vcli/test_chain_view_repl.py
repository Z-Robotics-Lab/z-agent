# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.1 wiring — the REPL native path drives a live ChainView from on_event.

The console.status spinner is replaced by ONE ChainView live region fed by
``engine.run_turn_native(..., on_event=...)``. Additive contract: the fake
engine records the callback (must be callable), events flow into the view,
and every pinned post-turn line (step lines, verdict, card) is unchanged.
"""
from __future__ import annotations

from zeno.vcli import cli
from zeno.vcli.turn_events import NativeEvent

from tests.vcli.test_repl_native_cutover import (
    _FakeConsole,
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)


class _EventFakeEngine:
    """run_turn_native double that exercises the on_event seam."""

    def __init__(self, trace: object) -> None:
        self._vgg_agent = None
        self._trace = trace
        self.received_on_event = "NOT_PASSED"

    def classify_intent(self, text: str):  # noqa: ANN001
        from types import SimpleNamespace

        return SimpleNamespace(use_vgg=True)

    def run_turn_native(
        self, user_message, agent=None, session=None, app_state=None,
        on_progress=None, on_event=None,
    ):  # noqa: ANN001
        self.received_on_event = on_event
        if on_event is not None:
            on_event(NativeEvent(kind="tool_start", label="walk"))
            on_event(NativeEvent(kind="verify", label="at_position(11.0, 3.0)", ok=True))
            on_event(NativeEvent(kind="finish", data={"wall_sec": 1.0, "turns": 1,
                                                      "in_tokens": 10, "out_tokens": 5}))
        return self._trace


def test_repl_passes_on_event_and_turn_completes(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    engine = _EventFakeEngine(trace)
    console = _FakeConsole()

    acted = cli._repl_attempt_native(engine, "走到坐标 (11,3)", _FakeSession(), {}, console)

    assert acted is True
    assert callable(engine.received_on_event), engine.received_on_event
    # Pinned post-turn lines unchanged.
    assert "verify at_position(11.0, 3.0)" in console.text
    assert "verified=True" in console.text
    assert "grounded)" in console.text
