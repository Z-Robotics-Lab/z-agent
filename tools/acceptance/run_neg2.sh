#!/usr/bin/env bash
set -u
cd /home/yusen/Desktop/zeno
export VECTOR_PROVIDER=deepseek VECTOR_NO_ROS2=1 DEEPSEEK_MODEL=deepseek-chat
# Control: negate the RED CAN, demand the GREEN BOTTLE. Rules out a can-bias/grab-nearest
# confound. Blue bottle also present as an un-negated distractor.
FETCH='别拿红色的罐子，也别动蓝色的，把绿色的瓶子拿给我'
timeout 1500 .venv/bin/python tools/acceptance/repl_accept.py "$FETCH" "" neg_green fetch
echo "EXIT=$?"
