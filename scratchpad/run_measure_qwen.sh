#!/bin/bash
set +e
cd /home/yusen/Desktop/vector_os_nano || exit 9
set -a; source .env 2>/dev/null; set +a
export PATH=/usr/bin:$PATH
export VECTOR_JUDGE_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1" VECTOR_JUDGE_MODEL="qwen3-vl-plus" VECTOR_JUDGE_API_KEY="$QWEN_API_KEY"
SP=/tmp/claude-1000/-home-yusen/de114851-2aa5-4dd2-b3cb-20b2199b9b23/scratchpad
LOG="$SP/measure_${3:-m}.log"; echo "START measure $*" > "$LOG"
.venv/bin/python "$SP/measure_qwen.py" "$1" "$2" "$3" "$4" >> "$LOG" 2>&1
echo "RC=$?" >> "$LOG"
