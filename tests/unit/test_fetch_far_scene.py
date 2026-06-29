# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the VECTOR_FETCH_FAR scenario knob relocates the green fetch target
~3 m down the clear +X hall (onto pick_table_far) — beyond perception_grasp's 1.6 m
self-approach radius — so the model must compose look -> navigate_to_object ->
perception_grasp (the agent-adaptive fetch). The default (unset) keeps the in-reach
near-grasp baseline. The honest-verify spine reads live GT (arm_sim_oracle), so
moving the body does not weaken verification — this knob only changes the scenario.
"""
from __future__ import annotations

import mujoco
import numpy as np
import pytest

from vector_os_nano.hardware.sim.mujoco_go2 import MuJoCoGo2

_SPAWN = np.array([10.0, 3.0])
_SELF_APPROACH_RADIUS_M = 1.6  # perception_grasp._SCAN_MAX_LOCAL_M


def _green_xy(go2: MuJoCoGo2) -> np.ndarray:
    m, d = go2._mj.model, go2._mj.data
    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, "pickable_bottle_green")
    assert bid >= 0, "pickable_bottle_green must exist in the room scene"
    qadr = int(m.jnt_qposadr[int(m.body_jntadr[bid])])
    return np.array([d.qpos[qadr], d.qpos[qadr + 1]])


def test_default_keeps_green_in_reach(monkeypatch):
    """Default (no env): green stays ~0.88 m ahead, inside the self-approach radius."""
    monkeypatch.delenv("VECTOR_FETCH_FAR", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    gx = _green_xy(go2)
    assert gx[0] == pytest.approx(10.88, abs=0.05)
    assert np.linalg.norm(gx - _SPAWN) < _SELF_APPROACH_RADIUS_M


def test_far_knob_pushes_green_out_of_reach(monkeypatch):
    """VECTOR_FETCH_FAR: green relocated ~3 m down the +X hall, genuinely out of a
    1-step grasp's reach so the model MUST route navigate_to_object first."""
    monkeypatch.setenv("VECTOR_FETCH_FAR", "1")
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    gx = _green_xy(go2)
    assert gx[0] == pytest.approx(13.88, abs=0.05)
    assert gx[1] == pytest.approx(3.0, abs=0.05)
    assert np.linalg.norm(gx - _SPAWN) > 2.0  # well beyond the 1.6 m self-approach
