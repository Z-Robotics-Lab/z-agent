# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Platform-aware viewer drive-mode resolution (the high-level run-mode seam).

A MuJoCo passive viewer can be driven three different ways depending on the
platform and whether a window is actually open. This module is the single
high-level seam that distinguishes those run modes, so the sim/hardware and the
REPL never scatter ad-hoc per-platform ``if sys.platform`` branches:

- ``main_thread_pump`` -- macOS under mjpython. Apple GLFW is main-thread-ONLY,
  so a background physics thread may NOT call ``viewer.sync()`` (that is the
  cross-thread GLFW segfault the arm fix 118f886 addressed). The owner of the
  viewer (the REPL / bridge main thread) must drive physics + sync via a pump.
- ``background_daemon`` -- Linux / Windows with a window. GLFW there tolerates a
  background physics thread driving ``mj_step`` + ``viewer.sync()`` (the current,
  proven behavior). The ROS2 nav stack relies on this structure, so it stays
  byte-for-byte unchanged.
- ``headless`` -- no window (any platform). Physics runs on the background
  daemon; nothing ever touches GL.

The mechanism is world-agnostic (it knows nothing about arm vs go2) and
platform-aware (it preserves the Linux/Windows paths exactly; only the
macOS/mjpython windowed path switches to the main-thread pump).
"""
from __future__ import annotations

MAIN_THREAD_PUMP = "main_thread_pump"
BACKGROUND_DAEMON = "background_daemon"
HEADLESS = "headless"


def running_under_mjpython() -> bool:
    """Return True when executing under mjpython (macOS Cocoa main-loop launcher).

    mjpython sets ``mujoco.viewer._MJPYTHON``; under plain python it is absent.
    This is the precise condition under which a passive viewer requires
    main-thread GL access -- more precise than a bare ``sys.platform`` check
    (a macOS process NOT under mjpython has no usable window anyway).
    """
    try:
        import mujoco.viewer as _mjv  # noqa: PLC0415
    except Exception:  # noqa: BLE001 -- mujoco may be absent (headless CI)
        return False
    return getattr(_mjv, "_MJPYTHON", None) is not None


def resolve_viewer_drive_mode(
    has_viewer: bool,
    under_mjpython: bool | None = None,
) -> str:
    """Resolve how a live viewer (if any) must be driven.

    Args:
        has_viewer: whether a passive viewer window is actually open.
        under_mjpython: override the mjpython probe (for tests). When ``None``
            the live :func:`running_under_mjpython` probe is used.

    Returns:
        One of ``MAIN_THREAD_PUMP`` / ``BACKGROUND_DAEMON`` / ``HEADLESS``.
    """
    if not has_viewer:
        return HEADLESS
    if under_mjpython is None:
        under_mjpython = running_under_mjpython()
    return MAIN_THREAD_PUMP if under_mjpython else BACKGROUND_DAEMON


def uses_background_physics(drive_mode: str) -> bool:
    """Return True when physics should run on the background daemon thread.

    Only the macOS main-thread-pump mode drives physics on the caller's thread;
    both the Linux/Windows windowed path and the headless path keep the daemon.
    """
    return drive_mode != MAIN_THREAD_PUMP
