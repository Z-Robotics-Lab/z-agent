# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Novel-CATEGORY plug-in (R212): a 5th pickable — a PURPLE BOX — enters the go2
scene as CONFIG + data. Unlike R211's yellow bottle (a new COLOUR on the frozen
cylinder shape), this is the FIRST non-cylinder GEOMETRY: it proves the grounding
pipeline is not hard-wired to cylinders either. Same 5-site plug-in surface as
yellow, ZERO kernel edits: HSV band, NL colour aliases (zh + en), verify-oracle
scene-name map, MJCF body (type="box") + grasp weld. See LESSONS Frontier / E45.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from vector_os_nano.perception.front_object import (
    _COLOR_HUE,
    front_object_mask,
    parse_color,
)
from vector_os_nano.skills.perception_grasp import _COLOR_TO_SCENE

_ROOT = Path(__file__).resolve().parents[3]
# The SOURCE room template (attached + compiled at connect); scene_room_piper.xml is
# the GENERATED output, overwritten each build — never the source of truth (E45 gotcha).
_ROOM_TEMPLATE = _ROOT / "vector_os_nano/hardware/sim/go2_room.xml"
# The grasp weld is added programmatically from this driver tuple, not the XML.
_GO2_DRIVER = _ROOT / "vector_os_nano/hardware/sim/mujoco_go2.py"
_PURPLE_NAME = "pickable_box_purple"


def test_parse_color_purple_zh_and_en():
    assert parse_color("把紫色的盒子拿过来") == "purple"
    assert parse_color("抓紫色的") == "purple"
    assert parse_color("the purple box") == "purple"


def test_purple_hue_band_disjoint_from_rgby():
    """Purple (hue ~152 in OpenCV 0..180) must not overlap red/green/blue/yellow
    bands, else the HSV resolver would confuse a 5th colour with an existing one."""
    assert "purple" in _COLOR_HUE
    others = ("red", "green", "blue", "yellow")
    bands = {c: _COLOR_HUE[c] for c in (*others, "purple")}

    def _covers(colour, hue):
        return any(lo <= hue <= hi for lo, hi in bands[colour])

    # Every hue in the purple band belongs to purple ALONE.
    for lo, hi in bands["purple"]:
        for hue in range(lo, hi + 1):
            for other in others:
                assert not _covers(other, hue), (
                    f"purple hue {hue} also matches {other}"
                )


def test_verify_map_has_purple():
    assert _COLOR_TO_SCENE.get("purple") == _PURPLE_NAME


def _muted_bg(h=48, w=64):
    rgb = np.full((h, w, 3), 130, dtype=np.uint8)
    rgb[:, :, 0] += 5
    return rgb


def _put_blob(rgb, cx, cy, color, r=6):
    h, w, _ = rgb.shape
    for v in range(max(0, cy - r), min(h, cy + r)):
        for u in range(max(0, cx - r), min(w, cx + r)):
            rgb[v, u] = color


def test_front_object_mask_selects_purple_over_blue():
    """Among a purple and a blue blob, color='purple' selects the purple one —
    the near-in-hue neighbour is the discrimination stress (blue band tops at 135,
    purple starts at 140)."""
    rgb = _muted_bg()
    _put_blob(rgb, 20, 24, (191, 26, 179))   # vivid purple (rgb .75/.10/.70), left
    _put_blob(rgb, 44, 24, (51, 102, 217))   # vivid blue, right
    depth = np.full((48, 64), 1.0, dtype=np.float32)
    m = front_object_mask(rgb, depth, color="purple")
    assert m is not None and int(m.sum()) > 0
    xs = np.where(m > 0)[1]
    assert abs(xs.mean() - 20) < 8, "purple mask should sit on the LEFT blob"


def test_source_room_declares_purple_box_body():
    xml = _ROOM_TEMPLATE.read_text()
    assert f'name="{_PURPLE_NAME}"' in xml, "purple box body missing from room template"
    # The novelty is GEOMETRY: the body must carry a box geom, not a cylinder.
    body_idx = xml.index(f'name="{_PURPLE_NAME}"')
    body_tail = xml[body_idx:body_idx + 400]
    assert 'type="box"' in body_tail, "purple object must be a BOX (new geometry), not a cylinder"


def test_driver_registers_purple_box_grasp_weld():
    src = _GO2_DRIVER.read_text()
    assert f'"grasp_{_PURPLE_NAME}", "piper_link6", "{_PURPLE_NAME}"' in src, (
        "purple box grasp weld missing from MuJoCoGo2 welds tuple"
    )
