# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P0 segfault fix — synchronous skill execution when a GUI viewer is live.

MuJoCo mjData and GLFW are not thread-safe (GLFW must be touched only on the
main thread on macOS). engine.vgg_execute_async normally runs skills on a
background "vgg-executor" thread, but the passive viewer is created on the
caller/main thread. Concurrent mjData/GLFW access from the worker thread vs the
main-thread render segfaults. The fix: when a viewer is live, run vgg_execute
SYNCHRONOUSLY on the caller's (viewer-owning) thread; keep the background thread
only for the headless/dev path (no viewer).

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
# Test A — viewer live => synchronous execution on the caller's thread
# ---------------------------------------------------------------------------


def test_viewer_live_runs_synchronously() -> None:
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
