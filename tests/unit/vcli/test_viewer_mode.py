# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Tests for the platform-aware viewer drive-mode seam (hardware/sim/viewer_mode).

Pure logic — no MuJoCo / no GL — so these run in the canonical suite and pin the
high-level run-mode distinction (macOS pump vs Linux/Windows daemon vs headless).
"""
from zeno.hardware.sim import viewer_mode as vm


class TestResolveViewerDriveMode:
    def test_no_viewer_is_headless_regardless_of_platform(self):
        assert vm.resolve_viewer_drive_mode(False, under_mjpython=True) == vm.HEADLESS
        assert vm.resolve_viewer_drive_mode(False, under_mjpython=False) == vm.HEADLESS

    def test_viewer_under_mjpython_is_main_thread_pump(self):
        # macOS / mjpython: GLFW is main-thread-only -> caller pumps.
        assert vm.resolve_viewer_drive_mode(True, under_mjpython=True) == vm.MAIN_THREAD_PUMP

    def test_viewer_not_under_mjpython_is_background_daemon(self):
        # Linux / Windows window: background daemon is fine (proven path).
        assert vm.resolve_viewer_drive_mode(True, under_mjpython=False) == vm.BACKGROUND_DAEMON

    def test_resolver_uses_live_probe_when_override_omitted(self, monkeypatch):
        monkeypatch.setattr(vm, "running_under_mjpython", lambda: True)
        assert vm.resolve_viewer_drive_mode(True) == vm.MAIN_THREAD_PUMP
        monkeypatch.setattr(vm, "running_under_mjpython", lambda: False)
        assert vm.resolve_viewer_drive_mode(True) == vm.BACKGROUND_DAEMON


class TestUsesBackgroundPhysics:
    def test_only_main_thread_pump_skips_the_daemon(self):
        assert vm.uses_background_physics(vm.MAIN_THREAD_PUMP) is False
        assert vm.uses_background_physics(vm.BACKGROUND_DAEMON) is True
        assert vm.uses_background_physics(vm.HEADLESS) is True


class TestRunningUnderMjpython:
    def test_false_under_plain_python(self):
        # The test runner is plain python, never mjpython.
        assert vm.running_under_mjpython() is False

    def test_true_when_mjpython_marker_present(self, monkeypatch):
        import sys
        import types
        fake_viewer = types.SimpleNamespace(_MJPYTHON=object())
        fake_pkg = types.ModuleType("mujoco")
        fake_pkg.viewer = fake_viewer  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "mujoco", fake_pkg)
        monkeypatch.setitem(sys.modules, "mujoco.viewer", fake_viewer)
        assert vm.running_under_mjpython() is True
