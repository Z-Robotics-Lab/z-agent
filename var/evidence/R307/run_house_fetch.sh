#!/usr/bin/env bash
# R307: skeptic eyes-upgrade the STALE self-read HOUSE fetch bars -> vlm-judge on the
# CURRENT shipped bare face (deepseek-v4-flash + local gemma4:e4b judge). Inv.1 stricter-only.
# Usage: run_house_fetch.sh <tag> <fetch_nl>
set -euo pipefail
cd /home/yusen/Desktop/vector_os_nano
set -a; . ./.env; set +a
export VECTOR_PROVIDER=deepseek
export DEEPSEEK_MODEL=deepseek-v4-flash
export VECTOR_NO_ROS2=1 MUJOCO_GL=egl
export VECTOR_VLM_URL=http://localhost:11434/v1 VECTOR_VLM_MODEL=gemma4:e4b
TAG="$1"; FETCH_NL="$2"
export VECTOR_EVIDENCE_DIR="var/evidence/R307/${TAG}"
mkdir -p "$VECTOR_EVIDENCE_DIR"
export ROUND_N="${ROUND_N:-307}" ROUND_DEADLINE_EPOCH="${ROUND_DEADLINE_EPOCH:-0}"
# HOUSE world = default (no VECTOR_ROOM_TEMPLATE). MODE=fetch: grasp GT + vlm-judge eyes.
.venv/bin/python tools/acceptance/repl_accept.py "$FETCH_NL" "把绿色的瓶子放到架子上" "R${ROUND_N}${TAG}" fetch
