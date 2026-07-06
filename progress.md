# Zeno — progress

更新：2026-07-06。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)，分支 main。

## Works（已验证）
- **F1+F2 合入 main（3ead15b）**：修剪确证死重（-895 行 -14MB，测试夹具全保）；
  BYO 世界一等公民化——world.register_tools 接通、--world/VECTOR_WORLD(_PLUGINS)、
  build_embodiment 正门、setup/health/teardown 生命周期钩子、go2w 内置世界
  （vcli/worlds/go2w.py + 10 单测）。**E2E 锚（零 shim）**：`--world go2w -p 导航…`
  → arrived+held d=0.32 → verdict GROUNDED verified=True EXIT 0。
  集成门：vcli chunk 失败集 ≡ F0 基线（2 个表面新失败=worktree 缺 gitignored
  场景资产，补齐后 31/31——资产清单教训再次验证）。
- F0：完整历史已推 Z-Robotics-Lab/z-agent；loop 机器已剥；新宪法 AGENTS.md 落盘。
- **F0 关门：全套基线 parity 达成，fork 零回归**。tests/vcli 失败集逐项一致（8 个
  环境性 PTY 失败）；tests/unit 拆 4 子块全部 parity OK（唯一 delta
  test_cancel_exploration 双侧复跑均 ~50% 抖动=既有 flaky）；level71 段错误与
  ik_solver 17 错误（pinocchio 4.0 对 package:// 的本机解析怪癖 + 测试引用仓库外
  ~/Desktop/vector_ws 绝对路径）双侧一致。
- 环境固化：constraints.txt = 上游 venv 逐版本镜像（207 包）；venv 重建命令见下。

## Failed / 教训
- 新 venv 装最新版二进制（pin 4.x 最新/coal/numpy 组合）→ pinocchio 段错误；
  必须 `uv pip install -r constraints.txt` 镜像上游版本 + 另装本地包
  `-e ~/Desktop/go2-convex-mpc --no-deps`（PEP610 direct install，不在 PyPI）。
- .env（provider 密钥）gitignored 不随 clone——PTY 测试要真 CLI，必须手动复制。
- PTY/sim 测试对宿主负载敏感（Isaac 双容器在跑时 8 个 PTY 测试稳定失败，
  上游同样失败）——parity 对照是比"绝对全绿"更诚实的门。

## 环境镜像清单（冷启动新机器必读）
venv: uv pip install -r constraints.txt + clip@git(577b3cfa…d93eb3be) +
-e ~/Desktop/go2-convex-mpc --no-deps + -e . --no-deps。另需从上游工作树同步
gitignored 运行资产：hardware/sim/mjcf/{go2,g1}/scene_*.xml、assets/（g1 步态）、
config/{user.yaml,boundary.ply,workspace_calibration.yaml}、.env、robot_mode.txt。

## CEO 方针（2026-07-06 裁定）
轻量化点到为止：**保留原有 MuJoCo sim 与全部核心代码**（它们是脊柱回归测试的
夹具与必要基座），在此基础上叠加新能力；深度剥离与包改名（zeno →
z_agent / za）**推迟到后期架构重构时一并做**。F1 已做的仅是零引用死重
（-895 行 -14MB，全部经依赖审计），无需回退。

## Next
1. （改名推迟，见上方 CEO 方针）
2. P5.1 收尾：go2w 世界加 bringup/status 工具（调 go2W_Sim 的 bringup.sh/status.sh，
   经 setup 钩子或工具面）；go2W_Sim 侧脚本已真跑验收。
3. P5.2：explore 技能 + Δexplored_volume 验证谓词（go2W_Sim 桥端点已就绪）。
4. P5.4 真机（等 CEO 三决策：verify 语义 / NUC vs Orin / unitree_sdk2 依赖）。
5. 待 CEO RULING：docs/RULES.md loop 章节悬空指针修剪（F1 agent 依纪律停在 gate 前）。

## 关键背景
- go2W_Sim 仓库 = 数字孪生（Isaac 资产/CMU navstack/桥）；z-agent 经 HTTP 桥
  (127.0.0.1:8042) 控它；桥 API 是 sim/real 对称的合同面。
- 四份调研报告（zeno 生命周期 / go2w 编排 / TARE+RViz / 真机路径）：
  见 go2W_Sim 会话档案；TARE 在栈内现成、/explored_volume 是独立探索裁判。
