# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P0 segfault fix — synchronous skill execution when a viewer is live on mjpython.

MuJoCo mjData and GLFW are not thread-safe, and GLFW is main-thread-ONLY under
mjpython/macOS, where the passive viewer is pumped by the caller/main thread.
engine.vgg_execute_async normally runs skills on a background "vgg-executor"
thread; under mjpython that races the main-thread render and segfaults. The
fix: when a viewer is live AND we run under mjpython, run vgg_execute
SYNCHRONOUSLY on the caller's (viewer-owning) thread. Everywhere else —
headless/dev, and Linux/Windows even WITH a live viewer (their viewer+physics
run on dedicated daemons) — the background thread is kept so the REPL stays
responsive (Test A2).

Pure kernel logic — no real MuJoCo, no real model. vgg_execute is stubbed.
"""
from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from vector_os_nano.vcli.engine import VectorEngine


def _make_engine() -> VectorEngine:
    return VectorEngine(backend=MagicMock(), intent_router=MagicMock())


# ---------------------------------------------------------------------------
# Test A — viewer live UNDER mjpython => synchronous on the caller's thread
# (the macOS GLFW-main-thread constraint; only there must skills run inline)
# ---------------------------------------------------------------------------


def test_viewer_live_under_mjpython_runs_synchronously(monkeypatch) -> None:
    import vector_os_nano.hardware.sim.viewer_mode as vm
    monkeypatch.setattr(vm, "running_under_mjpython", lambda: True)

    eng = _make_engine()
    # Arm hardware with a live (truthy) viewer handle.
    eng._vgg_agent = SimpleNamespace(_arm=SimpleNamespace(_viewer=object()))

    sentinel = object()
    state = {"ran": False, "thread": None}

    def stub_execute(goal_tree: object) -> object:
        state["ran"] = True
        state["thread"] = threading.current_thread()
        return sentinel

    eng.vgg_execute = stub_execute  # type: ignore[method-assign]

    cb_args: list[object] = []

    eng.vgg_execute_async(MagicMock(), on_complete=cb_args.append)

    # Ran synchronously: the stub executed and the callback fired with the
    # sentinel BEFORE vgg_execute_async returned, on the caller's thread.
    assert state["ran"] is True
    assert cb_args == [sentinel]
    assert state["thread"] is threading.current_thread()
    assert eng._vgg_thread is None


# ---------------------------------------------------------------------------
# Test A2 — viewer live but NOT mjpython (Linux/Windows) => background thread.
# On those platforms the viewer + physics run on their own daemons, so the
# skill thread never touches GLFW/mjData; forcing sync-on-main would only
# freeze the REPL (laggy Ctrl-C / "stop") with no safety benefit.
# ---------------------------------------------------------------------------


def test_viewer_live_off_mjpython_runs_in_background_thread(monkeypatch) -> None:
    import vector_os_nano.hardware.sim.viewer_mode as vm
    monkeypatch.setattr(vm, "running_under_mjpython", lambda: False)

    eng = _make_engine()
    eng._vgg_agent = SimpleNamespace(_arm=SimpleNamespace(_viewer=object()))

    done = threading.Event()
    state = {"ran": False, "thread": None}

    def stub_execute(goal_tree: object) -> object:
        state["ran"] = True
        state["thread"] = threading.current_thread()
        return object()

    eng.vgg_execute = stub_execute  # type: ignore[method-assign]

    eng.vgg_execute_async(MagicMock(), on_complete=lambda _t: done.set())

    # Despite a live viewer, on non-mjpython platforms execution is dispatched
    # to the background "vgg-executor" thread so the REPL stays responsive.
    assert isinstance(eng._vgg_thread, threading.Thread)
    eng._vgg_thread.join(timeout=5.0)
    assert done.wait(timeout=5.0)
    assert state["ran"] is True
    assert state["thread"] is not threading.current_thread()


# ---------------------------------------------------------------------------
# Test B — no viewer => background "vgg-executor" thread (CLI stays responsive)
# ---------------------------------------------------------------------------


def test_no_viewer_runs_in_background_thread() -> None:
    eng = _make_engine()
    # Arm present but no viewer; base absent.
    eng._vgg_agent = SimpleNamespace(_arm=SimpleNamespace(_viewer=None))

    done = threading.Event()
    state = {"ran": False}

    def stub_execute(goal_tree: object) -> object:
        state["ran"] = True
        return object()

    eng.vgg_execute = stub_execute  # type: ignore[method-assign]

    cb_calls: list[object] = []

    def cb(trace: object) -> None:
        cb_calls.append(trace)
        done.set()

    eng.vgg_execute_async(MagicMock(), on_complete=cb)

    assert isinstance(eng._vgg_thread, threading.Thread)
    eng._vgg_thread.join(timeout=5.0)
    assert done.wait(timeout=5.0)
    assert state["ran"] is True
    assert len(cb_calls) == 1


# ---------------------------------------------------------------------------
# Test C — _has_live_viewer duck-typing across arm/base, _viewer/viewer attrs
# ---------------------------------------------------------------------------


def test_has_live_viewer_detection() -> None:
    eng = _make_engine()

    # Live arm viewer (_viewer attr).
    eng._vgg_agent = SimpleNamespace(_arm=SimpleNamespace(_viewer=object()))
    assert eng._has_live_viewer() is True

    # Live base viewer (public `viewer` attr).
    eng._vgg_agent = SimpleNamespace(_base=SimpleNamespace(viewer=object()))
    assert eng._has_live_viewer() is True

    # No agent connected.
    eng._vgg_agent = None
    assert eng._has_live_viewer() is False

    # Arm + base present but both viewers None.
    eng._vgg_agent = SimpleNamespace(
        _arm=SimpleNamespace(_viewer=None),
        _base=SimpleNamespace(_viewer=None, viewer=None),
    )
    assert eng._has_live_viewer() is False
