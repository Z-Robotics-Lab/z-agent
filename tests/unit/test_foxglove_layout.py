# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Foxglove dashboard layout — structural integrity guards.

The layout JSON is hand-edited config; these guards catch the failure modes
that silently break it in the app: a layout-tree node referencing a panel id
that has no config (blank panel), a Tab referencing a missing child, a ghost
topic (typo'd / removed from the nav stack), and the D184 identity rule
(no vector-branded strings in a user-facing artifact).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_LAYOUT = Path(__file__).resolve().parents[2] / "foxglove" / "zeno-go2w-dashboard.json"

# Topics verified against ~/Z-Navigation-Stack + go2w-nuc + zeno driver sources
# (2026-07-14). If the stack renames one, update BOTH the layout and this list.
_KNOWN_TOPICS = {
    "/prior_map_color", "/registered_scan", "/overall_map", "/sensor_scan",
    "/terrain_map", "/terrain_map_ext", "/added_obstacles", "/trajectory",
    "/free_paths", "/explored_areas", "/path", "/way_point", "/goal_point",
    "/state_estimation", "/navigation_boundary", "/nogo_boundary",
    "/viz_graph_topic", "/camera/camera/color/image_raw", "/camera/camera/depth/image_rect_raw",
    "/camera/semantic_image/compressed", "/cmd_vel", "/cmd_vel_safe",
    "/imu/data", "/far_reach_goal_status", "/exploration_finish", "/place_markers",
}

_MUST_SHOW = {
    "/prior_map_color", "/registered_scan", "/state_estimation", "/path",
    "/way_point", "/goal_point", "/camera/camera/color/image_raw",
}


@pytest.fixture(scope="module")
def layout() -> dict:
    return json.loads(_LAYOUT.read_text(encoding="utf-8"))


def _tree_panel_ids(node) -> set[str]:
    if isinstance(node, str):
        return {node}
    if isinstance(node, dict):
        return _tree_panel_ids(node.get("first")) | _tree_panel_ids(node.get("second"))
    return set()


def test_layout_parses_and_has_panels(layout: dict) -> None:
    assert layout["configById"]
    assert layout["layout"]


def test_every_layout_node_has_a_panel_config(layout: dict) -> None:
    ids = _tree_panel_ids(layout["layout"])
    missing = ids - set(layout["configById"])
    assert not missing, f"layout tree references unconfigured panels: {missing}"


def test_tab_children_exist(layout: dict) -> None:
    for pid, cfg in layout["configById"].items():
        if pid.startswith("Tab!"):
            for tab in cfg.get("tabs", []):
                child = tab.get("layout")
                assert child in layout["configById"], f"{pid} tab -> missing {child}"


def test_all_topics_are_known(layout: dict) -> None:
    used: set[str] = set()
    for cfg in layout["configById"].values():
        used.update(cfg.get("topics", {}).keys())
        if cfg.get("cameraTopic"):
            used.add(cfg["cameraTopic"])
        for path in cfg.get("paths", []):
            used.add("/" + path["value"].lstrip("/").split(".", 1)[0])
        if cfg.get("topicPath"):
            used.add("/" + cfg["topicPath"].lstrip("/").split(".", 1)[0])
    ghosts = used - _KNOWN_TOPICS
    assert not ghosts, f"layout references topics not in the verified stack list: {ghosts}"


def test_key_sensors_present(layout: dict) -> None:
    used: set[str] = set()
    for cfg in layout["configById"].values():
        used.update(cfg.get("topics", {}).keys())
        if cfg.get("cameraTopic"):
            used.add(cfg["cameraTopic"])
    assert _MUST_SHOW <= used, f"missing key sensors: {_MUST_SHOW - used}"


def test_no_vector_branding() -> None:
    text = _LAYOUT.read_text(encoding="utf-8")
    assert not re.search(r"vector", text, re.I)


def test_publish_targets_the_operator_waypoint_seam(layout: dict) -> None:
    # Click-to-publish must go to the SAME topics the operator-override seam
    # already tolerates (/way_point + /goal_point) — never a new interface.
    for pid, cfg in layout["configById"].items():
        pub = cfg.get("publish")
        if pub:
            assert pub["pointTopic"] == "/way_point", pid
            assert pub["poseTopic"] == "/goal_point", pid
