# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Contract: the VECTOR_ROOM_TEMPLATE scenario knob swaps the go2 ROOM TEMPLATE for a
genuinely-NEW WORLD (R229/E52 breadth pivot) — the deeper bar the R226→R228 scene-clutter
work left standing ("still ONE room"). A room enters as a new XML TEMPLATE fed to the
already-parameterized build_room_scene(room_template_path=), NOT a kernel or driver edit:
worlds are CONFIG (Invariant 3), the same discipline as embodiments (robot.yaml).

The warehouse template is a distinct compact industrial box (steel perimeter, concrete
floor, orange racking) — geometrically unlike the 20m x 14m multi-room house — but it keeps
the tuned pick furniture (pick_table + 5 pickables + place_bin) at the SAME coordinates so
every confirmed grasp/perception/place bar stays reachable. Only the room SHELL differs.

The honest-verify spine is UNTOUCHED: holding_object(real bottle) reads live sim GT the
actor cannot author; the pickable bodies are copied byte-for-byte, so a grasp grades the
same way regardless of which world shell surrounds them.

Default (unset) keeps the frozen house BYTE-IDENTICAL (mirrors VECTOR_SCENE_CLUTTER /
VECTOR_SCENE_SWAP). An unknown key fails LOUD — a typo never silently reverts to the house.
"""
from __future__ import annotations

import mujoco
import pytest

from vector_os_nano.hardware.sim.mujoco_go2 import (
    MuJoCoGo2,
    _ROOM_TEMPLATES,
    _ROOM_XML,
    _select_room_template,
)

_PICKABLES = (
    "pickable_bottle_blue",
    "pickable_bottle_green",
    "pickable_can_red",
    "pickable_bottle_yellow",
    "pickable_box_purple",
)


def _body_id(go2: MuJoCoGo2, name: str) -> int:
    return mujoco.mj_name2id(go2._mj.model, mujoco.mjtObj.mjOBJ_BODY, name)


def _geom_id(go2: MuJoCoGo2, name: str) -> int:
    return mujoco.mj_name2id(go2._mj.model, mujoco.mjtObj.mjOBJ_GEOM, name)


# ---- template selection (pure, no sim) ------------------------------------

def test_select_default_is_house(monkeypatch):
    monkeypatch.delenv("VECTOR_ROOM_TEMPLATE", raising=False)
    assert _select_room_template() == _ROOM_XML


def test_select_warehouse(monkeypatch):
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "warehouse")
    assert _select_room_template() == _ROOM_TEMPLATES["warehouse"]


def test_select_is_case_insensitive_and_trims(monkeypatch):
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "  WAREHOUSE  ")
    assert _select_room_template() == _ROOM_TEMPLATES["warehouse"]


def test_select_unknown_key_fails_loud(monkeypatch):
    """An unknown template must raise, never silently fall back to the house — otherwise a
    typo would mask which world actually ran (external input validation, fail-loud)."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "mansion")
    with pytest.raises(RuntimeError, match="not a known room template"):
        _select_room_template()


def test_warehouse_template_file_exists():
    assert _ROOM_TEMPLATES["warehouse"].exists()
    xml = _ROOM_TEMPLATES["warehouse"].read_text()
    # The scene_builder resolves these tokens; a template missing any would not compose.
    for tok in ("GO2_MODEL_PATH", "GO2_ASSETS_DIR", "GRASP_WELDS"):
        assert tok in xml, f"warehouse template must carry the {tok} token"


# ---- the warehouse actually compiles with the 5 pickables reachable -------

def test_warehouse_compiles_with_all_pickables(monkeypatch):
    """VECTOR_ROOM_TEMPLATE=warehouse: the new world compiles and every tuned pickable
    body is present at its coordinates — the grasp/perception face stays reachable."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "warehouse")
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    for name in _PICKABLES:
        assert _body_id(go2, name) >= 0, f"{name} must exist in the warehouse world"
    # Pick furniture present too.
    for name in ("pick_table", "place_bin"):
        assert _body_id(go2, name) >= 0, f"{name} must exist in the warehouse world"


def test_warehouse_green_bottle_at_house_coordinates(monkeypatch):
    """The green bottle (the confirmed colour-fetch target) must sit at the SAME (10.88, 3.0)
    it does in the house — a moved target would break the tuned grasp reach and the oracle
    GT, making the new-world re-verify a different (unfair) experiment."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "warehouse")
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    bid = _body_id(go2, "pickable_bottle_green")
    assert bid >= 0
    x, y, _z = (float(v) for v in go2._mj.model.body_pos[bid])
    assert abs(x - 10.88) < 1e-6 and abs(y - 3.00) < 1e-6, (
        f"green bottle moved to ({x}, {y}); must stay at house coords (10.88, 3.00)"
    )


