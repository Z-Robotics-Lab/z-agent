#!/usr/bin/env bash
# install-launcher-workstation.sh — 把 `zeno` 工作站入口装进 ~/.local/bin。
#
# 这是开发机(4090 工作站)专用变体,和 NUC 版 scripts/install-launcher.sh 并列。
# 用户唯一测试方式 = 终端输入 `zeno` → 自然语言下任务;本脚本让该入口在 4090
# 上一步到位,并随仓库继承(启动配方入库,不再靠某台机器的手工残留)。
#
# 用法: bash scripts/install-launcher-workstation.sh
#
# 与 NUC 版(install-launcher.sh)的关键差异:
#   - 直接 source 系统 ROS(/opt/ros/jazzy);NUC 版 source ~/go2w-nuc/bringup/ros_env.sh。
#   - CYCLONEDDS_URI 指向 *workstation* 侧 DDS profile(本机 WiFi 网卡 + 单播 peer
#     192.168.3.8),让 4090 以“只订阅”方式加入 NUC 的 domain 20——见
#     go2w-nuc/bringup/workstation/cyclonedds-workstation.xml。
#   - ZENO_WORLD=go2w_real:裸 `zeno` 直接进真机世界(NUC 由 ros_env.sh 设同值)。
#   - GO2W_NAV_TRANSPORT=ssh + GO2W_NAV_SSH_HOST=go2w-nuc:导航栈跑在 NUC 上,
#     经 ssh 远端启停(transport 由下游 bringup agent 落地;此处先把契约变量设好)。
#
# .env(DeepSeek 等密钥)是 gitignored 的——从 NUC 拷到本仓根:
#     scp go2w-nuc:z-agent/.env <repo>/.env && chmod 600 <repo>/.env
set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"

# workstation DDS profile 位于同级 go2w-nuc 仓(Z-Robotics-Lab/go2w-nuc)。
# 相对本检出定位(REPO 的父目录),迁移到任何路径都成立。
LAB_ROOT="$(cd "$REPO/.." && pwd)"
DDS_XML="$LAB_ROOT/go2w-nuc/bringup/workstation/cyclonedds-workstation.xml"

if [ ! -f "$DDS_XML" ]; then
    echo "[install] 警告: workstation DDS profile 不存在:"
    echo "[install]       $DDS_XML"
    echo "[install]   跨机 DDS(domain 20)由 DDS agent 在 go2w-nuc 仓落地。文件就位后"
    echo "[install]   zeno 才能看到 NUC 的话题;缺失时世界仍能加载但订阅不到 /nuc/*。"
    echo "[install]   TODO: DDS profile 落地后重跑本脚本,或确认上面的路径正确。"
fi

cat > "$BIN/zeno" <<EOF
#!/bin/bash
# zeno — Zeno CLI 工作站入口(4090 → go2w 真机世界)。
# 由 scripts/install-launcher-workstation.sh 生成于 $REPO
# 请勿手改:改配方请改 scripts/install-launcher-workstation.sh 并重跑。

# --- 系统 ROS(rclpy 从这里进 PYTHONPATH;venv 是 no-system-site-packages) ---
source /opt/ros/jazzy/setup.bash

# --- 跨机 DDS:以只订阅方式加入 NUC 的 domain 20(不参与控制链路) ---
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID=20
export CYCLONEDDS_URI="file://$DDS_XML"

# --- 世界 + 导航 transport(nav 栈在 NUC,经 ssh 远端启停;下游 agent 实现) ---
export ZENO_WORLD="\${ZENO_WORLD:-go2w_real}"
export GO2W_NAV_TRANSPORT="\${GO2W_NAV_TRANSPORT:-ssh}"
export GO2W_NAV_SSH_HOST="\${GO2W_NAV_SSH_HOST:-go2w-nuc}"

# --- 大脑:DeepSeek(与 NUC 一致;密钥由 .env 提供) ---
export ZENO_PROVIDER="\${ZENO_PROVIDER:-deepseek}"
export DEEPSEEK_MODEL="\${DEEPSEEK_MODEL:-deepseek-v4-pro}"

cd "$REPO" || exit 1
set -a; source .env 2>/dev/null; set +a
exec "$REPO/.venv/bin/python" -m zeno.vcli.cli --world "\${ZENO_WORLD:-go2w_real}" "\$@"
EOF
chmod +x "$BIN/zeno"
ln -sf "$BIN/zeno" "$BIN/za"

[ -f "$REPO/.env" ] || echo "[install] 警告: $REPO/.env 不存在——从 NUC 拷密钥文件(scp go2w-nuc:z-agent/.env)后 zeno 才能连 LLM"
[ -x "$REPO/.venv/bin/python" ] || echo "[install] 警告: .venv 未就绪——先按 progress.md 环境镜像清单重建 venv(python3.12 -m venv .venv; pip install -e '.[dev]')"
case ":$PATH:" in
    *":$BIN:"*) : ;;
    *) echo "[install] 提示: $BIN 不在 PATH——把它加进 ~/.bashrc 后 \`zeno\` 才能裸调用" ;;
esac
echo "[install] 完成: $BIN/zeno (+ za 别名) -> $REPO  (world=go2w_real, DDS domain 20)"
