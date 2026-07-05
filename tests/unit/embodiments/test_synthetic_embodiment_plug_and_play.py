# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Plug-and-play proof for a SYNTHETIC third embodiment (North Star Inv-3).

AGENTS.md Invariant 3: "Embodiments/worlds are CONFIG, not code — one generic
driver; if a robot needs kernel or driver edits, the design is wrong." The
shipped coverage (test_embodiment_config / test_dof_layout) proves the generic
path only for the TWO shipped robots (go2, g1) — both 12-DoF, both with a joint
naming convention the code was co-developed against. Neither test proves the
path is not silently OVERFIT to those two conventions.

This test stands up a THIRD robot that never ships in the repo — a made-up
tripod with:
  * a novel root-body name + attach prefix ("syn_"),
  * a NON-12 actuated-joint count (3, so any implicit "== 12" assumption fails),
  * the robot placed AFTER a free prop so its freejoint is NOT at qpos 0 (proves
    DofLayout introspects addresses, never assumes 0),
  * manifest stance keys in the un-prefixed convention ("hip_a"), which must
    match the prefixed model joints ("syn_hip_a_joint") via suffix-matching.

It flows ONLY through the generic ``embodiments/`` helpers + a data manifest +
an in-memory MJCF — it imports NO ``mujoco_go2`` / ``mujoco_g1`` driver. If a
new robot can reach a correct DofLayout + stance vector + capability profile
without a driver edit, Inv-3 holds generically; if not, the failure IS the
finding. Headless model compile only (no physics, no GL window, no sim slot).

Run:
    PATH=/usr/bin:$PATH MUJOCO_GL=egl .venv/bin/python -m pytest \
        tests/unit/embodiments/test_synthetic_embodiment_plug_and_play.py -q
"""
from __future__ import annotations

import dataclasses
import os

import numpy as np
import pytest

os.environ.setdefault("MUJOCO_GL", "egl")

# Generic embodiment layer ONLY — no per-robot driver import (that is the point).
from vector_os_nano.embodiments.config import (
    CapabilityProfile,
    EmbodimentConfig,
    EmbodimentConfigError,
    parse_embodiment_config,
)
from vector_os_nano.embodiments.dof_layout import DofLayout

# The synthetic robot's number of actuated joints — deliberately NOT 12.
_SYN_NUM_ACTUATED = 3

# Nominal stance the manifest declares, in the un-prefixed (model-agnostic)
# convention. Distinct values so a mis-ordered vector is caught.
_SYN_STANCE = {"hip_a": 0.10, "hip_b": -0.20, "hip_c": 0.30}


# A tiny MJCF for a robot that ships nowhere in the repo. A free "prop_cube" is
# declared BEFORE the robot so the robot's freejoint does not land at qpos 0 —
# mirroring the real attach-last scenario the go2 scene relies on.
_SYNTHETIC_MJCF = """
<mujoco model="synthetic_tripod">
  <worldbody>
    <body name="prop_cube" pos="1 1 0.1">
      <freejoint/>
      <geom type="box" size="0.05 0.05 0.05"/>
    </body>
    <body name="syn_torso" pos="0 0 0.30">
      <freejoint/>
      <geom type="box" size="0.10 0.10 0.05"/>
      <body name="syn_leg_a" pos="0.10 0 0">
        <joint name="syn_hip_a_joint" type="hinge" axis="0 1 0"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.15" size="0.02"/>
      </body>
      <body name="syn_leg_b" pos="-0.05 0.087 0">
        <joint name="syn_hip_b_joint" type="hinge" axis="0 1 0"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.15" size="0.02"/>
      </body>
      <body name="syn_leg_c" pos="-0.05 -0.087 0">
        <joint name="syn_hip_c_joint" type="hinge" axis="0 1 0"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.15" size="0.02"/>
      </body>
    </body>
  </worldbody>
