#!/usr/bin/env bash
# install-launcher.sh — 把 `zeno` 产品入口装进 ~/.local/bin（新机迁移一步到位）。
# 用法: bash scripts/install-launcher.sh
# 生成的 launcher 以本仓库检出位置为锚（迁移到任何路径都成立），
# .env（DeepSeek 等密钥）gitignored——需从旧机手动拷贝到仓库根。
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"

cat > "$BIN/zeno" <<EOF
#!/bin/bash
# zeno — Zeno CLI（go2w 世界 + DeepSeek 大脑）。Z-Robotics-Lab/z-agent 的产品入口。
# 由 scripts/install-launcher.sh 生成于 $REPO
cd "$REPO" || exit 1
set -a; source .env 2>/dev/null; set +a
export ZENO_PROVIDER="\${ZENO_PROVIDER:-deepseek}"
export DEEPSEEK_MODEL="\${DEEPSEEK_MODEL:-deepseek-v4-flash}"
export GO2W_SIM_DIR="\${GO2W_SIM_DIR:-\$HOME/Desktop/go2w}"
exec "$REPO/.venv/bin/python" -m zeno.vcli.cli --world go2w "\$@"
EOF
chmod +x "$BIN/zeno"
ln -sf "$BIN/zeno" "$BIN/za"

[ -f "$REPO/.env" ] || echo "[install] 警告: $REPO/.env 不存在——从旧机拷贝密钥文件后 zeno 才能连 LLM"
[ -x "$REPO/.venv/bin/python" ] || echo "[install] 警告: .venv 未就绪——先按 progress.md 环境镜像清单重建 venv"
echo "[install] 完成: $BIN/zeno (+ za 别名) -> $REPO"
