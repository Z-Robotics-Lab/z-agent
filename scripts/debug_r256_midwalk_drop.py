#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""DEBUG R256/E60 — localize the courtyard PLACE mid-walk drop.

In-process go2+Piper+gripper (courtyard), NO brain/VLM. Grasp the green bottle,
then reproduce mobile_place's walk (navigate_to approach) and dock (Step-6b) while
sampling the held object at ~30 Hz. Attributes any holding_object()==False to a
phase (walk / dock) and tells apart:
  - transient weld COMPLIANCE (dist>0.08 but eq_active stays 1, object stays lifted)
  - real SEPARATION (object z -> floor, or eq_active flips 0)
  - read RACE (a stationary re-read disagrees).

Prints one JSON summary line prefixed DIAG_SUMMARY=. Diagnostics only; no verdict.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time

_TARGET = "green bottle"


class _StubVLM:
    def query(self, *_a, **_k):
        return {"answer": "yes", "confidence": 1.0}

    def describe(self, *_a, **_k):
        return "a green bottle on a table"


def _dist(a, b):
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def main() -> int:
    os.environ["VECTOR_SIM_WITH_ARM"] = "1"
    os.environ.setdefault("VECTOR_ROOM_TEMPLATE", "courtyard")

    from vector_os_nano.core.agent import Agent
    from vector_os_nano.core.scene_graph import SceneGraph
    from vector_os_nano.core.skill import SkillContext
    from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2
    from vector_os_nano.hardware.sim.mujoco_piper import MuJoCoPiper
    from vector_os_nano.hardware.sim.mujoco_piper_gripper import MuJoCoPiperGripper
    from vector_os_nano.perception.go2_grasp_perception import Go2GraspPerception
    from vector_os_nano.skills.perception_grasp import PerceptionGraspSkill
    from vector_os_nano.skills import mobile_place as mp
    from vector_os_nano.vcli.worlds.arm_sim_oracle import make_holding_object, _ee_position

    go2 = MuJoCoGo2(gui=False, room=True, backend="mpc")
    go2.connect()
    piper = MuJoCoPiper(go2)
    piper.connect()
    gripper = MuJoCoPiperGripper(go2)
    gripper.connect()
    perception = Go2GraspPerception(go2, width=320, height=240)
    agent = Agent(base=go2, arm=piper, gripper=gripper, perception=perception, config={})
    holding = make_holding_object(agent)
    ctx = SkillContext(
        arms={"default": piper}, grippers={"default": gripper},
        bases={"default": go2}, perception_sources={"default": perception},
        services={"vlm": _StubVLM(), "spatial_memory": SceneGraph()},
    )

    samples: list[dict] = []
    phase = {"name": "settle"}
    stop = threading.Event()

    def _bottle_state():
        """(dist_ee, obj_z, eq_active, is_holding_flag) for the object nearest the EE."""
        try:
            ee = _ee_position(piper)
            objs = piper.get_object_positions() or {}
            best_n, best_d = None, float("inf")
            for n, p in objs.items():
                d = _dist(ee, p)
                if d < best_d:
                    best_d, best_n = d, n
            oz = float(objs[best_n][2]) if best_n else float("nan")
            wa = gripper.weld_is_active() if hasattr(gripper, "weld_is_active") else {}
            eq = any(wa.values()) if wa else None
            return best_d, oz, eq, bool(gripper.is_holding())
        except Exception as exc:  # noqa: BLE001
            return float("nan"), float("nan"), None, None

    def _sampler():
        while not stop.is_set():
            d, oz, eq, ih = _bottle_state()
            try:
                ho = bool(holding())
            except Exception:  # noqa: BLE001
                ho = None
            samples.append({
                "t": round(time.monotonic(), 3), "ph": phase["name"],
                "d": round(d, 4), "oz": round(oz, 4), "eq": eq, "ih": ih, "ho": ho,
            })
            time.sleep(0.033)

    result = {"target": _TARGET, "template": os.environ.get("VECTOR_ROOM_TEMPLATE")}
    try:
        time.sleep(2.0)
        gr = PerceptionGraspSkill().execute({"query": _TARGET}, ctx)
        result["grasp_success"] = bool(gr.success)
        result["grasp_holding_object"] = bool(holding())
        if not gr.success or not holding():
            result["abort"] = f"grasp failed: {gr.error_message!r}"
            print("DIAG_SUMMARY=" + json.dumps(result))
            return 2

        # Resolve the scene place receptacle + its -X approach (exactly mobile_place's path).
        geom = mp._scene_place_geom(go2)
        tx, ty = float(geom[0]), float(geom[1])
        clearance = mp._DEFAULT_CLEARANCE
        approach_x, approach_y = tx - clearance, ty
        result["place_target"] = [round(tx, 3), round(ty, 3)]
        result["approach"] = [round(approach_x, 3), round(approach_y, 3)]
        dog0 = go2.get_position()
        result["dog_at_grasp"] = [round(float(dog0[0]), 3), round(float(dog0[1]), 3)]

        th = threading.Thread(target=_sampler, daemon=True)
        th.start()

        # PHASE walk — the L-nav approach walk (the suspected mid-walk drop window).
        phase["name"] = "walk"
        mp._navigate_to_approach(go2, approach_x, approach_y, True)
        time.sleep(0.5)

        # PHASE dock — Step-6b jam-dock repose (H4 window).
        phase["name"] = "dock"
        try:
            from vector_os_nano.skills.perception_grasp import (
                _approach_object, _face_object, _grasp_ready_repose,
            )
            _grasp_ready_repose(go2, (tx, ty))
            _approach_object(go2, (tx, ty))
            _face_object(go2, (tx, ty))
        except Exception as exc:  # noqa: BLE001
            result["dock_raised"] = str(exc)
        time.sleep(0.5)

        phase["name"] = "post"
        time.sleep(0.5)
        stop.set()
        th.join(timeout=2.0)

        # ---- Attribute: first sample where holding_object went False, per phase ----
        def _phase_stats(ph):
            ss = [s for s in samples if s["ph"] == ph]
            if not ss:
                return None
            ds = [s["d"] for s in ss if s["d"] == s["d"]]
            ho_false = [s for s in ss if s["ho"] is False]
            eq_off = [s for s in ss if s["eq"] is False]
            floor = [s for s in ss if s["oz"] == s["oz"] and s["oz"] < 0.10]
            return {
                "n": len(ss),
                "d_max": round(max(ds), 4) if ds else None,
                "d_min": round(min(ds), 4) if ds else None,
                "ho_false_n": len(ho_false),
                "eq_off_n": len(eq_off),
                "floor_n": len(floor),
                "first_ho_false_t": ho_false[0]["t"] if ho_false else None,
            }

        result["phases"] = {p: _phase_stats(p) for p in ("walk", "dock", "post")}
        result["n_samples"] = len(samples)
        # A compact trace of the moments around the FIRST holding_object=False.
        first_false_idx = next((i for i, s in enumerate(samples) if s["ho"] is False), None)
        if first_false_idx is not None:
            lo = max(0, first_false_idx - 3)
            result["around_first_false"] = samples[lo:first_false_idx + 4]
        result["final_holding_object"] = bool(holding())
        print("DIAG_SUMMARY=" + json.dumps(result))
        return 0
    finally:
        stop.set()
        for dev in (gripper, piper, go2):
            try:
                dev.disconnect()
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
