"""g1 scene probe — de-risks the honest VLN design (NOT acceptance).

Answers, empirically, the three questions that decide whether a "go to the <colour>
thing" compound is honestly buildable on g1's current scene:
  1. WHERE are the red/green/blue objects (world xy), and which are freejoint
     PICKABLES (navigable-to, not obstacles) vs static FURNITURE (obstacles the
     planner routes AROUND, never INTO)?
  2. WHAT coloured geometry is actually IN g1's head-cam spawn view (segmentation)?
  3. Is each coloured object's xy REACHABLE by the g1_vgraph planner from spawn
     (a target inside an inflated obstacle → planner None → cannot arrive)?

Run ONE sim at a time; `rosm nuke --yes` after. Usage: python g1_scene_probe.py
"""
from __future__ import annotations

import os

os.environ.setdefault("VECTOR_NO_ROS2", "1")
os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.pop("DISPLAY", None)

import numpy as np

from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1, _SCENE_CAM_NAME


def _colour_of(rgba) -> str | None:
    r, g, b = float(rgba[0]), float(rgba[1]), float(rgba[2])
    if r > 0.55 and g < 0.5 and b < 0.5:
        return "red"
    if g > 0.5 and r < 0.5 and b < 0.5:
        return "green"
    if b > 0.55 and r < 0.5 and g < 0.6:
        return "blue"
    return None


def main() -> int:
    import mujoco as mj

    g1 = MuJoCoG1(gui=False, room=True)
    g1.connect()
    model, data = g1._model, g1._data
    spawn = g1.get_position()
    print(f"spawn xyz = {tuple(round(float(v), 2) for v in spawn)}")

    # (1) enumerate coloured geoms: colour, world xyz, static-vs-freejoint body.
    print("\n=== coloured geoms ===")
    coloured: list[tuple[str, str, tuple, bool]] = []
    for gi in range(model.ngeom):
        col = _colour_of(model.geom_rgba[gi])
        if col is None:
            continue
        gname = mj.mj_id2name(model, mj.mjtObj.mjOBJ_GEOM, gi) or f"geom{gi}"
        bid = int(model.geom_bodyid[gi])
        bname = mj.mj_id2name(model, mj.mjtObj.mjOBJ_BODY, bid) or f"body{bid}"
        # freejoint? a body with a free joint has jntadr -> jnt_type == FREE
        is_free = False
        jadr = int(model.body_jntadr[bid])
        jnum = int(model.body_jntnum[bid])
        if jadr >= 0 and jnum > 0:
            for j in range(jadr, jadr + jnum):
                if int(model.jnt_type[j]) == int(mj.mjtJoint.mjJNT_FREE):
                    is_free = True
        wxyz = tuple(round(float(v), 2) for v in data.geom_xpos[gi])
        coloured.append((col, gname, wxyz, is_free))
        print(f"  {col:5s} geom={gname:28s} body={bname:24s} xyz={wxyz} freejoint={is_free}")

    # (2) segmentation: which coloured geoms are in g1 head-cam spawn view.
    print("\n=== head-cam spawn segmentation (in-view coloured geoms) ===")
    cam_id = model.cam(_SCENE_CAM_NAME).id
    r = mj.Renderer(model, 480, 640)
    r.update_scene(data, camera=cam_id)
    r.enable_segmentation_rendering()
    seg = r.render()[:, :, 0]
    r.close()
    for col in ("red", "green", "blue"):
        geoms = [gi for gi in range(model.ngeom) if _colour_of(model.geom_rgba[gi]) == col]
        px = int(np.isin(seg, geoms).sum())
        ys, xs = np.where(np.isin(seg, geoms))
        cen = (round(float(xs.mean()), 0), round(float(ys.mean()), 0)) if len(xs) else None
        print(f"  {col:5s}: {px:6d} seg px  centroid={cen}")

    # (3) planner reachability to each coloured object's xy (target = object xy).
    print("\n=== planner reachability to each coloured object xy ===")
    seen: set = set()
    for col, gname, wxyz, is_free in coloured:
        key = (col, round(wxyz[0], 1), round(wxyz[1], 1))
        if key in seen:
            continue
        seen.add(key)
        tx, ty = wxyz[0], wxyz[1]
        try:
            res = g1.navigate_to(tx, ty)
            pf = g1.get_position()
            d = ((pf[0] - tx) ** 2 + (pf[1] - ty) ** 2) ** 0.5
            print(f"  {col:5s} target=({tx:.2f},{ty:.2f}) free={is_free} -> "
                  f"reached_within={d:.2f}m final={tuple(round(float(v),2) for v in pf[:2])} res={bool(res)}")
        except Exception as e:  # noqa: BLE001
            print(f"  {col:5s} target=({tx:.2f},{ty:.2f}) -> EXC {type(e).__name__}: {e}")
        # reset posture between nav attempts
        try:
            g1.reset()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
