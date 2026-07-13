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
# v2 (2026-07-13): the old TWO-step '启动导航栈,站起来,打开 rviz' few-shot
# silently dropped the rviz clause; it is REPLACED by a COMPLETE three-step
# compound ('启动导航栈,打开 rviz,站起来' -> bringup + open_viz + standup,
# chained) so the planner learns no clause is ever dropped. Two turn few-shots
# (左转90度 -> turned(54); 掉头 -> turned(108)) are appended below.
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

# Lifecycle disambiguation (first-REPL-contact, 2026-07-10): "启动导航栈"
# decomposed to standup_skill (启动≈站立). The bringup few-shot pins the
# lifecycle strategy; posture stays with standup/liedown.
REAL_DECOMPOSE_EXAMPLES += """

Task: "启动导航栈"
Response:
{
  "goal": "启动导航栈",
  "sub_goals": [
    {
      "name": "bringup_stack",
      "description": "启动导航栈并等待 SLAM 就绪(这是栈的生命周期,不是站立)",
      "verify": "stack_ready()",
      "strategy": "bringup_skill",
      "timeout_sec": 200,
      "depends_on": [],
      "strategy_params": {"action": "start"},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}

Task: "启动导航栈,打开 rviz,站起来"   (a COMPOUND request — EVERY clause becomes a step; drop none)
Response:
{
  "goal": "启动导航栈,打开 rviz,站起来",
  "sub_goals": [
    {
      "name": "bringup_stack",
      "description": "启动导航栈并等待就绪(生命周期)",
      "verify": "stack_ready()",
      "strategy": "bringup_skill",
      "timeout_sec": 200,
      "depends_on": [],
      "strategy_params": {"action": "start"},
      "fail_action": ""
    },
    {
      "name": "open_rviz",
      "description": "打开 rviz 让操作员观察(open_viz 是策略,不是被丢弃的子句)",
      "verify": "True",
      "strategy": "open_viz_skill",
      "timeout_sec": 30,
      "depends_on": ["bringup_stack"],
      "strategy_params": {"view": "main"},
      "fail_action": ""
    },
    {
      "name": "stand_up",
      "description": "起立(姿态,非生命周期)",
      "verify": "True",
      "strategy": "standup_skill",
      "timeout_sec": 30,
      "depends_on": ["open_rviz"],
      "strategy_params": {},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""

# Motion goes STRAIGHT to motion skills — never via bringup (field trace
# 2026-07-10: '往前走3米' routed through bringup(start) and restarted the
# live stack). bringup appears ONLY when the goal is about the stack itself.
REAL_DECOMPOSE_EXAMPLES += """

Task: "往前走 3 米"
Response:
{
  "goal": "往前走 3 米",
  "sub_goals": [
    {
      "name": "walk_forward",
      "description": "向前相对移动 3 米(栈已在跑,直接运动,无需 bringup)",
      "verify": "moved(2.0)",
      "strategy": "move_relative_skill",
      "timeout_sec": 60,
      "depends_on": [],
      "strategy_params": {"direction": "forward", "distance": 3.0},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""

# Single-action commands are SINGLE steps (field trace 2026-07-10 15:19: the
# planner gave 站起来 a 7-step plan including liedown-first and a restart).
REAL_DECOMPOSE_EXAMPLES += """

Task: "站起来"
Response:
{
  "goal": "站起来",
  "sub_goals": [
    {
      "name": "stand_up",
      "description": "起立(单步;不需要 liedown/bringup/其他前置)",
      "verify": "True",
      "strategy": "standup_skill",
      "timeout_sec": 30,
      "depends_on": [],
      "strategy_params": {},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""

# In-place rotation goes STRAIGHT to turn_skill — NO bringup (odometry already
# flows; field trace 2026-07-10 evening: '左转90度' had no rotation vocab at
# all). Verify hint = turned(round(0.6*degrees)): the wrapped heading delta
# caps at 180°, so 90°->turned(54), 掉头/180°->turned(108), never turned(180).
REAL_DECOMPOSE_EXAMPLES += """

Task: "左转90度"
Response:
{
  "goal": "左转90度",
  "sub_goals": [
    {
      "name": "turn_left_90",
      "description": "原地左转90度(栈在跑,直接旋转,无需 bringup)",
      "verify": "turned(54)",
      "strategy": "turn_skill",
      "timeout_sec": 30,
      "depends_on": [],
      "strategy_params": {"direction": "left", "degrees": 90},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}

Task: "掉头"
Response:
{
  "goal": "掉头",
  "sub_goals": [
    {
      "name": "u_turn",
      "description": "原地掉头(180度;单步旋转,无需 bringup)",
      "verify": "turned(108)",
      "strategy": "turn_skill",
      "timeout_sec": 30,
      "depends_on": [],
      "strategy_params": {"direction": "left", "degrees": 180},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""
