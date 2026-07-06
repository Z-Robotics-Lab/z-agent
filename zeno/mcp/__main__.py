# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Entry point: python -m zeno.mcp

Runs the MCP server with stdio transport so Claude Code can communicate
with the Vector OS Nano simulated robot.

Examples:
    python -m zeno.mcp                 # headless sim (default)
    python -m zeno.mcp --sim            # sim with viewer
    python -m zeno.mcp --sim-headless   # headless sim (explicit)
"""

import asyncio

from zeno.mcp.server import main

asyncio.run(main())
