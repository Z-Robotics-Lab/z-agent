# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for G1-in-go2-room scene — R1 WIP floor.

Tests are headless (MUJOCO_GL=egl) and cover:
  1. Scene compiles and contains both the room's pick_table AND g1's pelvis.
  2. The compiled model has the g1_head_rgb camera.
  3. G1 self-geom-id set is non-empty.
  4. _start_g1 is wired in sim_tool (method exists + "g1" in schema enum).

Run:
    cd /home/yusen/Desktop/vector_os_nano
    PATH=/usr/bin:$PATH MUJOCO_GL=egl .venv/bin/python -m pytest tests/unit/hardware/sim/test_g1_room.py -q
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Force EGL rendering for headless CI
os.environ.setdefault("MUJOCO_GL", "egl")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_G1_SCENE_XML = Path(
    "/home/yusen/Desktop/vector_os_nano/vector_os_nano/hardware/sim/mjcf/g1/scene_g1_room.xml"
)


def _ensure_scene() -> Path:
    """Build the scene if not already built (idempotent, fast on cache hit)."""
    from vector_os_nano.hardware.sim.mujoco_g1 import _build_g1_room_scene_xml
    return _build_g1_room_scene_xml()


# ---------------------------------------------------------------------------
# Test 1: scene builds and compiles — both pick_table and g1_pelvis present
# ---------------------------------------------------------------------------

def test_scene_compiles_with_pick_table_and_g1_pelvis() -> None:
    """The compiled scene must contain both room geometry and g1 robot."""
    import mujoco

    scene_path = _ensure_scene()
    assert scene_path.exists(), f"scene_g1_room.xml not found at {scene_path}"

    model = mujoco.MjModel.from_xml_path(str(scene_path))
    assert model.nbody > 0, "Model has no bodies"

    # Collect body names
    body_names = {
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, i)
        for i in range(model.nbody)
    }

    assert "pick_table" in body_names, (
        f"pick_table not found in model bodies: {sorted(body_names)}"
    )
    assert "g1_pelvis" in body_names, (
        f"g1_pelvis not found in model bodies: {sorted(body_names)}"
    )


# ---------------------------------------------------------------------------
# Test 2: g1_head_rgb camera exists in compiled model
# ---------------------------------------------------------------------------

def test_g1_head_camera_in_compiled_model() -> None:
    """The compiled scene must contain the g1_head_rgb camera."""
    import mujoco

    scene_path = _ensure_scene()
    model = mujoco.MjModel.from_xml_path(str(scene_path))

    cam_names = [
        mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_CAMERA, i)
        for i in range(model.ncam)
    ]
    assert "g1_head_rgb" in cam_names, (
        f"g1_head_rgb camera not found; available cameras: {cam_names}"
    )


# ---------------------------------------------------------------------------
# Test 3: G1 self-geom-id set is non-empty
# ---------------------------------------------------------------------------

def test_g1_self_geom_set_nonempty() -> None:
    """_build_robot_geom_set must find at least one g1_* body geom."""
    import mujoco
    from vector_os_nano.hardware.sim.mujoco_g1 import (
        _build_g1_room_scene_xml,
        _build_robot_geom_set,
    )

    scene_path = _build_g1_room_scene_xml()
    model = mujoco.MjModel.from_xml_path(str(scene_path))
    geom_ids = _build_robot_geom_set(model)

    assert len(geom_ids) > 0, "Robot geom set is empty — lidar self-filter will not work"

    # Verify all geoms in the set belong to g1_* bodies
    for gid in geom_ids:
        bid = model.geom_bodyid[gid]
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, bid) or ""
        assert name.startswith("g1_"), (
            f"Non-g1 body '{name}' in robot geom set (geom_id={gid})"
        )


# ---------------------------------------------------------------------------
# Test 4: _start_g1 wired in sim_tool (no sim instantiated)
# ---------------------------------------------------------------------------

def test_start_g1_wired_in_sim_tool() -> None:
    """SimStartTool must have _start_g1 method and 'g1' in the schema enum."""
    from vector_os_nano.vcli.tools.sim_tool import SimStartTool

    assert hasattr(SimStartTool, "_start_g1"), (
        "SimStartTool._start_g1 not found — dispatch not wired"
    )
    assert callable(SimStartTool._start_g1), "_start_g1 is not callable"

    schema = SimStartTool.input_schema
    sim_type_prop = schema.get("properties", {}).get("sim_type", {})
    allowed = sim_type_prop.get("enum", [])
    assert "g1" in allowed, (
        f"'g1' not in sim_type enum; allowed values: {allowed}"
    )
