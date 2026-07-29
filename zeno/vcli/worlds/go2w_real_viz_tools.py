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
import shlex
from pathlib import Path
from typing import Any, Callable

from zeno.hardware.ros2.go2w_hw_overlay import OverlayLauncher
from zeno.hardware.ros2.nav_transport import NavTransport, nav_transport
from zeno.vcli.tools.base import ToolContext, ToolResult, tool

#: view name (agent-facing) -> nav.sh subcommand (one overlay per view).
#: 'route' now maps to the MAIN view: far_planner's displays (GlobalPath /
#: Goalpoint / VGraph / ViewpointExtend) were merged into vehicle_simulator.rviz
#: (2026-07-15), so there is no separate route RViz. Same key as 'main' -> the
#: launcher dedupes them (opening 'route' when 'main' is up is a no-op).
_VIEWS: dict[str, str] = {
    "main": "rviz",
    "explore": "rviz-explore",
    "route": "rviz",
}

#: STANDALONE-SCRIPT views: view name -> a script the OverlayLauncher runs
#: DIRECTLY (empty mode), NOT a nav.sh subcommand. The 3D View3D stream
#: (彩色预建图 + 实时位姿, Foxglove) is built by the go2w-nuc half; contract-
#: first here (2026-07-14). Reuses the SAME OverlayLauncher machinery — dedupe
#: + close_all work identically — so the two viz stacks share one lifecycle.
_SCRIPT_VIEWS: dict[str, str] = {
    "3d": "~/go2w-nuc/scripts/view3d.sh",
}

# ---------------------------------------------------------------------------
# Workstation-local RViz (4090) — the Phase 2 ssh-transport stub replacement.
#
# When the nav host is the headless NUC (ssh transport, opens_local_gui False) the
# earlier code returned a "go connect Foxglove yourself" pointer. Main control now
# runs on the 4090 (a desktop box), so RViz must open HERE, subscribing to the NUC's
# topics over DDS domain 20. The window renders on the 4090's screen; the data is the
# NUC's. (CEO-authorized 2026-07-29.)
# ---------------------------------------------------------------------------

#: The workstation checkout root: this file is
#: <root>/z-agent-run/zeno/vcli/worlds/go2w_real_viz_tools.py, so the sibling
#: go2w-nuc / Z-Navigation-Stack checkouts live under parents[4].
_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]

#: nav.sh RViz MODE -> rviz config, RELATIVE to the nav-stack checkout. Mirrors
#: nav.sh's own choices (main/route share vehicle_simulator.rviz; explore ->
#: tare_planner_ground.rviz) so the workstation window matches what the NUC shows.
_WORKSTATION_RVIZ_REL: dict[str, str] = {
    "rviz": "src/base_autonomy/vehicle_simulator/rviz/vehicle_simulator.rviz",
    "rviz-explore": "src/exploration_planner/tare_planner/rviz/tare_planner_ground.rviz",
}


def _workstation_ros_env() -> str:
    """Path to the workstation ros_env.sh (RMW=cyclonedds, ROS_DOMAIN_ID=20,
    CYCLONEDDS_URI, /opt/ros/jazzy). Env override ``GO2W_WORKSTATION_ROS_ENV``;
    default the in-repo go2w-nuc bringup script."""
    return os.environ.get("GO2W_WORKSTATION_ROS_ENV", "").strip() or str(
        _WORKSPACE_ROOT / "go2w-nuc" / "bringup" / "workstation" / "ros_env.sh")


def _workstation_nav_stack() -> str:
    """The Z-Navigation-Stack checkout on this workstation (holds the rviz configs).
    Env override ``ZENO_NAV_STACK_REPO``; default the sibling checkout."""
    return os.environ.get("ZENO_NAV_STACK_REPO", "").strip() or str(
        _WORKSPACE_ROOT / "Z-Navigation-Stack-go2w")


def _workstation_rviz_config(mode: str) -> str | None:
    """Absolute rviz-config path for nav.sh RViz *mode* on this workstation, or None
    for a mode with no workstation config."""
    rel = _WORKSTATION_RVIZ_REL.get(mode)
    if rel is None:
        return None
    return os.path.join(_workstation_nav_stack(), rel)


