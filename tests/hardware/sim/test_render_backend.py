# SPDX-License-Identifier: Apache-2.0
"""reconcile_render_backend: EGL offscreen render and a GLFW passive viewer cannot
coexist in one process — the viewer starves the perception renderer ('Failed to
make the EGL context current'), so fetch/place perceive nothing (verified
2026-07-01: egl+gui=True grasp 0/3, egl+headless 5/5, glfw+gui=True 2/2).

The reconciler is the single policy that keeps them mutually exclusive: a GLFW
viewer opens ONLY when the offscreen backend is glfw (needs a display); otherwise
render headless on egl and DROP the viewer so perception always keeps its context.
It must run BEFORE mujoco is imported (the backend binds at import).
"""
from __future__ import annotations

import sys

import pytest

from vector_os_nano.hardware.sim.go2_inprocess import reconcile_render_backend


def _clear_mujoco(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate "mujoco not yet imported" so the reconciler may bind a backend.
    monkeypatch.delitem(sys.modules, "mujoco", raising=False)


def test_viewer_wanted_with_display_binds_glfw(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mujoco(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("MUJOCO_GL", raising=False)
    eff = reconcile_render_backend(True)
    assert eff is True
    import os
    assert os.environ["MUJOCO_GL"] == "glfw"  # viewer + offscreen renderer coexist


def test_explicit_egl_overridden_to_glfw_when_viewer_wanted(monkeypatch: pytest.MonkeyPatch) -> None:
    # The acceptance wrapper sets MUJOCO_GL=egl by habit; with a display + a viewer
    # request and mujoco not yet imported, egl is incompatible with the window, so
    # the reconciler overrides it to glfw (safe before import).
    _clear_mujoco(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("MUJOCO_GL", "egl")
    eff = reconcile_render_backend(True)
    assert eff is True
    import os
    assert os.environ["MUJOCO_GL"] == "glfw"


def test_headless_request_uses_egl(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mujoco(monkeypatch)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("MUJOCO_GL", raising=False)
    eff = reconcile_render_backend(False)
    assert eff is False
    import os
    assert os.environ.get("MUJOCO_GL", "egl") == "egl"


def test_viewer_wanted_no_display_drops_to_headless_egl(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_mujoco(monkeypatch)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("MUJOCO_GL", raising=False)
    eff = reconcile_render_backend(True)
    assert eff is False  # no display -> no viewer, perception on egl
    import os
    assert os.environ["MUJOCO_GL"] == "egl"


def test_egl_already_bound_suppresses_viewer(monkeypatch: pytest.MonkeyPatch) -> None:
    # mujoco already imported under egl (backend locked) -> a viewer would break
    # perception, so it must be refused even though a display exists.
    monkeypatch.setitem(sys.modules, "mujoco", object())
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("MUJOCO_GL", "egl")
    eff = reconcile_render_backend(True)
    assert eff is False
    import os
    assert os.environ["MUJOCO_GL"] == "egl"  # unchanged; perception protected


def test_glfw_already_bound_allows_viewer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "mujoco", object())
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setenv("MUJOCO_GL", "glfw")
    eff = reconcile_render_backend(True)
    assert eff is True
