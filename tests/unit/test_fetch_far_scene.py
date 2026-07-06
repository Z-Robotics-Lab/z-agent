# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the VECTOR_FETCH_FAR scenario knob relocates ALL THREE pickables
(green + blue + red) ~3 m down the clear +X hall (onto pick_table_far) — beyond
perception_grasp's 1.6 m self-approach radius — so the model must compose
look -> navigate_to_object -> perception_grasp (the agent-adaptive fetch). Moving
the blue/red distractors too (not green alone) removes the confound where a near
distractor sat inside the spawn's reach and a 1-step perception_grasp could engage
it instead of routing to the far target. The default (unset) keeps the in-reach
near-grasp baseline. The honest-verify spine reads live GT (arm_sim_oracle), so
moving the body does not weaken verification — this knob only changes the scenario.
"""
from __future__ import annotations

import mujoco
import numpy as np
import pytest

from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2

_SPAWN = np.array([10.0, 3.0])
_SELF_APPROACH_RADIUS_M = 1.6  # perception_grasp._SCAN_MAX_LOCAL_M


def _body_xy(go2: MuJoCoGo2, name: str) -> np.ndarray:
    m, d = go2._mj.model, go2._mj.data
    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, name)
    assert bid >= 0, f"{name} must exist in the room scene"
    qadr = int(m.jnt_qposadr[int(m.body_jntadr[bid])])
    return np.array([d.qpos[qadr], d.qpos[qadr + 1]])


def _green_xy(go2: MuJoCoGo2) -> np.ndarray:
    return _body_xy(go2, "pickable_bottle_green")


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


def test_default_keeps_all_three_near(monkeypatch):
    """Default (no env): blue and red distractors stay near the spawn pedestal."""
    monkeypatch.delenv("VECTOR_FETCH_FAR", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    assert _body_xy(go2, "pickable_bottle_blue")[0] == pytest.approx(10.90, abs=0.05)
    assert _body_xy(go2, "pickable_can_red")[0] == pytest.approx(10.90, abs=0.05)


def test_far_knob_pushes_all_three_out_of_reach(monkeypatch):
    """VECTOR_FETCH_FAR: blue + red distractors move the SAME +3 m as green so no
    near distractor remains inside the spawn's 1-step reach to confound the far
    green fetch. The y-spread is preserved (green stays the deictic centre)."""
    monkeypatch.setenv("VECTOR_FETCH_FAR", "1")
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    blue = _body_xy(go2, "pickable_bottle_blue")
    red = _body_xy(go2, "pickable_can_red")
    # +3.0 m down the hall, y-spread preserved (2.78 / 3.22 around green's 3.0)
    assert blue[0] == pytest.approx(13.90, abs=0.05)
    assert blue[1] == pytest.approx(2.78, abs=0.05)
    assert red[0] == pytest.approx(13.90, abs=0.05)
    assert red[1] == pytest.approx(3.22, abs=0.05)
    # every distractor is now well beyond the 1.6 m self-approach radius
    assert np.linalg.norm(blue - _SPAWN) > 2.0
    assert np.linalg.norm(red - _SPAWN) > 2.0
