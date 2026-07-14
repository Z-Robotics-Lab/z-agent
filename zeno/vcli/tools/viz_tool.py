# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""FoxgloveTool — start/stop Foxglove Bridge for web visualization."""
from __future__ import annotations

import shutil
import subprocess
from typing import Any

from zeno.vcli.tools.base import ToolContext, ToolResult, tool

# Module-level process tracking (survives across tool calls)
_foxglove_proc: subprocess.Popen | None = None


def _lan_ips() -> str:
    """Space-separated LAN IPs for remote-connection hints (best-effort).

    Pure-socket (NO subprocess): tests patch subprocess.Popen around the
    bridge start, and subprocess.run would consume that mock. UDP connect
    sends no packet — it just resolves the default-route interface; the
    hostname lookup adds any additional NICs (robot LAN vs home LAN).
    """
    import socket

    ips: list[str] = []
    try:  # Linux: enumerate every interface address via ioctl (robot NUC path)
        import fcntl
        import struct

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            for _idx, name in socket.if_nameindex():
                if name == "lo":
                    continue
                try:
                    packed = fcntl.ioctl(
                        sock.fileno(), 0x8915,  # SIOCGIFADDR
                        struct.pack("256s", name[:15].encode()),
                    )
                    ip = socket.inet_ntoa(packed[20:24])
                    if not ip.startswith("127.") and ip not in ips:
                        ips.append(ip)
                except OSError:
                    continue  # interface without an IPv4 address
        finally:
            sock.close()
    except Exception:  # noqa: BLE001 — hint only
        pass
    if not ips:  # non-Linux fallback: default-route interface only
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(("8.8.8.8", 80))
                ips.append(sock.getsockname()[0])
            finally:
                sock.close()
        except Exception:  # noqa: BLE001 — hint only
            pass
    # LAN (192.168/10/172.16-31) first — that's what a laptop can actually reach.
    ips.sort(key=lambda ip: not ip.startswith(("192.168.", "10.", "172.")))
    return " ".join(ips[:3]) or "<本机IP>"


def _connect_help() -> str:
    """Connection recipes incl. REMOTE viewing (owner ask 2026-07-14)."""
    ips = _lan_ips()
    return (
        f"远程(推荐,桌面版 Foxglove Studio): ws://{ips.split()[0] if ips[0] != '<' else '<本机IP>'}:8765\n"
        f"  本机 IP: {ips} (需同一局域网)\n"
        "远程(浏览器 app.foxglove.dev): HTTPS 拒连远程 ws://,先 SSH 隧道:\n"
        "  笔记本: ssh -N -L 8765:localhost:8765 <user>@<本机IP> → 连 ws://localhost:8765\n"
        "本机: app.foxglove.dev → ws://localhost:8765\n"
        + (
            f"跨网远程(Tailscale 已装): 桌面版连 ws://{_ts}:8765,任意网络可达\n"
            if (_ts := next((ip for ip in ips.split() if ip.startswith("100.")), ""))
            else ""
        )
        + "导入 layout: foxglove/zeno-go2w-dashboard.json\n"
        "⚠ 局域网内连上的人可点击发布 /way_point(机器人会走) — 可信网络+E-stop 在手"
    )


def _is_bridge_running() -> bool:
    """Check if foxglove_bridge is already listening on port 8765."""
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return ":8765" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


@tool(
    name="open_foxglove",
    description=(
        "打开/关闭可视化 (Open/close visualization). "
        "Start or stop Foxglove Bridge for real-time 3D visualization (可视化/foxglove/viz). "
        "Shows point clouds, navigation paths, camera feed, and scene graph markers. "
        "Call this tool when user says: 打开可视化, open visualization, start foxglove, show viz. "
        "Use action='start' to launch, action='stop' to shut down, action='status' to check."
    ),
    read_only=False,
    permission="allow",
)
class FoxgloveTool:
    """Manage the Foxglove Bridge lifecycle from the CLI."""

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "stop", "status"],
                "description": "start: launch bridge, stop: kill bridge, status: check if running",
                "default": "start",
            },
        },
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        global _foxglove_proc
        action = params.get("action", "start")

        if action == "status":
            running = _is_bridge_running()
            return ToolResult(
                content=f"Foxglove Bridge: {'running on ws://localhost:8765' if running else 'not running'}"
            )

        if action == "stop":
            return self._stop()

        # action == "start"
        return self._start()

    def _start(self) -> ToolResult:
        global _foxglove_proc

        # Already running?
        if _is_bridge_running():
            return ToolResult(
                content=(
                    "Foxglove Bridge already running (port 8765, 局域网可达)\n\n"
                    + _connect_help()
                )
            )

        # Check foxglove_bridge is installed
        foxglove_exec = shutil.which("ros2")
        if foxglove_exec is None:
            return ToolResult(
                content="ros2 not found in PATH. Source /opt/ros/jazzy/setup.bash first.",
                is_error=True,
            )

        # Start foxglove_bridge as background process
        try:
            _foxglove_proc = subprocess.Popen(
                [
                    "ros2", "launch", "foxglove_bridge",
                    "foxglove_bridge_launch.xml",
                    "address:=0.0.0.0", "port:=8765",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as e:
            return ToolResult(
                content=f"Failed to start foxglove_bridge: {e}",
                is_error=True,
            )

        # Brief wait and verify
        try:
            _foxglove_proc.wait(timeout=2)
            # If it exited quickly, something went wrong
            return ToolResult(
                content=(
                    "foxglove_bridge exited immediately. "
                    "Check: sudo apt install ros-jazzy-foxglove-bridge"
                ),
                is_error=True,
            )
        except subprocess.TimeoutExpired:
            pass  # Still running — good

        return ToolResult(
            content=(
                "Foxglove Bridge started (port 8765, 局域网可达)\n\n"
                + _connect_help()
                + "\n\nUse open_foxglove(action='stop') to shut down."
            )
        )

    def _stop(self) -> ToolResult:
        global _foxglove_proc

        if _foxglove_proc is not None:
            _foxglove_proc.terminate()
            try:
                _foxglove_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _foxglove_proc.kill()
            _foxglove_proc = None
            return ToolResult(content="Foxglove Bridge stopped.")

        # Try to kill by port even if we don't have the process handle
        if _is_bridge_running():
            try:
                subprocess.run(
                    ["fuser", "-k", "8765/tcp"],
                    capture_output=True,
                    timeout=5,
                )
                return ToolResult(content="Foxglove Bridge stopped (via port kill).")
            except (subprocess.SubprocessError, FileNotFoundError):
                return ToolResult(
                    content="Could not stop foxglove_bridge. Kill manually: fuser -k 8765/tcp",
                    is_error=True,
                )

        return ToolResult(content="Foxglove Bridge is not running.")
