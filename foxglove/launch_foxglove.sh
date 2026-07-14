#!/usr/bin/env bash
# Zeno — Foxglove Bridge 启动脚本
# 启动 foxglove_bridge，然后用浏览器连接 Foxglove Studio
#
# Usage: ./foxglove/launch_foxglove.sh
# 需要: ros-jazzy-foxglove-bridge, ROS2 topics 已在发布

set -e

# Real-robot DDS isolation (domain 20 + CycloneDDS): without this the bridge
# joins the default domain and sees ZERO topics on the NUC. Same guarded
# source the zeno launcher uses; dev machines without the file are unaffected.
[ -f "$HOME/go2w-nuc/bringup/ros_env.sh" ] && source "$HOME/go2w-nuc/bringup/ros_env.sh"

PORT="${FOXGLOVE_PORT:-8765}"

# Colors
TEAL='\033[36m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${TEAL}Zeno — Foxglove Bridge${RESET}"
echo ""

# Check foxglove_bridge
if ! ros2 pkg list 2>/dev/null | grep -q foxglove_bridge; then
    echo "ERROR: foxglove_bridge not found."
    echo "Install: sudo apt install ros-jazzy-foxglove-bridge"
    exit 1
fi

# Source ROS2 if needed
if [ -z "$ROS_DISTRO" ]; then
    source /opt/ros/jazzy/setup.bash
fi

# Cleanup on exit
cleanup() {
    echo -e "\n${DIM}Shutting down foxglove_bridge...${RESET}"
    kill "$BRIDGE_PID" 2>/dev/null
    wait "$BRIDGE_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

# Start foxglove_bridge — address:=0.0.0.0 makes REMOTE viewing explicit
# (stock default is already 0.0.0.0; stated here so it's a documented choice).
echo -e "${DIM}Starting foxglove_bridge on 0.0.0.0:${PORT}...${RESET}"
ros2 launch foxglove_bridge foxglove_bridge_launch.xml \
    address:=0.0.0.0 port:="$PORT" &
BRIDGE_PID=$!

sleep 2

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAN_IPS="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | head -3 | tr '\n' ' ')"

echo ""
echo -e "${TEAL}Foxglove Bridge ready${RESET} — 本机 IP: ${BOLD}${LAN_IPS:-未知}${RESET}"
echo ""
echo -e "  ${BOLD}远程查看(推荐 — 桌面版 Foxglove Studio):${RESET}"
echo -e "    笔记本装 Foxglove Studio 桌面版 → Open connection →"
echo -e "    ${TEAL}ws://<本机IP>:${PORT}${RESET}   (IP 见上;需同一局域网)"
echo ""
echo -e "  ${BOLD}远程查看(浏览器 app.foxglove.dev):${RESET}"
echo -e "    ${DIM}HTTPS 页面拒连非 localhost 的 ws://(mixed-content),须先建 SSH 隧道:${RESET}"
echo -e "    笔记本执行: ${TEAL}ssh -N -L ${PORT}:localhost:${PORT} $(whoami)@<本机IP>${RESET}"
echo -e "    然后浏览器连 ${TEAL}ws://localhost:${PORT}${RESET}"
echo ""
TS_IP="$(echo "$LAN_IPS" | tr ' ' '\n' | grep '^100\.' | head -1)"
if [ -n "$TS_IP" ]; then
    echo -e "  ${BOLD}跨网远程(Tailscale):${RESET} 桌面版连 ${TEAL}ws://${TS_IP}:${PORT}${RESET} ${DIM}(任意网络)${RESET}"
    echo ""
fi
echo -e "  ${BOLD}本机查看:${RESET} app.foxglove.dev → ${TEAL}ws://localhost:${PORT}${RESET}"
echo ""
echo -e "  导入 dashboard: Layout menu → Import → ${DIM}${SCRIPT_DIR}/zeno-go2w-dashboard.json${RESET}"
echo ""
if command -v ufw >/dev/null 2>&1 && sudo -n ufw status 2>/dev/null | grep -q '^Status: active'; then
    if ! sudo -n ufw status 2>/dev/null | grep -q "${PORT}"; then
        echo -e "  ${BOLD}⚠ 防火墙 ufw 已启用且未放行 ${PORT}${RESET}: sudo ufw allow ${PORT}/tcp"
        echo ""
    fi
fi
echo -e "  ${BOLD}⚠ 安全${RESET}${DIM}: bridge 对局域网开放,连上的人可点击发布 /way_point(机器人会走)。"
echo -e "  仅在可信网络使用;操作期间 E-stop 遥控器在手(AGENTS.md 硬件铁律)。${RESET}"
echo ""
echo -e "${DIM}Press Ctrl+C to stop${RESET}"

wait "$BRIDGE_PID"
