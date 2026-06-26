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


def _base_pose(base):
    """(x, y, heading) of the connected base, or None — the deterministic pose track (hard channel)."""
    try:
        pos = base.get_position()
        x, y = float(pos[0]), float(pos[1])
    except Exception:  # noqa: BLE001
        return None
    try:
        h = float(base.get_heading())
    except Exception:  # noqa: BLE001
        h = 0.0
    return (x, y, h)


def _render_agent_frame(agent, path: str):
    """Render a same-process third-person frame of ``agent._base`` to ``path`` from an ISOLATED qpos
    copy with a FRESH renderer on the CALLING thread (thread-safe vs the control thread — ADR-002
    tricky Case 11). Returns the base pose ``(x, y, heading)`` (``(0,0,0)`` if unknown), or ``None``
    when there is no connected sim to render. May raise (GL/cv2) — callers wrap for inertness.
    """
    base = getattr(agent, "_base", None)
    if base is None:
        return None
    model, data = _connected_model_data(base)
    if model is None or data is None:
        return None
    import mujoco as mj

    pose = _base_pose(base)
    spec = CamSpec(lookat=(pose[0], pose[1], 0.3)) if pose else CamSpec()
    data_copy = mj.MjData(model)
    n = min(len(data_copy.qpos), len(data.qpos))
    data_copy.qpos[:n] = np.asarray(data.qpos)[:n]
    snapshot(model, data_copy, spec, path)  # transient renderer (this thread) + forward on the copy
    return pose if pose is not None else (0.0, 0.0, 0.0)


def snapshot_on_verdict(agent) -> str | None:
    """Env-gated, best-effort same-process snapshot for the verdict hook (ADR-002 Stage 1).

    Writes a third-person PNG into ``$VECTOR_SNAPSHOT_DIR`` IFF that env var is set AND a MuJoCo sim
    base is connected on ``agent._base``. Returns the path, or ``None`` if nothing was captured.
    Takes ONLY the agent — no access to the ``VerdictReport``, so it CANNOT change it. NEVER raises.
    """
    out_dir = os.environ.get("VECTOR_SNAPSHOT_DIR")
    if not out_dir:
        return None
    try:
        os.makedirs(out_dir, exist_ok=True)
        stamp = os.environ.get("VECTOR_SNAPSHOT_TAG") or str(int(time.time() * 1000))
        path = os.path.join(out_dir, f"verdict_{stamp}.png")
        return path if _render_agent_frame(agent, path) is not None else None
    except Exception:  # noqa: BLE001 — a snapshot must NEVER affect the turn / verdict
        return None


def _strip_enabled() -> bool:
    return os.environ.get("VECTOR_SNAPSHOT_STRIP", "0").strip().lower() in ("1", "true", "on", "yes")


def capture_strip_frame(agent, idx: int) -> str | None:
    """Env-gated per-step TEMPORAL frame (ADR-002 Stage 3) — gated by ``VECTOR_SNAPSHOT_DIR`` AND
    ``VECTOR_SNAPSHOT_STRIP=1`` (off by default; strips add render latency). Renders
    ``frame_{idx}.png`` from the same process AND appends the base pose to ``strip.jsonl`` — the
    deterministic pose track that is the HARD motion channel. Inert: never raises, never grades.
    """
    out_dir = os.environ.get("VECTOR_SNAPSHOT_DIR")
    if not out_dir or not _strip_enabled():
        return None
    try:
        import json

        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"frame_{int(idx):03d}.png")
        pose = _render_agent_frame(agent, path)
        if pose is None:
            return None
        rec = {"idx": int(idx), "path": path, "x": pose[0], "y": pose[1], "heading": pose[2], "t": time.time()}
        with open(os.path.join(out_dir, "strip.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return path
    except Exception:  # noqa: BLE001 — a strip frame must NEVER affect the turn / verdict
        return None


def load_strip(out_dir: str) -> list[dict]:
    """Read the per-step pose manifest (``strip.jsonl``) ordered by step idx. [] on any failure."""
    import json

    recs: list[dict] = []
    try:
        with open(os.path.join(out_dir, "strip.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    except Exception:  # noqa: BLE001
        return []
    return sorted(recs, key=lambda r: r.get("idx", 0))


def _sample_evenly(items: list, k: int) -> list:
    """Down-sample ``items`` to at most ``k``, keeping the first + last and even spacing between."""
    n = len(items)
    if n <= k:
        return items
    idxs = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
    return [items[i] for i in idxs]


def montage(frame_paths: list[str], out_path: str, cols: int = 4, max_frames: int = 12) -> str | None:
    """Tile frames (in order) into one grid image for the temporal VLM judge. Down-samples to
    ``max_frames`` evenly (keeping first+last) so a long turn never produces an oversized image the
    VLM may choke on. None on failure."""
    try:
        import cv2

        frame_paths = _sample_evenly(list(frame_paths), max_frames)
        imgs = [im for im in (cv2.imread(p) for p in frame_paths) if im is not None]
        if not imgs:
            return None
        h, w = imgs[0].shape[:2]
        imgs = [cv2.resize(im, (w, h)) for im in imgs]
        rows = []
        for i in range(0, len(imgs), cols):
            row = imgs[i : i + cols]
            while len(row) < cols:
                row.append(np.zeros_like(imgs[0]))
            rows.append(cv2.hconcat(row))
        cv2.imwrite(out_path, cv2.vconcat(rows))
        return out_path
    except Exception:  # noqa: BLE001
        return None
