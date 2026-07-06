# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Novel-object plug-in (R211/E45): a 4th pickable — a YELLOW bottle — enters the
go2 scene as CONFIG + data, proving the colour-grounding pipeline is not hard-wired
to the frozen red/green/blue triple. This test pins every site the object touches so
the plug-in surface stays honest (and any regression is loud): the HSV colour band,
the NL colour aliases (zh + en), the verify-oracle scene-name map, and the scene MJCF
body + grasp weld. See docs/WIRING.md embodiments / LESSONS Frontier.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from zeno.perception.front_object import (
    _COLOR_HUE,
    front_object_mask,
    parse_color,
)
from zeno.skills.perception_grasp import _COLOR_TO_SCENE

_ROOT = Path(__file__).resolve().parents[3]
# The SOURCE room template (attached + compiled at connect); scene_room_piper.xml is
# the GENERATED output, overwritten each build — never the source of truth.
_ROOM_TEMPLATE = _ROOT / "zeno/hardware/sim/go2_room.xml"
# The grasp weld is added programmatically from this driver tuple, not the XML.
_GO2_DRIVER = _ROOT / "zeno/hardware/sim/mujoco_go2.py"
_YELLOW_NAME = "pickable_bottle_yellow"


def test_parse_color_yellow_zh_and_en():
    assert parse_color("把黄色的瓶子拿过来") == "yellow"
    assert parse_color("抓黄色的") == "yellow"
    assert parse_color("the yellow bottle") == "yellow"


def test_yellow_hue_band_disjoint_from_rgb():
    """Yellow (hue ~27 in OpenCV 0..180) must not overlap red/green/blue bands,
    else the HSV resolver would confuse a 4th colour with an existing one."""
    assert "yellow" in _COLOR_HUE
    bands = {c: _COLOR_HUE[c] for c in ("red", "green", "blue", "yellow")}

    def _covers(colour, hue):
        return any(lo <= hue <= hi for lo, hi in bands[colour])

    # Every hue in the yellow band belongs to yellow ALONE.
    for lo, hi in bands["yellow"]:
        for hue in range(lo, hi + 1):
            for other in ("red", "green", "blue"):
                assert not _covers(other, hue), (
                    f"yellow hue {hue} also matches {other}"
                )


def test_verify_map_has_yellow():
    assert _COLOR_TO_SCENE.get("yellow") == _YELLOW_NAME


def _muted_bg(h=48, w=64):
    rgb = np.full((h, w, 3), 130, dtype=np.uint8)
    rgb[:, :, 0] += 5
    return rgb


def _put_blob(rgb, cx, cy, color, r=6):
    h, w, _ = rgb.shape
    for v in range(max(0, cy - r), min(h, cy + r)):
        for u in range(max(0, cx - r), min(w, cx + r)):
            rgb[v, u] = color


def test_front_object_mask_selects_yellow_over_green():
    """Among a yellow and a green blob, color='yellow' selects the yellow one."""
    rgb = _muted_bg()
    _put_blob(rgb, 20, 24, (242, 217, 13))   # vivid yellow, left
    _put_blob(rgb, 44, 24, (30, 200, 40))    # vivid green, right
    depth = np.full((48, 64), 1.0, dtype=np.float32)
    m = front_object_mask(rgb, depth, color="yellow")
    assert m is not None and int(m.sum()) > 0
    xs = np.where(m > 0)[1]
    assert abs(xs.mean() - 20) < 8, "yellow mask should sit on the LEFT blob"


def test_source_room_declares_yellow_body():
    xml = _ROOM_TEMPLATE.read_text()
    assert f'name="{_YELLOW_NAME}"' in xml, "yellow body missing from room template"


def test_driver_registers_yellow_grasp_weld():
    src = _GO2_DRIVER.read_text()
    assert f'"grasp_{_YELLOW_NAME}", "piper_link6", "{_YELLOW_NAME}"' in src, (
        "yellow grasp weld missing from MuJoCoGo2 welds tuple"
    )
