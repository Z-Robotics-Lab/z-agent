# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P3.7 TurnRunner — the persistent-composer turn executor (owner ask 2026-07-13).

Claude-Code-style contract: submit() returns IMMEDIATELY; the turn runs on a
worker thread; a submit while busy routes to the SAME interject queue the
kernel already polls at its safe boundaries (cancel-and-replace semantics
unchanged); when a turn ends with a queued line pending, the runner starts it
as the next turn automatically. Display-only state: a short activity string
for the composer footer. A crashing turn body must never wedge the runner.
"""
from __future__ import annotations

import threading
import time

from zeno.vcli.interject import interject_pending
from zeno.vcli.turn_runner import ComposerInterjectQueue, TurnRunner


def _wait(pred, timeout=5.0) -> bool:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.005)
    return False


def _make_runner(body, queue=None):
    q = queue if queue is not None else ComposerInterjectQueue()
    echoes: list[str] = []
    runner = TurnRunner(run_turn=body, interject_queue=q, echo=echoes.append)
    return runner, q, echoes


# ---------------------------------------------------------------------------
# ComposerInterjectQueue — the kernel-facing duck type, minus the stdin thread
# ---------------------------------------------------------------------------


def test_queue_satisfies_kernel_protocol_without_stdin_thread() -> None:
    q = ComposerInterjectQueue()
    q.start()  # MUST be a no-op: prompt_toolkit owns stdin in composer mode
    assert q.has_pending() is False
    q.push("回到起点")
    assert interject_pending({"interject": q}) is True
    assert q.pop() == "回到起点"
    assert q.pop() is None
    q.stop()  # no-op, never raises


# ---------------------------------------------------------------------------
# TurnRunner lifecycle
# ---------------------------------------------------------------------------


def test_submit_runs_turn_on_worker_and_returns_immediately() -> None:
    ran = threading.Event()
    started: list[str] = []

    def body(text: str) -> None:
        started.append(text)
        ran.wait(2.0)

    runner, _q, _e = _make_runner(body)
    assert runner.submit("往前走3米") == "started"
    assert runner.busy is True  # returned while the turn is still running
    ran.set()
    assert _wait(lambda: not runner.busy)
    assert started == ["往前走3米"]


def test_busy_submit_queues_as_interject_and_echoes() -> None:
    gate = threading.Event()
    runner, q, echoes = _make_runner(lambda _t: gate.wait(2.0))
    runner.submit("第一条")
    assert runner.submit("插队的") == "queued"
    assert q.has_pending() is True  # the kernel's safe-boundary poll sees it
    assert any("插队" in e for e in echoes)
    gate.set()
    assert _wait(lambda: not runner.busy)


def test_queued_line_runs_as_next_turn_when_kernel_left_it() -> None:
    first_gate = threading.Event()
    ran: list[str] = []

    def body(text: str) -> None:
        ran.append(text)
        if len(ran) == 1:
            first_gate.wait(2.0)

    runner, _q, _e = _make_runner(body)
    runner.submit("原目标")
    runner.submit("换个方向")  # queued while busy
    first_gate.set()
    assert _wait(lambda: ran == ["原目标", "换个方向"])
    assert _wait(lambda: not runner.busy)


def test_crashing_turn_never_wedges_the_runner() -> None:
    def body(text: str) -> None:
        raise RuntimeError("turn exploded")

    runner, _q, _e = _make_runner(body)
    runner.submit("x")
    assert _wait(lambda: not runner.busy)
    ran: list[str] = []
    runner._run_turn = ran.append  # type: ignore[attr-defined]
    assert runner.submit("y") == "started"
    assert _wait(lambda: ran == ["y"])


def test_activity_string_for_footer() -> None:
    gate = threading.Event()
    runner, _q, _e = _make_runner(lambda _t: gate.wait(2.0))
    assert runner.activity == ""
    runner.submit("走")
    runner.set_activity("thinking 3s")
    assert runner.activity == "thinking 3s"
    gate.set()
    assert _wait(lambda: not runner.busy)
    assert runner.activity == ""  # cleared when idle


def test_wait_idle_helper() -> None:
    runner, _q, _e = _make_runner(lambda _t: time.sleep(0.05))
    runner.submit("a")
    assert runner.wait_idle(3.0) is True
    assert runner.busy is False
