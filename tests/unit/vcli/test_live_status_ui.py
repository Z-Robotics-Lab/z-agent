# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P3.2 live-status UI: one world truth, projected into CLI surfaces only."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

from zeno.vcli import cli


class _LiveWorld:
    def __init__(self, line: str | None) -> None:
        self.line = line
        self.seen_agent = None

    def live_status_line(self, agent):  # noqa: ANN001
        self.seen_agent = agent
        return self.line


def _state(world) -> tuple[dict, object]:  # noqa: ANN001
    agent = object()
    return {"engine": SimpleNamespace(_world=world), "agent": agent}, agent


def test_display_status_reads_active_world_hook_and_flattens() -> None:
    world = _LiveWorld("  pose x=1.25\n y=-0.50   · odom age=0.1s  ")
    state, agent = _state(world)

    assert cli._live_status_for_display(state) == (
        "pose x=1.25 y=-0.50 · odom age=0.1s"
    )
    assert world.seen_agent is agent


def test_display_status_absent_or_broken_is_none() -> None:
    assert cli._live_status_for_display({}) is None
    state, _ = _state(_LiveWorld(None))
    assert cli._live_status_for_display(state) is None

    class _BrokenWorld:
        def live_status_line(self, _agent):  # noqa: ANN001
            raise RuntimeError("sensor failed")

    state, _ = _state(_BrokenWorld())
    assert cli._live_status_for_display(state) is None


def test_toolbar_fragment_escapes_prompt_toolkit_html() -> None:
    state, _ = _state(_LiveWorld("pose <unsafe> & still text"))
    assert cli._live_status_toolbar_fragment(state) == (
        "pose &lt;unsafe&gt; &amp; still text"
    )


def test_main_toolbar_and_native_chain_both_use_live_status_projection() -> None:
    """Pin both UI seams without starting an interactive prompt or a robot."""
    main_src = inspect.getsource(cli.main)
    native_src = inspect.getsource(cli._repl_attempt_native)
    assert "_live_status_toolbar_fragment(app_state)" in main_src
    # P3.11: both seams read the SAME source through the TTL cache wrapper
    # (which delegates to _live_status_for_display) — still single-sourced.
    assert "status_provider=lambda: _live_status_cached(app_state)" in native_src
