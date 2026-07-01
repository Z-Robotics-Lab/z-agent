"""Offline eyes frame for the g1 acceptance: render g1's HEAD camera + the segmentation
GT the oracle uses, to VISUALLY corroborate the moat verdict (red IS in g1's spawn view,
green is NOT). Deterministic — builds a fresh MuJoCoG1 at the same spawn pose the REPL used,
so it does NOT depend on the (torn-down) REPL sim. ONE sim at a time: run only after the
acceptance REPL has exited.

Writes /tmp/g1_accept/eyes/head_rgb.png (what g1 sees) + prints the red/green segmentation
pixel counts (the oracle's INDEPENDENT GT: >MIN_SEG_PX red in view -> GROUNDED-eligible;
~0 green -> refutation).
"""
from __future__ import annotations

import os
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.pop("DISPLAY", None)

import numpy as np
from PIL import Image

import mujoco as mj
from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1, _SCENE_CAM_NAME

OUT = "/tmp/g1_accept/eyes"
os.makedirs(OUT, exist_ok=True)


def _colour_match(rgba, tok):
    r, g, b = float(rgba[0]), float(rgba[1]), float(rgba[2])
    if tok == "red":
        return r > 0.55 and g < 0.5 and b < 0.5
    if tok == "green":
        return g > 0.5 and r < 0.5 and b < 0.5
    return False


sim = MuJoCoG1(gui=False, room=True)
sim.connect()
model, data = sim._model, sim._data
cam_id = model.cam(_SCENE_CAM_NAME).id

# RGB the detector sees
r = mj.Renderer(model, 480, 640)
r.update_scene(data, camera=cam_id)
rgb = r.render()
Image.fromarray(rgb).save(f"{OUT}/head_rgb.png")

# Segmentation GT (per-pixel geom id) — the oracle's independent truth
r.enable_segmentation_rendering()
seg = r.render()
r.disable_segmentation_rendering()
objid = seg[:, :, 0]
for tok in ("red", "green"):
    geoms = [g for g in range(model.ngeom) if _colour_match(model.geom_rgba[g], tok)]
    px = int(np.isin(objid, geoms).sum()) if geoms else 0
    ys, xs = np.where(np.isin(objid, geoms)) if geoms else (np.array([]), np.array([]))
    ctr = (float(xs.mean()), float(ys.mean())) if len(xs) else None
    print(f"[eyes] {tok}: {len(geoms)} geoms, {px} seg px in g1 head-cam view, centroid={ctr}")

r.close()
try:
    sim.disconnect()
except Exception:
    pass
print(f"[eyes] head RGB saved -> {OUT}/head_rgb.png")
