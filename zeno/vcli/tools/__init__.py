# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""vcli.tools — Tool registry and discovery for Zeno's agentic harness."""
from __future__ import annotations

from zeno.vcli.tools.base import (
    CategorizedToolRegistry,
    PermissionResult,
    Tool,
    ToolContext,
    ToolRegistry,
    ToolResult,
    tool,
)

__all__ = [
    "CategorizedToolRegistry",
    "PermissionResult",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "tool",
    "discover_all_tools",
    "discover_categorized_tools",
]


def discover_all_tools() -> list:
    """Instantiate and return all built-in tool objects (flat list, backward compat).

    Each tool class is imported here to avoid circular imports at module level.
    The caller registers the returned instances into a ToolRegistry.
    """
    from zeno.vcli.tools.bash_tool import BashTool
    from zeno.vcli.tools.file_tools import FileEditTool, FileReadTool, FileWriteTool
    from zeno.vcli.tools.robot import RobotStatusTool, WorldQueryTool
    from zeno.vcli.tools.search_tools import GlobTool, GrepTool
    from zeno.vcli.tools.sim_tool import SimStartTool, SimStopTool
    # SysNav sim integration PAUSED — v2.4 T6 bridge-wiring + G5 launch not delivered; module + tests retained, re-register when v2.4 resumes (see progress.md).
    from zeno.vcli.tools.web_tool import WebFetchTool
    from zeno.vcli.tools.scene_graph_tool import SceneGraphQueryTool
    from zeno.vcli.tools.ros2_tools import Ros2TopicsTool, Ros2NodesTool, Ros2LogTool
    from zeno.vcli.tools.nav_tools import NavStateTool, TerrainStatusTool
    from zeno.vcli.tools.reload_tool import SkillReloadTool
    from zeno.vcli.tools.viz_tool import FoxgloveTool

    return [
        # Existing tools
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        BashTool(),
        GlobTool(),
        GrepTool(),
        WorldQueryTool(),
        RobotStatusTool(),
        SimStartTool(),
        SimStopTool(),
        WebFetchTool(),
        # New Wave 1-2 tools
        SceneGraphQueryTool(),
        Ros2TopicsTool(),
        Ros2NodesTool(),
        Ros2LogTool(),
        NavStateTool(),
        TerrainStatusTool(),
        SkillReloadTool(),
        FoxgloveTool(),
    ]


# Category assignments for CategorizedToolRegistry.
# "code" + "general" are the domain-general kernel toolset (work with no robot).
# "robot" / "diag" / "system" are robot-world tools (disabled when no robot agent).
_TOOL_CATEGORIES: dict[str, list[str]] = {
    "code": ["file_read", "file_write", "file_edit", "bash", "glob", "grep"],
    "general": ["web_fetch"],
    "robot": ["world_query", "scene_graph_query"],
    "diag": ["ros2_topics", "ros2_nodes", "ros2_log", "nav_state", "terrain_status"],
    # Sim lifecycle: kept enabled even in the dev (no-robot) world so the user can
    # spin up a sim conversationally ("start the arm sim").
    "sim": ["start_simulation", "stop_simulation"],
    "system": ["robot_status", "skill_reload", "open_foxglove"],
}


def discover_categorized_tools() -> tuple[list, dict[str, list[str]]]:
    """Return (tools_list, categories_dict) for CategorizedToolRegistry.

    Returns:
        Tuple of (list of tool instances, dict mapping category name to tool names).
    """
    tools = discover_all_tools()
    return tools, dict(_TOOL_CATEGORIES)
