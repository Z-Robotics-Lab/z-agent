#!/usr/bin/env bash
# start_rynn.sh — 手动/开发态前台启动 RynnBrain 服务。
#
# 生产态走 systemd --user（见 install-service.sh + README）；本脚本给调试/临时跑用。
# 用 ~/envs/rynnbrain 的解释器（torch/transformers/bitsandbytes 都在那），跑*仓内*
# server.py。配置全走环境变量，与 systemd unit 同一套契约：
#   RYNNBRAIN_MODEL_SPEC  2b-bf16（默认） | 9b-nf4
#   RYNNBRAIN_HTTP_PORT   默认 8786（z-agent 感知契约端口）
#   RYNNBRAIN_DEVICE      默认 cuda:0
#   RYNNBRAIN_WS_ENABLE   1 = 额外开 ws+msgpack（LIBERO/ab_compare 老客户端）；默认关
#   RYNNBRAIN_PYTHON      覆盖解释器路径（默认 ~/envs/rynnbrain/bin/python）
#
# 例:  RYNNBRAIN_MODEL_SPEC=9b-nf4 bash scripts/rynnbrain/start_rynn.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="${RYNNBRAIN_PYTHON:-$HOME/envs/rynnbrain/bin/python}"

if [ ! -x "$VENV_PY" ]; then
    echo "[start_rynn] 找不到 venv 解释器: $VENV_PY" >&2
    echo "[start_rynn] 设 RYNNBRAIN_PYTHON 或按 README 建 ~/envs/rynnbrain 后重试。" >&2
    exit 1
fi

PORT="${RYNNBRAIN_HTTP_PORT:-8786}"
if ss -tln 2>/dev/null | grep -q ":${PORT} "; then
    echo "[start_rynn] 端口 ${PORT} 已被占用——服务可能已在跑（systemd? 见"
    echo "[start_rynn]   systemctl --user status rynnbrain）。先停掉再起，无需重复启动。"
    exit 0
fi

echo "[start_rynn] spec=${RYNNBRAIN_MODEL_SPEC:-2b-bf16} http_port=${PORT}" \
     "ws=${RYNNBRAIN_WS_ENABLE:-0} python=$VENV_PY"
exec "$VENV_PY" "$HERE/server.py"
