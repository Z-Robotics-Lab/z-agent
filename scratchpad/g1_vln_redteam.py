"""RED-TEAM the VLN chain: is the projected target perception-DRIVEN (tracks the mat) or a
degenerate bottom-centre box (always 'walk straight ahead', mat-independent)?

Test: relocate the blue mat to several xy and confirm (a) the raw detector bbox is NOT full-frame,
and (b) the PROJECTED target follows the mat. If projection is invariant to mat position -> the
chain is NOT perception-load-bearing (falsified)."""
import os
os.environ.setdefault("VECTOR_NO_ROS2","1"); os.environ.setdefault("MUJOCO_GL","egl"); os.environ.pop("DISPLAY",None)
os.environ.setdefault("HF_HUB_OFFLINE","1"); os.environ.setdefault("TRANSFORMERS_OFFLINE","1")
import numpy as np, mujoco as mj
from vector_os_nano.hardware.sim.mujoco_g1 import MuJoCoG1
from vector_os_nano.perception.grounding_dino import get_shared_detector
from vector_os_nano.perception.ground_projection import project_pixel_to_ground
W,H=640,480
g1=MuJoCoG1(gui=False,room=True); g1.connect()
m,d=g1._model,g1._data
gid=mj.mj_name2id(m,mj.mjtObj.mjOBJ_GEOM,"vln_mat_blue")
# geom pos is stored on model.geom_pos for a world (static) geom
det=get_shared_detector()
def run(matxy):
    m.geom_pos[gid][0]=matxy[0]; m.geom_pos[gid][1]=matxy[1]
    mj.mj_forward(m,d)
    rgb=g1.get_camera_frame(W,H)
    boxes=det.detect(rgb,"blue mat")
    if not boxes:
        print(f"  mat@{matxy}: NO BOX"); return
    b=max(boxes,key=lambda z:(z.bbox[2]-z.bbox[0])*(z.bbox[3]-z.bbox[1]))
    x1,y1,x2,y2=b.bbox
    frac=((x2-x1)*(y2-y1))/(W*H)
    px,py=(x1+x2)/2.0,y2
    cp,cmm=g1.get_camera_pose(); f=g1.get_camera_fovy()
    world=project_pixel_to_ground(px,py,width=W,height=H,fovy_deg=f,cam_pos=cp,cam_mat=cmm)
    err=None if world is None else ((world[0]-matxy[0])**2+(world[1]-matxy[1])**2)**0.5
    print(f"  mat@{matxy}: bbox=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}) frac_frame={frac:.2f} "
          f"proj={None if world is None else tuple(round(v,2) for v in world)} err_to_mat={None if err is None else round(err,2)}m")
print("=== does the projected target TRACK the mat? ===")
for xy in [(12.6,3.0),(13.5,2.2),(11.8,3.8),(14.0,3.0)]:
    run(xy)
g1.close()
