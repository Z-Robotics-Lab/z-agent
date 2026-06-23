# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R4 — route the learned grounding-dino DETECTOR to g1's HEAD camera (no-arm).

Covers the NON-cognitive wiring that lets a bare-cli detect command reach the
SECOND model family on the SECOND embodiment (cross-EMBODIMENT x cross-MODEL):

  1. ``RobotWorld.build_verify_namespace`` binds a perception-fed ``detect_objects``
     oracle for a camera-only (no-arm) agent, reading the LEARNED detector's last
     observation (``agent._last_detection``) — truth-bearing, RAN-honest.
  2. The native ``_NativeDetectTool`` routes a query to the registered capability,
     stashes the boxes on the agent, and reports them (no second model load).
  3. ``_registered_capability`` reaches the live CapabilityRegistry via the engine
     executor; ``_build_motor_tools`` surfaces ``detect`` only when registered.

The grounding-dino model is FAKED (a stub capability) — these tests prove the
WIRING/route, not the model's perception (that is the real-sim REAL-VERIFY).
"""
from __future__ import annotations

from typing import Any

from vector_os_nano.vcli.native_loop import (
    _NativeDetectTool,
    _build_motor_tools,
    _registered_capability,
)
from vector_os_nano.vcli.worlds.robot import RobotWorld


# --- fakes -----------------------------------------------------------------
class _Box:
    """A CapabilityResult-shaped stub (success + output)."""

    def __init__(self, success: bool, output: dict[str, Any]):
        self.success = success
        self.output = output
        self.error = ""


class _StubDetectCap:
    """Stands in for the registered grounding-dino DetectorCapability."""

    name = "detect"
    kind = "detector"
    side_effecting = False

    def __init__(self, detections):
        self._detections = detections
        self.last_query = None

    def invoke(self, payload, context):
        self.last_query = payload.get("query")
        if not self._detections:
            return _Box(False, {"boxes": [], "labels": [], "scores": []})
        return _Box(
            True,
            {
                "boxes": [list(d[1]) for d in self._detections],
                "labels": [d[0] for d in self._detections],
                "scores": [d[2] for d in self._detections],
            },
        )


class _G1Base:
    def get_camera_frame(self, width=640, height=480):
        import numpy as np

        return np.zeros((height, width, 3), dtype=np.uint8)

    def get_position(self):
        return (10.0, 3.0, 0.79)

    def get_heading(self):
        return 0.0


class _G1Agent:
    def __init__(self):
        self._arm = None
        self._base = _G1Base()
        self._perception = object()  # presence only; the stub cap ignores it


class _Ctx:
    def __init__(self, agent):
        self.agent = agent


class _Registry:
    def __init__(self, cap):
        self._cap = cap

    def get(self, name):
        return self._cap if name == "detect" else None


class _Executor:
    def __init__(self, cap):
        self._capability_registry = _Registry(cap)


class _Engine:
    def __init__(self, cap=None, registry=None):
        self._goal_executor = _Executor(cap) if cap is not None else None
        self._registry = registry  # for code-tool discovery (None -> none)


# --- 1. verify oracle: perception-fed detect_objects for g1 ----------------
def test_g1_verify_namespace_has_perceived_detect_objects():
    """A camera-only (no-arm) g1 gets a detect_objects oracle (the arm path never did)."""
    ns = RobotWorld().build_verify_namespace(_G1Agent())
    assert "detect_objects" in ns
    assert "at_position" in ns  # base predicates still present


def test_perceived_detect_objects_reads_last_detection():
    agent = _G1Agent()
    ns = RobotWorld().build_verify_namespace(agent)
    detect_objects = ns["detect_objects"]
    # No detection yet -> empty (NEVER a truthy stub).
    assert detect_objects() == []
    # The learned route stashes its observation; the oracle reflects it.
    agent._last_detection = {
        "query": "red object",
        "boxes": [[100.0, 120.0, 260.0, 380.0]],
        "labels": ["a red object"],
        "scores": [0.71],
    }
    got = detect_objects()
    assert len(got) == 1 and got[0]["name"] == "a red object"
    assert got[0]["score"] == 0.71
    # len(detect_objects()) > 0 is now truth-bearing for the verify spine.
    assert len(detect_objects()) > 0


def test_perceived_detect_objects_filters_by_query_and_fails_safe():
    agent = _G1Agent()
    detect_objects = RobotWorld().build_verify_namespace(agent)["detect_objects"]
    agent._last_detection = {
        "boxes": [[0, 0, 1, 1], [2, 2, 3, 3]],
        "labels": ["a red stool", "a blue cup"],
        "scores": [0.6, 0.5],
    }
    assert len(detect_objects("red")) == 1
    assert detect_objects("nonexistent") == []
    agent._last_detection = "garbage"  # malformed -> fail safe, never raise
    assert detect_objects() == []


def test_arm_agent_keeps_ground_truth_detect_objects():
    """An agent with an arm must keep its GROUND-TRUTH detect_objects (the moat anchor),
    NOT be overwritten by the perception-fed means output."""

    class _Arm:
        def get_object_positions(self):
            return {"pickable_can_red": (1.0, 2.0, 0.3)}

    class _ArmAgent:
        def __init__(self):
            self._arm = _Arm()
            self._base = None
            self._perception = None

    ns = RobotWorld().build_verify_namespace(_ArmAgent())
    # arm path bound it; the no-arm camera branch must not have run.
    assert "detect_objects" in ns
    got = ns["detect_objects"]()
    assert got and got[0]["name"] == "pickable_can_red"  # ground truth, not _last_detection


# --- 2. native detect tool routes to the capability ------------------------
def test_native_detect_tool_routes_and_stashes():
    cap = _StubDetectCap([("a red object", (100, 120, 260, 380), 0.73)])
    tool = _NativeDetectTool(cap)
    agent = _G1Agent()
    res = tool.execute({"query": "找前面的红色的东西"}, _Ctx(agent))
    assert not res.is_error
    assert cap.last_query == "找前面的红色的东西"
    # boxes stashed for the verify oracle (rule 4: observation flows).
    assert agent._last_detection["boxes"] == [[100, 120, 260, 380]]
    assert "grounding-dino localized 1 object" in res.content


def test_native_detect_tool_empty_query_errors():
    tool = _NativeDetectTool(_StubDetectCap([]))
    res = tool.execute({"query": "  "}, _Ctx(_G1Agent()))
    assert res.is_error


def test_native_detect_tool_nothing_localized_is_honest():
    cap = _StubDetectCap([])  # detector ran, found nothing
    tool = _NativeDetectTool(cap)
    agent = _G1Agent()
    res = tool.execute({"query": "red object"}, _Ctx(agent))
    assert not res.is_error
    assert "localized nothing" in res.content
    assert agent._last_detection["boxes"] == []  # honest empty, never fabricated


# --- 3. registry reach + motor-tool surfacing ------------------------------
def test_registered_capability_reaches_live_registry():
    cap = _StubDetectCap([])
    assert _registered_capability(_Engine(cap=cap), "detect") is cap
    assert _registered_capability(_Engine(cap=cap), "missing") is None
    assert _registered_capability(_Engine(cap=None), "detect") is None  # no executor


def test_build_motor_tools_surfaces_detect_when_registered():
    cap = _StubDetectCap([("x", (0, 0, 1, 1), 0.5)])
    tools = _build_motor_tools(_G1Agent(), _Engine(cap=cap))
    assert "detect" in tools
    assert isinstance(tools["detect"], _NativeDetectTool)
    assert "navigate" in tools  # g1 has a base -> the avoidance route too


def test_build_motor_tools_no_detect_when_unregistered():
    tools = _build_motor_tools(_G1Agent(), _Engine(cap=None))
    assert "detect" not in tools
