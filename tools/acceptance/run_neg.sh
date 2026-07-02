#!/usr/bin/env bash
set -u
cd /home/yusen/Desktop/vector_os_nano
export VECTOR_PROVIDER=deepseek
export DEEPSEEK_MODEL=deepseek-chat
export VECTOR_NO_ROS2=1
# Negation NL frontier: 3 pickables present (green bottle, blue bottle, red can).
# Two distractor colours EXPLICITLY negated; only red demanded. A naive substring/
# first-match matcher would grab blue or green; true NLU grasps the red can.
FETCH='不要蓝色的瓶子，也不要绿色的，只把红色的罐子拿过来'
timeout 1500 .venv/bin/python tools/acceptance/repl_accept.py "$FETCH" "" neg_red fetch
echo "EXIT=$?"