def test_warehouse_has_distinct_shell_geoms(monkeypatch):
    """The world is genuinely NEW: it carries the warehouse-signature geoms (steel perimeter
    + orange racking) that do NOT exist in the house, and NONE of the house's room geoms."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "warehouse")
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    for name in ("ww_south", "ww_north", "ww_west", "ww_east", "rack_up_a"):
        assert _geom_id(go2, name) >= 0, f"warehouse must have {name}"
    # House-only geoms must be absent (proves the shell was actually swapped).
    for name in ("bb_south", "df_living_l", "iw_l1"):
        assert _geom_id(go2, name) < 0, f"house geom {name} leaked into the warehouse"


def test_select_courtyard(monkeypatch):
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "courtyard")
    assert _select_room_template() == _ROOM_TEMPLATES["courtyard"]


def test_courtyard_template_file_exists():
    assert _ROOM_TEMPLATES["courtyard"].exists()
    xml = _ROOM_TEMPLATES["courtyard"].read_text()
    for tok in ("GO2_MODEL_PATH", "GO2_ASSETS_DIR", "GRASP_WELDS"):
        assert tok in xml, f"courtyard template must carry the {tok} token"


def test_courtyard_compiles_with_all_pickables(monkeypatch):
    """VECTOR_ROOM_TEMPLATE=courtyard: the 3rd world compiles and every tuned pickable body
    is present at its coordinates — the grasp/perception face stays reachable."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "courtyard")
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    for name in _PICKABLES:
        assert _body_id(go2, name) >= 0, f"{name} must exist in the courtyard world"
    for name in ("pick_table", "place_bin"):
        assert _body_id(go2, name) >= 0, f"{name} must exist in the courtyard world"


def test_courtyard_green_bottle_at_house_coordinates(monkeypatch):
    """The green bottle must sit at the SAME (10.88, 3.0) it does in the house/warehouse — a
    moved target would break the tuned grasp reach and the oracle GT, making the new-world
    re-verify a different (unfair) experiment."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "courtyard")
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    bid = _body_id(go2, "pickable_bottle_green")
    assert bid >= 0
    x, y, _z = (float(v) for v in go2._mj.model.body_pos[bid])
    assert abs(x - 10.88) < 1e-6 and abs(y - 3.00) < 1e-6, (
        f"green bottle moved to ({x}, {y}); must stay at house coords (10.88, 3.00)"
    )


def test_courtyard_has_distinct_shell_geoms(monkeypatch):
    """The world is genuinely NEW: it carries the courtyard-signature geoms (sandstone
    perimeter + timber pergola + stone fountain) that exist in NEITHER the house NOR the
    warehouse, and none of either prior world's shell geoms."""
    monkeypatch.setenv("VECTOR_ROOM_TEMPLATE", "courtyard")
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    for name in ("cw_south", "cw_north", "cw_west", "cw_east", "perg_post_a", "fnt_base"):
        assert _geom_id(go2, name) >= 0, f"courtyard must have {name}"
    # House-only and warehouse-only geoms must both be absent (proves a real 3rd shell).
    for name in ("bb_south", "df_living_l", "ww_south", "rack_up_a"):
        assert _geom_id(go2, name) < 0, f"foreign shell geom {name} leaked into the courtyard"


def test_default_env_is_the_house(monkeypatch):
    """Unset knob → the frozen house: its signature geoms are present, warehouse ones absent
    (guards the byte-identical default against silent drift)."""
    monkeypatch.delenv("VECTOR_ROOM_TEMPLATE", raising=False)
    monkeypatch.delenv("VECTOR_SIM_WITH_ARM", raising=False)
    go2 = MuJoCoGo2(gui=False, room=True)
    go2.connect()
    assert _geom_id(go2, "bb_south") >= 0, "house baseboard must exist by default"
    assert _geom_id(go2, "ww_south") < 0, "warehouse wall must be absent by default"
