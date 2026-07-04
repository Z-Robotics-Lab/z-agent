#!/usr/bin/env bash
# R304: re-run fetch colour bars bare-face under vlm-judge to adjudicate provisionals (E46 N>=2).
# Usage: run_fetch.sh <room> <colour> <fetch_nl>
set -euo pipefail
cd /home/yusen/Desktop/vector_os_nano
set -a; . ./.env; set +a
export VECTOR_PROVIDER=deepseek
export DEEPSEEK_MODEL=deepseek-v4-flash
export VECTOR_NO_ROS2=1 MUJOCO_GL=egl
export VECTOR_VLM_URL=http://localhost:11434/v1 VECTOR_VLM_MODEL=gemma4:e4b
ROOM="$1"; COLOUR="$2"; FETCH_NL="$3"
export VECTOR_ROOM_TEMPLATE="$ROOM"
export VECTOR_EVIDENCE_DIR="var/evidence/R304/${ROOM}_${COLOUR}"
mkdir -p "$VECTOR_EVIDENCE_DIR"
export ROUND_N="${ROUND_N:-304}" ROUND_DEADLINE_EPOCH="${ROUND_DEADLINE_EPOCH:-0}"
.venv/bin/python tools/acceptance/repl_accept.py "$FETCH_NL" "把绿色的瓶子放到架子上" "R${ROUND_N}${ROOM}${COLOUR}" fetch
