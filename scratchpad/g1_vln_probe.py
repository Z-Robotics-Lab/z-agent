"""Decide the VLN round: WHICH red geom(s) are in g1's head-cam spawn view, and does a
ground-plane projection of the red blob land near the reachable hall rug (9.99,4.08)?"""
import os
os.environ.setdefault("VECTOR_NO_ROS2", "1"); os.environ.setdefault("MUJOCO_GL", "egl")
os.environ.pop("DISPLAY", None)
import numpy as np, mujoco as mj
from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1, _SCENE_CAM_NAME

g1 = MuJoCoG1(gui=False, room=True); g1.connect()
m, d = g1._model, g1._data
def is_red(rgba):
    r,g,b = rgba[:3]; return r>0.55 and g<0.5 and b<0.5
cam_id = m.cam(_SCENE_CAM_NAME).id
W,H = 640,480
r = mj.Renderer(m, H, W); r.update_scene(d, camera=cam_id); r.enable_segmentation_rendering()
seg = r.render()[:,:,0]
red_geoms = [gi for gi in range(m.ngeom) if is_red(m.geom_rgba[gi])]
# per-geom in-view pixel count
print("=== in-view red geoms (spawn) ===")
for gi in red_geoms:
    n = int((seg==gi).sum())
    if n>0:
        gname = mj.mj_id2name(m, mj.mjtObj.mjOBJ_GEOM, gi) or f"g{gi}"
        bid=int(m.geom_bodyid[gi]); bname=mj.mj_id2name(m, mj.mjtObj.mjOBJ_BODY, bid)
        wxyz=tuple(round(float(v),2) for v in d.geom_xpos[gi])
        print(f"  geom={gname:24s} body={bname:20s} px={n:5d} xyz={wxyz}")
# blob bbox on red mask
mask = np.isin(seg, red_geoms)
ys,xs = np.where(mask)
print(f"\nred blob: n={len(xs)} bbox x[{xs.min()}..{xs.max()}] y[{ys.min()}..{ys.max()}] "
      f"centroid=({xs.mean():.0f},{ys.mean():.0f}) bottom_y={ys.max()}")
# ground projection of blob bottom-center pixel through camera matrix onto z=0 plane
# camera pose
cam_pos = d.cam_xpos[cam_id].copy()
cam_mat = d.cam_xmat[cam_id].reshape(3,3).copy()  # cols = cam x,y,z in world
fovy = m.cam_fovy[cam_id]
f = 0.5*H/np.tan(np.deg2rad(fovy)/2)
def pix_to_world_ground(px,py, z_plane=0.0):
    # mujoco cam looks down -z of its frame; image x right, y down
    x = (px - W/2)/f; y = (py - H/2)/f
    dir_cam = np.array([x, -y, -1.0]); dir_cam/=np.linalg.norm(dir_cam)
    dir_world = cam_mat @ dir_cam
    if abs(dir_world[2])<1e-6: return None
    t = (z_plane - cam_pos[2])/dir_world[2]
    if t<0: return None
    p = cam_pos + t*dir_world
    return (round(float(p[0]),2), round(float(p[1]),2))
bx, by = float(xs.mean()), float(ys.max())
for zpl in (0.0, 0.32):
    print(f"proj blob-bottom({bx:.0f},{by:.0f}) -> z={zpl}: {pix_to_world_ground(bx,by,zpl)}")
print(f"proj blob-centroid -> z=0: {pix_to_world_ground(xs.mean(),ys.mean(),0.0)}")
print(f"cam_pos={tuple(round(float(v),2) for v in cam_pos)} spawn={tuple(round(float(v),2) for v in g1.get_position())}")
print("reachable hall rug GT = (9.99, 4.08)")
r.close(); g1.close()