def _has_display() -> bool:
    """True iff an X / Wayland display is reachable — i.e. a GUI can open HERE. No
    display (headless ssh session into the 4090) -> honest Foxglove degrade."""
    return bool(os.environ.get("DISPLAY", "").strip()
                or os.environ.get("WAYLAND_DISPLAY", "").strip())


def _foxglove_hint(reason: str) -> str:
    """The honest 'open it on the 4090 yourself' pointer, prefixed with *reason*."""
    return (f"{reason} 请在 4090 工作站本地打开 Foxglove 或 RViz —— 话题已经过 DDS "
            "domain 20 跨机可见,不必在 NUC 上开窗。(Foxglove: ws://<NUC>:8765;"
            "RViz: 用工作站 DDS profile 订阅 /state_estimation、/registered_scan 等。)")


class _WorkstationRvizTransport(NavTransport):
    """Spawn ``rviz2`` on THIS box (the 4090), sourcing the workstation ROS env so it
    subscribes to the NUC's topics over DDS domain 20.

    A LOCAL-GUI transport shape that plugs into :class:`OverlayLauncher`'s existing
    spawn / SIGINT / dedupe / close_all lifecycle UNCHANGED — only the argv (source
    ros_env && exec rviz2 -d <config>) and a config/ros_env existence preflight
    differ from the nav.sh path. ``exec`` makes the child PID rviz2 itself, so the
    launcher's SIGINT lands on rviz2 (clean teardown) and ``start_new_session``
    detaches it (a REPL Ctrl+C / exit never takes RViz with it).
    """

    mode = "workstation-rviz"
    is_remote = False
    #: We ARE opening the window on this screen — local GUI by construction.
    opens_local_gui = True

    def __init__(self, config: str, ros_env: str) -> None:
        # Intentionally NOT calling super().__init__ (no nav.sh path involved) — the
        # only state the OverlayLauncher-invoked methods use is config + ros_env.
        self._config = config
        self._ros_env = ros_env

    def overlay_preflight(self, script: str) -> str | None:
        # Honest pre-run errors: a missing ros_env or rviz config means a doomed
        # spawn — report it loudly instead of a window that dies on an obscure error.
        if not os.path.isfile(self._ros_env):
            return (f"workstation ros_env not found: {self._ros_env} — set "
                    "GO2W_WORKSTATION_ROS_ENV to the ros_env.sh that joins DDS domain 20")
        if not os.path.isfile(self._config):
            return (f"rviz config not found: {self._config} — set ZENO_NAV_STACK_REPO "
                    "to the Z-Navigation-Stack checkout on this workstation")
        return None

    def overlay_argv(self, script: str, mode: str, handle: Any,
                     *extra: Any) -> list[str]:
        cmd = (f"source {shlex.quote(self._ros_env)} && "
               f"exec rviz2 -d {shlex.quote(self._config)}")
        return ["bash", "-c", cmd]

    # new_overlay_handle() -> None and overlay_interrupt() -> SIGINT are inherited
    # verbatim from NavTransport (a local child: signal the process we spawned).

    def describe(self) -> str:
        return f"workstation rviz2 -d {self._config}"


