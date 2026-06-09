# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for the in-turn progress controller (vcli.turn_status.TurnStatus).

These cover the spinner/status *controller logic* without a TTY: that the live
region opens and closes exactly once per turn, that pausing for a tool-execution
line stops and restarts the region (so frames never stack), and that the calm
"thinking…" indicator updates in place during the reasoning gap and yields to
streamed text. The literal terminal output is not asserted — a stub live region
records the calls.
"""
from __future__ import annotations

from typing import Any

from vector_os_nano.vcli.turn_status import TurnStatus


class StubLive:
    """Records start/stop/update calls instead of touching a terminal."""

    def __init__(self, renderable: Any) -> None:
        self.initial = renderable
        self.start_calls = 0
        self.stop_calls = 0
        self.updates: list[Any] = []

    def start(self, refresh: bool = False) -> None:
        self.start_calls += 1

    def stop(self) -> None:
        self.stop_calls += 1

    def update(self, renderable: Any, refresh: bool = False) -> None:
        self.updates.append(renderable)


def _make() -> tuple[TurnStatus, list[StubLive], list[tuple[str, float, bool]]]:
    lives: list[StubLive] = []
    rendered: list[tuple[str, float, bool]] = []

    def content(text: str, elapsed: float, is_thinking: bool) -> Any:
        rendered.append((text, elapsed, is_thinking))
        return ("content", text, elapsed, is_thinking)

    def live_factory(renderable: Any) -> StubLive:
        live = StubLive(renderable)
        lives.append(live)
        return live

    return TurnStatus(content, live_factory), lives, rendered


# --------------------------------------------------------------------------
# Lifecycle: one region per turn
# --------------------------------------------------------------------------


def test_start_then_stop_opens_and_closes_exactly_once() -> None:
    status, lives, _ = _make()
    status.start()
    status.stop()
    assert status.start_count == 1
    assert status.stop_count == 1
    assert len(lives) == 1
    assert lives[0].start_calls == 1
    assert lives[0].stop_calls == 1


def test_start_is_idempotent_no_second_region() -> None:
    status, lives, _ = _make()
    status.start()
    status.start()  # no-op while running — must NOT open a second live region
    assert status.start_count == 1
    assert len(lives) == 1
    assert status.running is True


def test_stop_when_not_running_is_noop() -> None:
    status, lives, _ = _make()
    status.stop()
    assert status.stop_count == 0
    assert lives == []


# --------------------------------------------------------------------------
# Pause / resume around a foreign print (the anti-stacking guarantee)
# --------------------------------------------------------------------------


def test_paused_stops_and_restarts_the_region() -> None:
    status, lives, _ = _make()
    status.start()
    with status.paused():
        # Inside the pause the region must be stopped so a tool line prints clean.
        assert status.running is False
    # ...and restarted afterwards.
    assert status.running is True
    # First region stopped, a fresh one started on resume.
    assert status.start_count == 2
    assert status.stop_count == 1
    assert len(lives) == 2
    assert lives[0].stop_calls == 1


def test_paused_when_not_running_does_not_start_a_region() -> None:
    # On the VGG/MCP path no region is active; paused() must be a safe no-op.
    status, lives, _ = _make()
    with status.paused():
        pass
    assert status.running is False
    assert status.start_count == 0
    assert lives == []


def test_many_tool_lines_keep_region_count_balanced() -> None:
    # Simulate a turn with several interleaved tool-execution lines. The region
    # must be stopped once per pause and restarted once per resume — never leaving
    # two live regions stacked.
    status, lives, _ = _make()
    status.start()
    for _ in range(5):
        with status.paused():
            pass  # caller would console.print a tool line here
    status.stop()
    # 1 initial start + 5 resumes = 6 starts; 5 pauses + 1 final stop = 6 stops.
    assert status.start_count == 6
    assert status.stop_count == 6
    assert status.running is False
    # Every created live region was eventually stopped.
    assert all(live.stop_calls == 1 for live in lives)


# --------------------------------------------------------------------------
# Content: thinking gap vs streamed text
# --------------------------------------------------------------------------


def test_initial_region_renders_thinking() -> None:
    status, lives, rendered = _make()
    status.start()
    # The renderable used to open the region must be in the thinking state.
    assert rendered[0][2] is True  # is_thinking


def test_thinking_bumps_elapsed_in_place_no_new_region() -> None:
    status, lives, rendered = _make()
    status.start()
    status.thinking(2.0)
    status.thinking(5.0)
    # Still one region; updated in place (no new StubLive created).
    assert len(lives) == 1
    assert lives[0].updates  # update() called in place
    # Latest thinking render carries the larger elapsed and is_thinking True.
    last_text, last_elapsed, last_is_thinking = rendered[-1]
    assert last_is_thinking is True
    assert last_elapsed == 5.0


def test_streamed_text_leaves_thinking_state() -> None:
    status, lives, rendered = _make()
    status.start()
    status.update_text("Hello")
    # Once text streams, content is no longer the thinking indicator.
    assert rendered[-1][2] is False  # is_thinking
    assert rendered[-1][0] == "Hello"


def test_thinking_is_noop_after_text_streams() -> None:
    # Guard: a late reasoning heartbeat must not replace the answer with a spinner.
    status, lives, rendered = _make()
    status.start()
    status.update_text("answer ")
    n_before = len(rendered)
    status.thinking(9.0)
    assert len(rendered) == n_before  # no re-render into thinking state
    assert rendered[-1][2] is False


def test_update_text_accumulates() -> None:
    status, lives, rendered = _make()
    status.start()
    status.update_text("foo")
    status.update_text("bar")
    assert rendered[-1][0] == "foobar"
