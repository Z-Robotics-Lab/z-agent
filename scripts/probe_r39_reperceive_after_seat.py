# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R39 Debug EXPERIMENT — does the perceived grasp-z stabilize AFTER the approach/seat?

The end-to-end chain (r39_run6.log) docks + perceives + approaches but the GRASP does
NOT ground: the perceived z is mislocalized LOW (0.13, 0.044 vs true 0.32) even from
the docked +X pose, while the A/B debug probe got z=0.32 (2.8 cm) from a *slightly
different* docked framing. Hypothesis: the perceive taken ONCE from the dock-arrival
framing is sensitive (mask-centroid lands on table/can-base -> low z); RE-PERCEIVING
after _approach_object seats the dog at its proven head-on close standoff yields the
correct z (that is exactly the framing the scripted-from-spawn grasp perceives from).

DISCRIMINATING CHECK (one sim, both targets): for green (centerline y=3.0) and red
(off-axis y=3.22): dock -> perceive@dock -> _approach_object(perceived xy) + seat ->
perceive@seat. Log z and grasp_vs_GT at BOTH moments. If perceive@seat z ~= 0.32 (GT)
while perceive@dock z is low, the fix is: re-perceive after the approach and grasp THAT
point. READ-ONLY probe; no repo-code edit; foreground; os._exit at end.
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("VECTOR_SIM_WITH_ARM", "1")
os.environ.setdefault("VECTOR_ENABLE_MANIPULATION", "1")
os.environ.setdefault("MUJOCO_GL", "egl")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the proven instrumented perceive + helpers from the A/B debug probe.
import scripts.probe_r39_debug_floor_vs_cans as ab  # noqa: E402

ART = "/tmp/r39_reperceive"
os.makedirs(ART, exist_ok=True)

_GREEN_GT = (10.88, 3.00, 0.320)
_RED_GT = (10.90, 3.22, 0.320)
_DOCK_XY = (10.0, 3.0)
_DOCK_HD = 0.0


def _log(m: str) -> None:
    print(f"[REPERC] {m}", flush=True)


def _perceive(perception, base, query, tag):
    """Instrumented perceive for `query`, writing frames under ART."""
    ab._QUERY = query  # the instrumented helper reads module-global _QUERY
    ab.ART = ART
    return ab.perceive_instrumented(perception, base, tag, save_frame=True)


def _trial(perception, base, query, gt, label):
    from vector_os_nano.skills.utils.terminal_dock import terminal_dock
    from vector_os_nano.skills.perception_grasp import _approach_object

    out = {"label": label, "query": query, "gt": list(gt)}

    # 0. dock to the FIXED proven pose (heading fix).
    _log(f"{label}: dock to {_DOCK_XY} hd={_DOCK_HD}")
    terminal_dock(base, _DOCK_XY, _DOCK_HD, on_progress=lambda m: _log(f"{label} dock {m}"))
    time.sleep(1.0)

    # 1. perceive @ dock pose.
    r_dock = _perceive(perception, base, query, f"{label}_at_dock")
    out["at_dock"] = r_dock
    gw = r_dock.get("grasp_world")
    if not gw:
        _log(f"{label}: perceive@dock produced NO grasp_world — aborting trial")
        return out

    # 2. hand off to the PROVEN approach (vy lateral track to the perceived xy) + seat.
    _log(f"{label}: _approach_object to perceived xy=({gw[0]:.2f},{gw[1]:.2f})")
    _approach_object(base, (gw[0], gw[1]), max_walks=30,
                     on_progress=lambda m: _log(f"{label} approach {m}"))
    time.sleep(1.0)
    out["pose_after_approach"] = ab._pose(base)

    # 3. RE-PERCEIVE @ the seated standoff.
    r_seat = _perceive(perception, base, query, f"{label}_at_seat")
    out["at_seat"] = r_seat

    z_dock = gw[2]
    z_seat = (r_seat.get("grasp_world") or [None, None, None])[2]
    d_dock = r_dock.get("grasp_vs_red_gt_m") if label == "red" else r_dock.get("grasp_vs_green_gt_m")
    d_seat = r_seat.get("grasp_vs_red_gt_m") if label == "red" else r_seat.get("grasp_vs_green_gt_m")
    _log(f"{label}: VERDICT z_dock={z_dock} z_seat={z_seat} | "
         f"dist_dock={d_dock} dist_seat={d_seat} (GT z=0.32)")
    out["summary"] = {"z_dock": z_dock, "z_seat": z_seat,
                      "dist_dock_m": d_dock, "dist_seat_m": d_seat}
    return out


def main() -> int:
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool

    _log("booting go2+arm sim ...")
    agent = SimStartTool._start_go2(gui=False, with_arm=True)
    if getattr(agent, "_arm", None) is None:
        _log("FAIL: no arm")
        return 1
    base = agent._base
    perception = agent._perception
    if perception is None:
        _log("FAIL: no perception")
        return 1
    _log(f"sim up: base={type(base).__name__} perception={type(perception).__name__}")
    time.sleep(9.0)

    report = {"green_gt": list(_GREEN_GT), "red_gt": list(_RED_GT)}
    # GREEN first (centerline — should be cleanest), then RED (off-axis).
    report["green"] = _trial(perception, base, "绿色的瓶子", _GREEN_GT, "green")
    # re-home before red so the dock starts from a comparable pose.
    from vector_os_nano.skills.utils.terminal_dock import terminal_dock
    terminal_dock(base, _DOCK_XY, _DOCK_HD, on_progress=lambda m: _log(f"rehome {m}"))
    time.sleep(1.0)
    report["red"] = _trial(perception, base, "红色的罐子", _RED_GT, "red")

    with open(os.path.join(ART, "reperceive.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    _log(f"wrote {ART}/reperceive.json")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
