# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Same-process visual capture for the honest visual-acceptance second witness (ADR-002).

The render PRIMITIVE the verdict-emit hook and the (future) ``tools/acceptance`` harness share.
HONESTY CONTRACT: a snapshot can NEVER change the verdict — it is never handed a ``VerdictReport``
(``snapshot_on_verdict`` takes only the agent), and it never raises. It writes a PNG and nothing
else. The frame is rendered from the SAME ``MjModel``/``MjData`` the turn ran on (no second sim).

Heavy deps (cv2, mujoco) load lazily inside ``snapshot`` so importing this module stays cheap.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import numpy as np

# Below this mean pixel brightness a frame is treated as black / unrendered — a fail-closed
# signal the witness must REJECT (nothing actually rendered), never silently accept.
_BLACK_MEAN = 3.0


@dataclass(frozen=True)
class CamSpec:
    """A free third-person ``MjvCamera`` pose (world frame). Defaults frame a go2-room scene."""

    lookat: tuple[float, float, float] = (10.5, 3.0, 0.3)
    azimuth: float = 135.0
    elevation: float = -22.0
    distance: float = 3.2
    width: int = 640
    height: int = 480


def is_black(rgb: np.ndarray, thresh: float = _BLACK_MEAN) -> bool:
    """True if the frame is (near-)black — i.e. nothing rendered. Fail-closed witness signal."""
    return float(np.mean(rgb)) < thresh


def _free_cam(cam_spec: CamSpec):
    import mujoco as mj

    cam = mj.MjvCamera()
    cam.type = mj.mjtCamera.mjCAMERA_FREE
    cam.lookat[:] = list(cam_spec.lookat)
    cam.azimuth = cam_spec.azimuth
    cam.elevation = cam_spec.elevation
    cam.distance = cam_spec.distance
    return cam


def _render(renderer, model, data, cam_spec: CamSpec, path: str, *, forward: bool) -> float:
    """Render ``data`` through ``renderer`` to a BGR PNG; return mean brightness."""
    import cv2
    import mujoco as mj

    if forward:
        mj.mj_forward(model, data)
    renderer.update_scene(data, camera=_free_cam(cam_spec))
    rgb = renderer.render()
    cv2.imwrite(path, rgb[:, :, ::-1])  # RGB -> BGR for OpenCV
    return float(np.mean(rgb))


def snapshot(model, data, cam_spec: CamSpec, path: str) -> float:
    """Render ONE third-person frame of ``(model, data)`` to ``path`` (PNG). Returns mean brightness.

    Standalone/offline primitive: ``mj_forward`` to flush derived quantities, render via a transient
    EGL ``Renderer``, write a BGR PNG, then release the GL context (no leak). May raise (GL/cv2) —
    callers that must stay inert wrap it (see ``snapshot_on_verdict``).
    """
    import mujoco as mj

    renderer = mj.Renderer(model, height=cam_spec.height, width=cam_spec.width)
    try:
        return _render(renderer, model, data, cam_spec, path, forward=True)
    finally:
        try:
            renderer.close()
        except Exception:  # noqa: BLE001 — best-effort GL context release
            pass


def _connected_model_data(base):
    """Pull the live ``(model, data)`` from a connected MuJoCo base, else ``(None, None)``."""
    mjw = getattr(base, "_mj", None)
    if mjw is None:
        return None, None
    return getattr(mjw, "model", None), getattr(mjw, "data", None)


def snapshot_on_verdict(agent) -> str | None:
    """Env-gated, best-effort same-process snapshot for the verdict hook (ADR-002).

    Writes a third-person PNG into ``$VECTOR_SNAPSHOT_DIR`` IFF that env var is set AND a MuJoCo
    sim base is connected on ``agent._base``. Returns the path, or ``None`` if nothing was captured.

    Takes ONLY the agent — it has NO access to the ``VerdictReport`` and so CANNOT change it.
    NEVER raises (every failure, including the render, returns ``None``). The free camera is aimed
    at the robot's own odometry position (framing only — never used to grade, no GT leak).
    """
    out_dir = os.environ.get("VECTOR_SNAPSHOT_DIR")
    if not out_dir:
        return None
    base = getattr(agent, "_base", None)
    if base is None:
        return None
    model, data = _connected_model_data(base)
    if model is None or data is None:
        return None
    try:
        spec = CamSpec()
        pos = base.get_position()
        if pos is not None and len(pos) >= 2:
            spec = CamSpec(lookat=(float(pos[0]), float(pos[1]), 0.3))
        os.makedirs(out_dir, exist_ok=True)
        stamp = os.environ.get("VECTOR_SNAPSHOT_TAG") or str(int(time.time() * 1000))
        path = os.path.join(out_dir, f"verdict_{stamp}.png")
        # Render from an ISOLATED copy of the sim state with a FRESH renderer created on THIS
        # (the verdict-emit) thread. MuJoCo GL contexts are thread-bound and a control/physics
        # thread may still be stepping the LIVE data, so reusing a worker-thread renderer or
        # rendering live data segfaults (cross-thread GL / torn read). Copying qpos into a fresh
        # MjData is race-free; the frame reflects the final pose the verdict was emitted on.
        import mujoco as mj

        data_copy = mj.MjData(model)
        n = min(len(data_copy.qpos), len(data.qpos))
        data_copy.qpos[:n] = np.asarray(data.qpos)[:n]
        snapshot(model, data_copy, spec, path)  # transient renderer (this thread) + forward on copy
        return path
    except Exception:  # noqa: BLE001 — a snapshot must NEVER affect the turn / verdict
        return None
