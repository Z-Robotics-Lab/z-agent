# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the verdict-time visual snapshot (ADR-002) CANNOT change the verdict.

The same-process capture hook is the first piece of the visual-acceptance second witness.
These tests pin its inertness STRUCTURALLY (it is never handed a VerdictReport) and
BEHAVIOURALLY (env-gated, never raises on adversarial input, the cli wrapper swallows render
failures). The actual render is proven against the real go2 sim in the Stage-1 demo, not here
(unit tests stay GL-free).
"""
from __future__ import annotations

import inspect

import numpy as np

from zeno.acceptance import capture
from zeno.vcli import cli


def test_snapshot_fns_take_no_verdict():
    """Structural inertness: the snapshot entrypoints accept ONLY an agent — there is no
    report/verdict parameter, so they cannot read or mutate the verdict."""
    assert list(inspect.signature(capture.snapshot_on_verdict).parameters) == ["agent"]
    assert list(inspect.signature(cli._safe_verdict_snapshot).parameters) == ["agent"]


def test_env_gated_off_by_default(monkeypatch):
    monkeypatch.delenv("VECTOR_SNAPSHOT_DIR", raising=False)
    # No env var -> no capture, regardless of the agent.
    assert capture.snapshot_on_verdict(object()) is None


def test_no_connected_base_is_noop(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_SNAPSHOT_DIR", str(tmp_path))

    class _NoBase:
        pass

    class _BaseNoMj:
        _base = object()  # a base with no `_mj` (not connected)

    assert capture.snapshot_on_verdict(_NoBase()) is None      # no `_base`
    assert capture.snapshot_on_verdict(_BaseNoMj()) is None    # `_base` but no live sim
    assert not list(tmp_path.iterdir())                        # nothing written


def test_never_raises_on_adversarial_input(monkeypatch, tmp_path):
    monkeypatch.setenv("VECTOR_SNAPSHOT_DIR", str(tmp_path))
    for bad in (None, object(), 123, "x", [], {"_base": 1}):
        assert capture.snapshot_on_verdict(bad) is None


def test_cli_wrapper_swallows_render_error(monkeypatch):
    """_safe_verdict_snapshot must NEVER propagate an exception (defense in depth)."""

    def boom(_agent):
        raise RuntimeError("render exploded")

    monkeypatch.setattr(capture, "snapshot_on_verdict", boom)
    assert cli._safe_verdict_snapshot(object()) is None  # does not raise


def test_is_black_detects_unrendered_frame():
    assert capture.is_black(np.zeros((4, 4, 3), dtype=np.uint8)) is True
    assert capture.is_black(np.full((4, 4, 3), 200, dtype=np.uint8)) is False
