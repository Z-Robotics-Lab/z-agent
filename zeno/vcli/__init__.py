# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""vcli — Vector CLI agentic harness.

Public surface::

    from zeno.vcli import ToolRegistry, ToolResult, ToolContext, tool
"""
from __future__ import annotations

from zeno.vcli.tools.base import (
    PermissionResult,
    Tool,
    ToolContext,
    ToolRegistry,
    ToolResult,
    tool,
)
from zeno.vcli.tools import discover_all_tools

__all__ = [
    "discover_all_tools",
    "PermissionResult",
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "tool",
]
