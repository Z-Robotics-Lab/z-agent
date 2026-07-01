"""Decide the VLN build: is the curated blue mat (12.6,3) VISIBLE in g1 head-cam spawn view,
REACHABLE by the planner, and does a ground-projection of the blue blob land near its GT xy?"""
import os
os.environ.setdefault("VECTOR_NO_ROS2","1"); os.environ.setdefault("MUJOCO_GL","egl"); os.environ.pop("DISPLAY",None)
import numpy as np, mujoco as mj
from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1, _SCENE_CAM_NAME
g1=MuJoCoG1(gui=False,room=True); g1.connect(); m,d=g1._model,g1._data
def is_blue(c): return c[2]>0.55 and c[0]<0.5 and c[1]<0.6
cam=m.cam(_SCENE_CAM_NAME).id; W,H=640,480
r=mj.Renderer(m,H,W); r.update_scene(d,camera=cam); r.enable_segmentation_rendering(); seg=r.render()[:,:,0]
blue=[gi for gi in range(m.ngeom) if is_blue(m.geom_rgba[gi])]
for gi in blue:
    n=int((seg==gi).sum())
    if n>0:
        gn=mj.mj_id2name(m,mj.mjtObj.mjOBJ_GEOM,gi); print(f"in-view blue geom={gn} px={n} xyz={tuple(round(float(v),2) for v in d.geom_xpos[gi])}")
mask=np.isin(seg,blue); ys,xs=np.where(mask)
if len(xs):
    print(f"blue blob n={len(xs)} bbox x[{xs.min()}..{xs.max()}] y[{ys.min()}..{ys.max()}] centroid=({xs.mean():.0f},{ys.mean():.0f}) bottom_y={ys.max()}")
    cp=d.cam_xpos[cam].copy(); cm=d.cam_xmat[cam].reshape(3,3).copy(); f=0.5*H/np.tan(np.deg2rad(m.cam_fovy[cam])/2)
    def proj(px,py,z=0.0):
        x=(px-W/2)/f; y=(py-H/2)/f; dc=np.array([x,-y,-1.0]); dc/=np.linalg.norm(dc); dw=cm@dc
        t=(z-cp[2])/dw[2]; return None if t<0 else (round(float(cp[0]+t*dw[0]),2),round(float(cp[1]+t*dw[1]),2))
    print(f"proj blob-bottom({xs.mean():.0f},{ys.max()}) z=0 -> {proj(xs.mean(),ys.max(),0.0)}  (mat GT xy=(12.6,3.0))")
else:
    print("BLUE NOT VISIBLE")
res=g1.navigate_to(12.6,3.0); pf=g1.get_position()
dxy=((pf[0]-12.6)**2+(pf[1]-3.0)**2)**0.5
print(f"navigate_to(12.6,3.0): res={bool(res)} reached_within={dxy:.2f}m final={tuple(round(float(v),2) for v in pf[:2])} reason={res.get('reason')!r}")
r.close(); g1.close()
