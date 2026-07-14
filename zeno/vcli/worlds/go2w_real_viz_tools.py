# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real viz — shared RViz overlay session + the operator-facing tool.

Product doctrine (CEO, 2026-07-10): the bare ``zeno`` CLI is the only surface
during agent testing — the agent itself brings up visualization. RViz runs as a
non-blocking overlay child via ``nav.sh rviz*`` (which exports DISPLAY for the
robot's Moonlight-viewable desktop), reusing :class:`OverlayLauncher`'s
SIGINT-only, never-kill-infra lifecycle.

v2 (field trace 2026-07-10 evening): viz is ALSO a skill (``open_viz`` in
``go2w_real_ops_skills.py``) so VGG plans can orchestrate it — '启动导航,打开
rviz' used to silently drop the rviz half because tools are invisible to
strategy planning. The launcher table therefore lives in ONE shared
:class:`VizOverlaySession` (owned by the embodiment, ridden by tool AND skill)
so the two faces can never double-launch a view; opening an already-open view
dedupes to ok.
"""

from __future__ import annotations

import os
from typing import Any, Callable

from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher
from zeno.vcli.tools.base import ToolContext, ToolResult, tool

#: view name (agent-facing) -> nav.sh subcommand (one overlay per view).
_VIEWS: dict[str, str] = {
    "main": "rviz",
    "explore": "rviz-explore",
    "route": "rviz-route",
}

#: STANDALONE-SCRIPT views: view name -> a script the OverlayLauncher runs
#: DIRECTLY (empty mode), NOT a nav.sh subcommand. The 3D View3D stream
#: (彩色预建图 + 实时位姿, Foxglove) is built by the go2w-nuc half; contract-
#: first here (2026-07-14). Reuses the SAME OverlayLauncher machinery — dedupe
#: + close_all work identically — so the two viz stacks share one lifecycle.
_SCRIPT_VIEWS: dict[str, str] = {
    "3d": "~/go2w-nuc/scripts/view3d.sh",
}


class VizOverlaySession:
    """Session-scoped RViz overlay state — the ONE owner of view launchers.

    Both the ``go2w_real_viz`` TOOL and the ``open_viz`` SKILL act on the same
    instance (the embodiment's ``_viz``, ridden on the driver as
    ``base.viz_manager`` like the explore/route managers), so a view opened on
    either face is 'already open' on the other. ``popen_factory`` / ``nav_sh``
    are the test seams, exactly as on :class:`OverlayLauncher`.
    """

    def __init__(self, popen_factory: Callable[..., Any] | None = None,
                 nav_sh: str | None = None) -> None:
        self._popen_factory = popen_factory
        self._nav_sh = nav_sh
        self._launchers: dict[str, OverlayLauncher] = {}

    @property
    def launchers(self) -> dict[str, OverlayLauncher]:
        return self._launchers

    def _launcher(self, key: str, script: str | None = None) -> OverlayLauncher:
        """The launcher table entry for *key* (a nav.sh mode OR a script view).

        A standalone-script view (e.g. '3d') passes *script*: the launcher's
        nav_sh IS that script and its mode is EMPTY, so argv is ['bash',
        <script>] — the OverlayLauncher runs it directly. nav.sh-mode views
        pass no script and behave exactly as before.
        """
        if key not in self._launchers:
            if script is not None:
                self._launchers[key] = OverlayLauncher(
                    "", nav_sh=os.path.expanduser(script),
                    popen_factory=self._popen_factory)
            else:
                self._launchers[key] = OverlayLauncher(
                    key, nav_sh=self._nav_sh,
                    popen_factory=self._popen_factory)
        return self._launchers[key]

    def open(self, view: str) -> tuple[str, str]:
        """Open *view* -> (status, detail); status: opened | already_open |
        bad_view | error. Dedupe: an already-running view is ok, not a relaunch."""
        script = _SCRIPT_VIEWS.get(view)
        if script is not None:
            # Script view ('3d'): key the launcher table by the VIEW name (its
            # mode is empty, so keying by mode would collide across scripts).
            launcher = self._launcher(view, script=script)
            return self._open_launcher(launcher)
        mode = _VIEWS.get(view)
        if mode is None:
            return "bad_view", (
                f"unknown view {view!r}; valid: "
                f"{sorted(set(_VIEWS) | set(_SCRIPT_VIEWS))}")
        launcher = self._launcher(mode)
        return self._open_launcher(launcher)

    def _open_launcher(self, launcher: OverlayLauncher) -> tuple[str, str]:
        if launcher.is_running():
            return "already_open", f"already running (pid {launcher.pid})"
        launched, detail = launcher.launch()
        if launched:
            return "opened", detail
        if "already running" in detail:
            return "already_open", detail
        return "error", detail

    def close_all(self) -> tuple[list[str], list[str]]:
        """SIGINT every running view -> (closed modes, still-running modes)."""
        closed: list[str] = []
        stuck: list[str] = []
        for mode, launcher in self._launchers.items():
            if not launcher.is_running():
                continue
            clean, _rc = launcher.stop()
            (closed if clean else stuck).append(mode)
        return closed, stuck


@tool(
    name="go2w_real_viz",
    description=(
        "Open or close a visualization on the robot's desktop so the operator "
        "can watch (Moonlight/local screen). action: open (view: main|explore|"
        "route = RViz, match the running planner; 3d = the Foxglove 3D View3D "
        "stream — 彩色预建图 + 实时位姿), close (closes all views). Non-blocking; "
        "runs as a background child. Opening an already-open view is ok "
        "(dedupe). 给操作者打开/关闭可视化(RViz 或 3D 视图)。"),
    read_only=False,
    permission="allow",
)
class Go2WRealVizTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["open", "close"],
                       "default": "open"},
            "view": {"type": "string",
                     "enum": sorted(set(_VIEWS) | set(_SCRIPT_VIEWS)),
                     "default": "main"},
        },
    }

    def __init__(self, popen_factory: Callable[..., Any] | None = None,
                 nav_sh: str | None = None) -> None:
        # Fallback session for agent-less contexts (tests, bare tool calls);
        # with a live embodiment the shared agent._viz session wins.
        self._own_session = VizOverlaySession(
            popen_factory=popen_factory, nav_sh=nav_sh)

    @property
    def _launchers(self) -> dict[str, OverlayLauncher]:
        """Back-compat test seam: the fallback session's launcher table."""
        return self._own_session.launchers

    # ------------------------------------------------------------------
    def _session_for(self, context: Any) -> VizOverlaySession:
        """The embodiment's shared session when present, else our own."""
        agent = getattr(context, "agent", None)
        shared = getattr(agent, "_viz", None) if agent is not None else None
        return shared if shared is not None else self._own_session

    def _open(self, session: VizOverlaySession, view: str) -> ToolResult:
        status, detail = session.open(view)
        if status == "opened":
            return ToolResult(content=(
                f"RViz ({view}) opening on the robot desktop — visible via "
                f"Moonlight or the local screen. {detail}"))
        if status == "already_open":
            return ToolResult(content=f"RViz ({view}) is already open. {detail}")
        if status == "bad_view":
            return ToolResult(content=detail, is_error=True)
        return ToolResult(content=f"could not open RViz ({view}): {detail}",
                          is_error=True)

    def _close(self, session: VizOverlaySession) -> ToolResult:
        closed, stuck = session.close_all()
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
        session = self._session_for(context)
        action = params.get("action", "open")
        if action == "open":
            return self._open(session, params.get("view", "main"))
        if action == "close":
            return self._close(session)
        return ToolResult(content=(
            f"unknown action {action!r}; valid: ['open', 'close']"),
            is_error=True)
