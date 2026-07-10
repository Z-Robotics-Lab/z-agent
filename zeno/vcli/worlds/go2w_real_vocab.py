# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real decompose-vocab examples (split from go2w_real.py, files < 400 lines).

The few-shot decomposition examples the planner sees for the real Go2W world.
Kept out of ``go2w_real.py`` so its DecomposeVocab wiring stays under the repo's
400-line ceiling as the v2 feature seams (explore, route, ...) add vocabulary.
Content only — the world module owns the DecomposeVocab construction and the
append-only extension markers.
"""

from __future__ import annotations

# NOTE: the ``at``/``move_relative`` examples are unchanged from the v1 world;
# the ``route_via_skill`` example is added so the planner learns to pick global
# route planning for a FAR cross-map goal (verify with route_reached()).
REAL_DECOMPOSE_EXAMPLES = """\
Task: "站起来然后开到 (2.0, 3.0)"
Response:
{
  "goal": "站起来然后开到 (2.0, 3.0)",
  "sub_goals": [
    {
      "name": "stand_up",
      "description": "起立",
      "verify": "True",
      "strategy": "standup_skill",
      "timeout_sec": 30,
      "depends_on": [],
      "strategy_params": {},
      "fail_action": ""
    },
    {
      "name": "goto_target",
      "description": "导航到 (2.0, 3.0)",
      "verify": "at(2.0, 3.0)",
      "strategy": "navigate_skill",
      "timeout_sec": 180,
      "depends_on": ["stand_up"],
      "strategy_params": {"x": 2.0, "y": 3.0},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}

Task: "往前走2米"   (world context: "Position: (3.0, 2.0)\\nHeading: 1.6 rad")
Target math: tx = 3.0 + 2*cos(1.6) ≈ 2.9, ty = 2.0 + 2*sin(1.6) ≈ 4.0.
Response:
{
  "goal": "往前走2米",
  "sub_goals": [
    {
      "name": "move_forward_2m",
      "description": "往前走2米",
      "verify": "at(2.9, 4.0, tol=1.5)",
      "strategy": "move_relative_skill",
      "timeout_sec": 180,
      "depends_on": [],
      "strategy_params": {"distance": 2.0, "direction": "forward"},
      "fail_action": ""
    }
  ],
  "context_snapshot": "Position: (3.0, 2.0), Heading: 1.6 rad"
}

Task: "规划一条路线去 (12.0, -4.0)"   (a FAR goal across the map — use global route planning)
Response:
{
  "goal": "规划一条路线去 (12.0, -4.0)",
  "sub_goals": [
    {
      "name": "route_to_far_goal",
      "description": "far_planner 规划全局路线到 (12.0, -4.0)",
      "verify": "route_reached()",
      "strategy": "route_via_skill",
      "timeout_sec": 240,
      "depends_on": [],
      "strategy_params": {"x": 12.0, "y": -4.0},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""
