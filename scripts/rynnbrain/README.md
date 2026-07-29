# RynnBrain 具身-VLM 服务（z-agent 感知 oracle）

本地 GPU 工作站（4090）上跑的 RynnBrain 视觉-语言模型服务，给 z-agent 的感知技能
（`zeno/perception/rynnbrain.py`）做 grounding / 场景问答的真值 oracle。

由桌面测试目录 `~/Desktop/Learning_based_model/rynnbrain_test/` 收编进仓、统一并
参数化而来（桌面原件不动不删）。服务端跑在**专用 venv `~/envs/rynnbrain`**（torch /
transformers / bitsandbytes），**不是** z-agent 的 `.venv`——所以 `server.py` 不 import
任何 `zeno` 代码，配置全走环境变量，可被仓库继承、被 z-agent 一键 bringup。

## 契约（z-agent 客户端已存在）

```
POST http://127.0.0.1:8786/infer
     {"image": <base64 jpeg>, "text": str, "think": bool} -> {"reply": str}
GET  http://127.0.0.1:8786/health
     -> {"ok": true, "model": <spec>}
```

坐标是 `[0,1000]` 归一化的：`<object>(x1,y1),(x2,y2)` 框、`<affordance>(x,y)` 点。
客户端侧 `ZENO_RYNNBRAIN_URL`（或 `VECTOR_RYNNBRAIN_URL`）可覆盖 base_url（NUC 部署
指向工作站 LAN IP）。

## 模型选择

| spec | 权重 | 显存 | 定位延迟 | 问答 | 说明 |
|------|------|------|----------|------|------|
| `2b-bf16`（**默认**） | `~/models/RynnBrain1.1-2B` | ~4.5GB | ~1s | 较弱 | 延迟/显存友好，共享 24GB 4090 首选 |
| `9b-nf4` | `~/models/RynnBrain1.1-9B` | ~7.9GB | ~1s | 强，支持思考模式 | bitsandbytes NF4 int4，视觉塔保 bf16 |

默认 **2B bf16**：定位够用、显存省。换 9B 只需把 `RYNNBRAIN_MODEL_SPEC` 设成
`9b-nf4`（模型路径自动推导），或 `systemctl --user edit rynnbrain` 覆盖。

## 配置（环境变量）

| 变量 | 默认 | 含义 |
|------|------|------|
| `RYNNBRAIN_MODEL_SPEC` | `2b-bf16` | `2b-bf16` \| `9b-nf4` |
| `RYNNBRAIN_MODEL_PATH` | 按 spec 推导 | 模型目录，覆盖时用绝对/`~` 路径 |
| `RYNNBRAIN_HTTP_PORT` | `8786` | z-agent 契约端口 |
| `RYNNBRAIN_DEVICE` | `cuda:0` | 推理设备 |
| `RYNNBRAIN_WS_ENABLE` | `0` | `1` = 额外开 ws+msgpack 边车（LIBERO/ab_compare 老客户端） |
| `RYNNBRAIN_WS_PORT` | `8782` | 仅 `WS_ENABLE=1` 时生效 |
| `RYNNBRAIN_PYTHON` | `~/envs/rynnbrain/bin/python` | 解释器路径（start_rynn.sh / install-service.sh） |

## 生产态：systemd --user

```bash
# 1. 生成 unit（只写文件，覆盖前备份旧的到 ~/deploy-backups-20260729/）
bash scripts/rynnbrain/install-service.sh              # 默认 2B
# 或： RYNNBRAIN_MODEL_SPEC=9b-nf4 bash scripts/rynnbrain/install-service.sh

# 2. 启用并启动
systemctl --user daemon-reload
systemctl --user enable --now rynnbrain

# 3. 验证
curl -s http://127.0.0.1:8786/health          # {"ok": true, "model": "2b-bf16"}
journalctl --user -u rynnbrain -f             # 看模型加载 / 请求日志
```

`Restart=on-failure`、`TimeoutStartSec=300`（9B 量化加载慢）。unit 里的
`Environment=` 就是全部旋钮，`systemctl --user edit rynnbrain` 可加 drop-in 覆盖。

## 开发态：前台手动跑

```bash
bash scripts/rynnbrain/start_rynn.sh                         # 默认 2B，前台
RYNNBRAIN_MODEL_SPEC=9b-nf4 bash scripts/rynnbrain/start_rynn.sh
RYNNBRAIN_WS_ENABLE=1 bash scripts/rynnbrain/start_rynn.sh   # 带 ws 老客户端
```

端口占用时会提示（可能 systemd 已在跑），不重复启动。

## 文件

| 文件 | 作用 |
|------|------|
| `server.py` | 统一入口：加载模型 + 起 HTTP 边车（+ 可选 ws）；配置全走 env |
| `rynn_http.py` | 纯 stdlib HTTP 边车（`/infer` `/health`），server.py import 它 |
| `start_rynn.sh` | 前台手动启动（开发/调试） |
| `install-service.sh` | 生成 `~/.config/systemd/user/rynnbrain.service` |
| `README.md` | 本文件 |

## 冒烟自测

```bash
python - <<'PY'
import base64, time, httpx
img = base64.b64encode(open(
    "/home/yusenzlabpc/Desktop/Learning_based_model/rynnbrain_test/outdoor_scene.jpg","rb"
).read()).decode()
t=time.time()
r=httpx.post("http://127.0.0.1:8786/infer",
    json={"image":img,"text":"Describe the scene in one sentence.","think":False},
    timeout=60)
print(round(time.time()-t,2),"s ->", r.json())
PY
```
