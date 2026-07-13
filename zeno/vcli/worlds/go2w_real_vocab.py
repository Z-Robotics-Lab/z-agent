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

# NOTE: the ``route_via_skill`` example teaches global route planning for a
# FAR cross-map goal (verify with route_reached()).
# v2 (2026-07-13): the old TWO-step '启动导航栈,站起来,打开 rviz' few-shot
# silently dropped the rviz clause; it is REPLACED by a COMPLETE three-step
# compound ('启动导航栈,打开 rviz,站起来' -> bringup + open_viz + standup,
# chained) so the planner learns no clause is ever dropped. Two turn few-shots
# (左转90度 -> turned(54); 掉头 -> turned(108)) are appended below.
# PRUNED for the ~6000-char budget (places round, 2026-07-13 night): the old
# '往前走2米' target-math example (后退1米 teaches the same math + at() verify,
# and the planner_intro spells the formula out) and the '站起来' single-step
# example (左转90度/掉头/后退1米/往前走 3 米 all pin single-step already).
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

# Reverse move is ONE relative step {direction: backward} — verify at() on the
# computed target (field trace 2026-07-13: the semantics are correct even while
# the nav-stack reverse-drive fix is still landing; the skill fails HONESTLY,
# and its error names the 掉头+前进 workaround). NO bringup (stack already runs).
REAL_DECOMPOSE_EXAMPLES += """

Task: "后退1米"   (world context: "Position: (2.0, 1.0)\\nHeading: 0.0 rad")
Target math: backward = heading+pi, tx = 2.0 + 1*cos(pi) = 1.0, ty = 1.0.
Response:
{
  "goal": "后退1米",
  "sub_goals": [
    {
      "name": "move_backward_1m",
      "description": "向后相对移动 1 米(栈在跑,直接运动,无需 bringup)",
      "verify": "at(1.0, 1.0, tol=1.0)",
      "strategy": "move_relative_skill",
      "timeout_sec": 60,
      "depends_on": [],
      "strategy_params": {"direction": "backward", "distance": 1},
      "fail_action": ""
    }
  ],
  "context_snapshot": "Position: (2.0, 1.0), Heading: 0.0 rad"
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

# Multi-leg RELATIVE plans (square path — field bug 2026-07-13 evening): each
# clause is its own move/turn step. turn_skill executes turns relative to the
# INTENDED course (drift folded into the commanded delta; re-anchors past 45°),
# so the plan stays square — grade the alignment with course_locked().
REAL_DECOMPOSE_EXAMPLES += """

Task: "前进2米,右转90度"   (multi-leg relative plan — the turn is 90° off the INTENDED course; turn_skill compensates heading drift itself)
Response:
{
  "goal": "前进2米,右转90度",
  "sub_goals": [
    {
      "name": "leg_1",
      "description": "沿预期航向前进2米",
      "verify": "moved(1.2)",
      "strategy": "move_relative_skill",
      "timeout_sec": 60,
      "depends_on": [],
      "strategy_params": {"direction": "forward", "distance": 2.0},
      "fail_action": ""
    },
    {
      "name": "turn_1",
      "description": "右转90度(相对预期航向,漂移自动补偿)",
      "verify": "turned(54) and course_locked()",
      "strategy": "turn_skill",
      "timeout_sec": 30,
      "depends_on": ["leg_1"],
      "strategy_params": {"direction": "right", "degrees": 90},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""

# Spatial session memory (CEO directive 2026-07-13 night: '回到刚才的位置'
# had NOTHING to resolve against — the model improvised coordinates from
# conversation text). goto_place resolves 起点/刚才/marked names from the
# odometry-recorded ledger; mark_place names the current pose. The at() verify
# uses the origin the where/world context reports — never an invented number.
REAL_DECOMPOSE_EXAMPLES += """

Task: "回到起点"   (world context: 起点 origin recorded at (0.0, 0.0))
Response:
{
  "goal": "回到起点",
  "sub_goals": [
    {
      "name": "return_to_origin",
      "description": "回到会话起点(台账自动记录的里程计位姿,单步,无需 bringup)",
      "verify": "at(0.0, 0.0, tol=1.0)",
      "strategy": "goto_place_skill",
      "timeout_sec": 180,
      "depends_on": [],
      "strategy_params": {"name": "起点"},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}

Task: "记住这里叫充电桩"
Response:
{
  "goal": "记住这里叫充电桩",
  "sub_goals": [
    {
      "name": "mark_charger",
      "description": "把当前里程计位姿记为地点“充电桩”(坐标来自里程计,单步)",
      "verify": "True",
      "strategy": "mark_place_skill",
      "timeout_sec": 15,
      "depends_on": [],
      "strategy_params": {"name": "充电桩"},
      "fail_action": ""
    }
  ],
  "context_snapshot": ""
}"""