</mujoco>
"""


# The robot's manifest — a plain dict, exactly what robot.yaml deserializes to.
def _syn_manifest() -> dict:
    return {
        "id": "synthetic_tripod",
        "display_name": "Synthetic Tripod (test-only)",
        "model": {"path": "synthetic/tripod.xml", "root_body": "syn_torso"},
        "spawn": {"xy": [0.0, 0.0], "base_height": 0.30, "heading": 0.0},
        "stance": dict(_SYN_STANCE),
        "sensors": [
            {
                "role": "camera",
                "mount_body": "syn_torso",
                "name": "syn_head_rgb",
                "pos": [0.08, 0.0, 0.05],
            }
        ],
        "policy": {"ref": "synthetic/tripod_gait.pt"},
        "capabilities": {"has_base": True, "camera": True, "lidar": False},
    }


@pytest.fixture(scope="module")
def syn_model():
    import mujoco

    return mujoco.MjModel.from_xml_string(_SYNTHETIC_MJCF)


# ---------------------------------------------------------------------------
# 1. The manifest parses into a frozen EmbodimentConfig — no driver, no code.
# ---------------------------------------------------------------------------


def test_synthetic_manifest_parses_frozen() -> None:
    cfg = parse_embodiment_config(_syn_manifest(), ctx="synthetic_tripod/robot.yaml")
    assert isinstance(cfg, EmbodimentConfig)
    assert cfg.id == "synthetic_tripod"
    assert cfg.model.root_body == "syn_torso"
    assert cfg.spawn.base_height == pytest.approx(0.30)
    assert cfg.stance == _SYN_STANCE
    # Frozen (Rule 6): mutation must raise, never silently succeed.
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.id = "hacked"  # type: ignore[misc]


def test_synthetic_capabilities_and_sensor() -> None:
    cfg = parse_embodiment_config(_syn_manifest())
    assert isinstance(cfg.capabilities, CapabilityProfile)
    assert cfg.capabilities.has_base is True
    assert cfg.capabilities.camera is True
    assert cfg.capabilities.lidar is False
    # The novel-role sensor survives parsing untouched.
    assert len(cfg.sensors) == 1
    cam = cfg.sensors[0]
    assert cam.role == "camera"
    assert cam.mount_body == "syn_torso"
    assert cam.name == "syn_head_rgb"


# ---------------------------------------------------------------------------
# 2. DofLayout introspects a robot it has never seen — addresses self-consistent
#    and NOT assumed to start at 0 (a prop precedes the robot in qpos).
# ---------------------------------------------------------------------------


def test_synthetic_layout_addresses_introspected(syn_model) -> None:
    layout = DofLayout(syn_model, "syn_torso", _SYN_NUM_ACTUATED)
    # The prop_cube's freejoint occupies qpos[0:7]; the robot's root is AFTER it.
    assert layout.root_qpos_adr == 7, "DofLayout must introspect, not assume qpos 0"
    assert layout.quat_start == layout.root_qpos_adr + 3
    assert layout.joint_qpos_start == layout.root_qpos_adr + 7
    assert layout.angvel_start == layout.root_dof_adr + 3
    assert layout.joint_dof_start == layout.root_dof_adr + 6
    # The three leg qpos slots sit right after the 7-float root block.
    assert layout.num_actuated == _SYN_NUM_ACTUATED


def test_synthetic_robot_geom_set_is_subtree_only(syn_model) -> None:
    layout = DofLayout(syn_model, "syn_torso", _SYN_NUM_ACTUATED)
    # The robot's geoms (torso + 3 legs = 4) belong to the set; the prop does not.
    prop_bid = int(syn_model.body("prop_cube").id)
    prop_geoms = {
        gid
        for gid in range(int(syn_model.ngeom))
        if int(syn_model.geom_bodyid[gid]) == prop_bid
    }
    assert prop_geoms, "test scene should have a prop geom"
    assert prop_geoms.isdisjoint(layout.robot_geom_ids)
    assert len(layout.robot_geom_ids) == 4  # torso + 3 legs


# ---------------------------------------------------------------------------
# 3. Nominal stance builds from the manifest by SUFFIX-matching prefixed joints
#    ("syn_hip_a_joint" <- manifest key "hip_a"), in qpos order — no driver.
# ---------------------------------------------------------------------------


def test_synthetic_stance_vector_maps_by_suffix(syn_model) -> None:
    cfg = parse_embodiment_config(_syn_manifest())
    layout = DofLayout(syn_model, "syn_torso", _SYN_NUM_ACTUATED)
    stance_vec = layout.build_stance_vector(syn_model, cfg.stance)
    assert stance_vec.shape == (_SYN_NUM_ACTUATED,)
    assert stance_vec.dtype == np.float32
    # Legs are declared a,b,c in body order == qpos order here, so the vector is
    # the manifest angles in that order — proving prefix-strip + suffix-match on
    # a naming convention neither shipped robot uses.
    np.testing.assert_allclose(stance_vec, [0.10, -0.20, 0.30], rtol=0, atol=1e-6)


def test_synthetic_stance_missing_key_fails_loud(syn_model) -> None:
    layout = DofLayout(syn_model, "syn_torso", _SYN_NUM_ACTUATED)
    incomplete = {"hip_a": 0.1, "hip_b": 0.2}  # hip_c missing
    with pytest.raises(ValueError, match="no stance angle"):
        layout.build_stance_vector(syn_model, incomplete)


# ---------------------------------------------------------------------------
# 4. A malformed synthetic manifest fails loud (fail-loud generalizes too).
# ---------------------------------------------------------------------------


def test_synthetic_missing_root_body_fails_loud() -> None:
    bad = _syn_manifest()
    del bad["model"]["root_body"]
    with pytest.raises(EmbodimentConfigError, match="root_body"):
        parse_embodiment_config(bad, ctx="synthetic_tripod/robot.yaml")
