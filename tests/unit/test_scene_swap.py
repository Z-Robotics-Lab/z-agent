# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the VECTOR_SCENE_SWAP scenario knob swaps the two BOTTLES' (x,y)
positions (blue <-> green) at connect. Each bottle lands on the OTHER bottle's
already-validated spot, so reach/FOV geometry stays valid (no new grasp/perception
regime) — but the LEFT-RIGHT ordering flips. That makes it a position-invariance
probe: a capability that grounded on the frozen layout (e.g. the ordinal resolver,
E31: 最左边的瓶子 -> green) must now track the NEW layout (resolve to whichever
bottle occupies the leftmost spot), proving the grounding reads LIVE positions and
is not overfit to memorized coordinates.

Default (unset) keeps the frozen baseline. The honest-verify spine reads live GT
(arm_sim_oracle), so moving the bodies never weakens verification — this knob only
changes the scenario, mirroring VECTOR_FETCH_FAR.
"""
from __future__ import annotations

import mujoco
import numpy as np
import pytest

from zeno.hardware.sim.mujoco_go2 import MuJoCoGo2

# Frozen-scene baseline positions (see test_fetch_far_scene.py).
_GREEN_XY = (10.88, 3.00)
_BLUE_XY = (10.90, 2.78)
_RED_XY = (10.90, 3.22)


def _body_xy(go2: MuJoCoGo2, name: str) -> np.ndarray:
    m, d = go2._mj.model, go2._mj.data
    bid = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_BODY, name)
    assert bid >= 0, f"{name} must exist in the room scene"
    qadr = int(m.jnt_qposadr[int(m.body_jntadr[bid])])
    return np.array([d.qpos[qadr], d.qpos[qadr + 1]])


def test_default_keeps_frozen_layout(monkeypatch):
    """Default (no env): blue/green sit at their frozen-scene spots."""
    monkeypatch.delenv("VECTOR_SCENE_SWAP", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    assert _body_xy(go2, "pickable_bottle_green") == pytest.approx(_GREEN_XY, abs=0.05)
    assert _body_xy(go2, "pickable_bottle_blue") == pytest.approx(_BLUE_XY, abs=0.05)


def test_swap_exchanges_blue_and_green(monkeypatch):
    """VECTOR_SCENE_SWAP: blue lands on green's old (x,y) and vice-versa; the
    left-right ordering flips so ordinal grounding must track the new layout."""
    monkeypatch.setenv("VECTOR_SCENE_SWAP", "1")
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    # Each bottle now occupies the OTHER bottle's validated spot.
    assert _body_xy(go2, "pickable_bottle_blue") == pytest.approx(_GREEN_XY, abs=0.05)
    assert _body_xy(go2, "pickable_bottle_green") == pytest.approx(_BLUE_XY, abs=0.05)


def test_swap_leaves_red_can_untouched(monkeypatch):
    """VECTOR_SCENE_SWAP moves only the two BOTTLES; the red CAN is unaffected."""
    monkeypatch.setenv("VECTOR_SCENE_SWAP", "1")
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    assert _body_xy(go2, "pickable_can_red") == pytest.approx(_RED_XY, abs=0.05)