class VizOverlaySession:
    """Session-scoped RViz overlay state — the ONE owner of view launchers.

    Both the ``go2w_real_viz`` TOOL and the ``open_viz`` SKILL act on the same
    instance (the embodiment's ``_viz``, ridden on the driver as
    ``base.viz_manager`` like the explore/route managers), so a view opened on
    either face is 'already open' on the other. ``popen_factory`` / ``nav_sh``
    are the test seams, exactly as on :class:`OverlayLauncher`.
    """

    def __init__(self, popen_factory: Callable[..., Any] | None = None,
                 nav_sh: str | None = None,
                 transport: NavTransport | None = None) -> None:
        self._popen_factory = popen_factory
        self._nav_sh = nav_sh
        # RViz/3D views render on the NAV HOST's screen. Under ssh (nav host =
        # headless NUC) there is no screen; the transport tells us to refuse the
        # remote window and point the operator at Foxglove/RViz on the 4090.
        self._transport = transport or nav_transport(
            os.path.expanduser(nav_sh) if nav_sh else None)
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
        """Open *view* -> (status, detail); status: opened | opened_workstation |
        already_open | remote_gui | bad_view | error. Dedupe: an already-running
        view is ok, not a relaunch.

        Transport-aware: in LOCAL mode the nav host IS this box, so RViz/3D open on
        the nav.sh path exactly as before. Under ssh (nav host = headless NUC) an
        RViz view opens LOCALLY on this workstation (the 4090) subscribing over DDS
        domain 20 — ``opened_workstation`` — while the NUC-built 3D (Foxglove) stream
        keeps its honest 'open it on the 4090' pointer (that option is preserved)."""
        script = _SCRIPT_VIEWS.get(view)
        if script is not None:
            # The 3D View3D (Foxglove) stream is BUILT on the nav host (the NUC's
            # view3d.sh), so it cannot run locally when the nav host is headless —
            # keep the honest Foxglove pointer under ssh; run it as before in local.
            if not self._transport.opens_local_gui:
                return "remote_gui", _foxglove_hint(
                    f"3D 视图(Foxglove View3D)在导航主机上构建,但 nav "
                    f"transport={self._transport.mode}(导航主机是无屏 NUC)。")
            # Script view ('3d'): key the launcher table by the VIEW name (its
            # mode is empty, so keying by mode would collide across scripts).
            launcher = self._launcher(view, script=script)
            return self._open_launcher(launcher)
        mode = _VIEWS.get(view)
        if mode is None:
            return "bad_view", (
                f"unknown view {view!r}; valid: "
                f"{sorted(set(_VIEWS) | set(_SCRIPT_VIEWS))}")
        if not self._transport.opens_local_gui:
            # Nav host is the headless NUC (ssh transport). Render RViz HERE on the
            # 4090 desktop instead of the Phase 2 stub that punted to the operator.
            return self._open_workstation_rviz(mode, view)
        launcher = self._launcher(mode)
        return self._open_launcher(launcher)

    def _open_workstation_rviz(self, mode: str, view: str) -> tuple[str, str]:
        """Open RViz LOCALLY on the 4090 for nav.sh RViz *mode*.

        DISPLAY detection: with no X/Wayland we honestly degrade to the Foxglove
        pointer rather than spawn a doomed window. Dedupe is keyed by nav.sh mode,
        so opening 'route' when 'main' is up is a no-op (both are the 'rviz' mode).
        """
        if not _has_display():
            return "remote_gui", _foxglove_hint(
                "工作站无可用图形界面(DISPLAY/WAYLAND_DISPLAY 未设置),无法在本机"
                "开 RViz 窗口。")
        config = _workstation_rviz_config(mode)
        if config is None:
            return "bad_view", f"no workstation rviz config for view {view!r}"
        launcher = self._workstation_launcher(mode, config)
        status, detail = self._open_launcher(launcher)
        # Rename the fresh-launch status so the operator-facing message says the
        # window opened HERE (on the 4090), not on the robot desktop. already_open /
        # error pass through unchanged.
        if status == "opened":
            return "opened_workstation", detail
        return status, detail

    def _workstation_launcher(self, mode: str, config: str) -> OverlayLauncher:
        """The workstation-local RViz launcher for nav.sh *mode* (dedupe key = mode,
        so main/route share one). Reuses OverlayLauncher's spawn / SIGINT / close_all
        lifecycle via the local-GUI :class:`_WorkstationRvizTransport`."""
        if mode not in self._launchers:
            self._launchers[mode] = OverlayLauncher(
                mode, nav_sh=self._nav_sh,
                popen_factory=self._popen_factory,
                transport=_WorkstationRvizTransport(config, _workstation_ros_env()))
        return self._launchers[mode]

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
    # GUI action: opens/closes a window for the operator. No physical goal-state a
    # predicate can prove, so the native-loop finish-gate must not demand a verify()
    # (see native_loop._tool_verify_exempt). CEO-authorized 2026-07-29.
    verify_exempt=True,
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
        if status == "opened_workstation":
            return ToolResult(content=(
                f"已在工作站打开 RViz({view}) —— 4090 本地窗口,通过 DDS domain 20 "
                f"订阅 NUC 的实时话题。{detail}"))
        if status == "already_open":
            return ToolResult(content=f"RViz ({view}) is already open. {detail}")
        if status == "remote_gui":
            # Not an error: we correctly declined to open a window on the
            # headless NUC and told the operator where to look on the 4090.
            return ToolResult(content=detail)
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
