#!/usr/bin/env bash
# install-service.sh — 生成并安装 rynnbrain 的 systemd --user unit。
#
# 只写 unit 文件，不 daemon-reload / 不 enable / 不 start（副作用留给调用方，见末尾提示）。
# 幂等：重跑覆盖 unit，覆盖前把旧文件备份到 ~/deploy-backups-20260729/。
# ExecStart 用 ~/envs/rynnbrain 的 python 跑*仓内* server.py；模型规格/路径/端口/设备
# 全走 Environment=，可在这里（下面几个变量）或 `systemctl --user edit rynnbrain` 覆盖。
#
# 用法:
#   bash scripts/rynnbrain/install-service.sh                 # 默认 2B
#   RYNNBRAIN_MODEL_SPEC=9b-nf4 bash scripts/rynnbrain/install-service.sh
set -e

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
SERVER="$REPO/scripts/rynnbrain/server.py"
VENV_PY="${RYNNBRAIN_PYTHON:-$HOME/envs/rynnbrain/bin/python}"
UNIT_DIR="$HOME/.config/systemd/user"
UNIT="$UNIT_DIR/rynnbrain.service"
BACKUP_DIR="$HOME/deploy-backups-20260729"

MODEL_SPEC="${RYNNBRAIN_MODEL_SPEC:-2b-bf16}"
HTTP_PORT="${RYNNBRAIN_HTTP_PORT:-8786}"
DEVICE="${RYNNBRAIN_DEVICE:-cuda:0}"

[ -f "$SERVER" ] || { echo "[install-service] 找不到仓内 server: $SERVER" >&2; exit 1; }
[ -x "$VENV_PY" ] || { echo "[install-service] 找不到 venv python: $VENV_PY" >&2; exit 1; }

mkdir -p "$UNIT_DIR"
if [ -f "$UNIT" ]; then
    mkdir -p "$BACKUP_DIR"
    cp -a "$UNIT" "$BACKUP_DIR/rynnbrain.service.$(date +%Y%m%d-%H%M%S).bak"
    echo "[install-service] 旧 unit 已备份到 $BACKUP_DIR/"
fi

cat > "$UNIT" <<EOF
[Unit]
Description=RynnBrain embodied-VLM service (z-agent perception oracle)
Documentation=file://$REPO/scripts/rynnbrain/README.md
After=network.target

[Service]
Type=simple
# 模型规格/路径/端口/设备 —— 改这里或 \`systemctl --user edit rynnbrain\` 覆盖。
Environment=RYNNBRAIN_MODEL_SPEC=$MODEL_SPEC
Environment=RYNNBRAIN_HTTP_PORT=$HTTP_PORT
Environment=RYNNBRAIN_DEVICE=$DEVICE
# 换 9B：把上面的 spec 改成 9b-nf4（模型路径默认推导到 %h/models/RynnBrain1.1-9B）。
# 自定义权重路径时再取消注释下一行：
# Environment=RYNNBRAIN_MODEL_PATH=%h/models/RynnBrain1.1-9B
# 额外开 ws+msgpack 老客户端边车（默认关，纯 HTTP 单一职责）：
# Environment=RYNNBRAIN_WS_ENABLE=1
ExecStart=$VENV_PY $SERVER
Restart=on-failure
RestartSec=5
# 模型加载（尤其 9B 量化）可能几十秒，给足启动余量。
TimeoutStartSec=300

[Install]
WantedBy=default.target
EOF

echo "[install-service] 已写入 $UNIT"
echo "[install-service]   spec=$MODEL_SPEC  http_port=$HTTP_PORT  device=$DEVICE"
echo "[install-service]   server=$SERVER"
echo "[install-service]   python=$VENV_PY"
echo
echo "启用并启动（4090 上）:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now rynnbrain"
echo "验证:"
echo "  curl -s http://127.0.0.1:$HTTP_PORT/health"
echo "查看日志:"
echo "  journalctl --user -u rynnbrain -f"
