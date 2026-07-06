# Z Agent — progress

更新：2026-07-05。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)，分支 main。

## Works（已验证）
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

## Next
1. F1（feat/f1-slim 分支，进行中）：修剪死重 → F2 一等公民化（--world go2w 删 shim）。
2. F1 剥离波次：playground → mujoco 硬件/世界 → SO-101 → perception(VLM)，每波全绿；
   末尾原子改名 vector_os_nano → z_agent（CLI: za）。
3. F2 一等公民化：接通 world.register_tools + --world 参数 + embodiment 正门 +
   World 生命周期钩子（setup/health/teardown）；go2w 世界从 go2W_Sim 迁入；删 3 shim；
   E2E 回归锚（agent 导航 verified=true）必须过。
4. P5.1 bringup/status/teardown 工具 + RViz；P5.2 TARE explore + Δexplored_volume 验证。
5. P5.4 真机（等 CEO 三决策：verify 语义 / NUC vs Orin / unitree_sdk2 依赖）。

## 关键背景
- go2W_Sim 仓库 = 数字孪生（Isaac 资产/CMU navstack/桥）；z-agent 经 HTTP 桥
  (127.0.0.1:8042) 控它；桥 API 是 sim/real 对称的合同面。
- 四份调研报告（vector_os_nano 生命周期 / go2w 编排 / TARE+RViz / 真机路径）：
  见 go2W_Sim 会话档案；TARE 在栈内现成、/explored_volume 是独立探索裁判。
