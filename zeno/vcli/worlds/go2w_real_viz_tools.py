# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real viz tool — the agent opens/closes RViz for the operator.

Product doctrine (CEO, 2026-07-10): the bare ``zeno`` CLI is the only surface
during agent testing — the agent itself brings up visualization. RViz runs as a
non-blocking overlay child via ``nav.sh rviz*`` (which exports DISPLAY for the
robot's Moonlight-viewable desktop), reusing :class:`OverlayLauncher`'s
SIGINT-only, never-kill-infra lifecycle.
"""

from __future__ import annotations

from typing import Any, Callable

from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher
from zeno.vcli.tools.base import ToolContext, ToolResult, tool

#: view name (agent-facing) -> nav.sh subcommand (one overlay per view).
_VIEWS: dict[str, str] = {
    "main": "rviz",
    "explore": "rviz-explore",
    "route": "rviz-route",
}


@tool(
    name="go2w_real_viz",
    description=(
        "Open or close RViz on the robot's desktop so the operator can watch "
        "(Moonlight/local screen). action: open (view: main|explore|route — "
        "match the running planner), close (closes all views). Non-blocking; "
        "RViz runs as a background child. 给操作者打开/关闭 RViz 可视化。"),
    read_only=False,
    permission="allow",
)
class Go2WRealVizTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["open", "close"],
                       "default": "open"},
            "view": {"type": "string", "enum": sorted(_VIEWS),
                     "default": "main"},
        },
    }

    def __init__(self, popen_factory: Callable[..., Any] | None = None,
                 nav_sh: str | None = None) -> None:
        self._popen_factory = popen_factory
        self._nav_sh = nav_sh
        self._launchers: dict[str, OverlayLauncher] = {}

    # ------------------------------------------------------------------
    def _launcher(self, mode: str) -> OverlayLauncher:
        if mode not in self._launchers:
            self._launchers[mode] = OverlayLauncher(
                mode, nav_sh=self._nav_sh, popen_factory=self._popen_factory)
        return self._launchers[mode]

    def _open(self, view: str) -> ToolResult:
        mode = _VIEWS.get(view)
        if mode is None:
            return ToolResult(
                content=f"unknown view {view!r}; valid: {sorted(_VIEWS)}",
                is_error=True)
        launched, detail = self._launcher(mode).launch()
        if launched:
            return ToolResult(content=(
                f"RViz ({view}) opening on the robot desktop — visible via "
                f"Moonlight or the local screen. {detail}"))
        if "already running" in detail:
            return ToolResult(content=f"RViz ({view}) is already open. {detail}")
        return ToolResult(content=f"could not open RViz ({view}): {detail}",
                          is_error=True)

    def _close(self) -> ToolResult:
        closed: list[str] = []
        stuck: list[str] = []
        for mode, launcher in self._launchers.items():
            if not launcher.is_running():
                continue
            clean, _rc = launcher.stop()
            (closed if clean else stuck).append(mode)
        if stuck:
            return ToolResult(content=(
                f"closed {closed or 'nothing'}; still running (needs manual "
                f"attention): {stuck}"), is_error=True)
        if not closed:
            return ToolResult(content="no RViz view was open — nothing to close.")
        return ToolResult(content=f"closed RViz views: {', '.join(closed)}.")

    # ------------------------------------------------------------------
    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        params = params or {}
        action = params.get("action", "open")
        if action == "open":
            return self._open(params.get("view", "main"))
        if action == "close":
            return self._close()
        return ToolResult(content=(
            f"unknown action {action!r}; valid: ['open', 'close']"),
            is_error=True)
