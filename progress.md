# Zeno — progress

更新：2026-07-10。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)。
当前分支 **hw-go2w-real**（off main b6b94b9；未 push，未动 main）。

## Works（已验证）
- **P5.4 真机世界 go2w_real（本轮，hw-go2w-real 3 提交）**：CEO 2026-07-10 裁定解锁
  （本 NUC / 无 unitree_sdk2 / verify 真值=/state_estimation 里程计 / 只消费现有话题）。
  - 驱动 go2w_hw.py::Go2WHardware：navigate_to 发 /way_point 一次+轮询里程计（停滞/超时
    →/nav_cancel）；/teleop_cmd_vel 钳 0.6m/s、walk 5Hz 刷新（<0.4s deadman）；Trigger
    助手 standup/liedown/estop/estop_release(=resume)/manual/nav_cancel。rclpy 懒加载。
  - 世界 go2w_real*.py::Go2WRealWorld（go2w 真机孪生，同 CLI/工具/技能/verify 接缝）：
    工具 go2w_real_{bringup,navigate,where,stop,manual,resume}；技能 navigate/
    move_relative/standup/liedown/stop；verify at/moved 只读 /state_estimation（Inv-1）
    fail-safe；禁内核 sim/diag/system；registry.py 懒注册（Inv-4）。42 新单测全绿，
    at/moved 经真 VectorEngine 到 verifier；文件 <400 行，内核未动，无新依赖。
- **P5.5 TARE 全自主探索接入（本轮 RED aa26a39 → GREEN d292316）**：
  go2w_hw_explore.py::Go2WExploreManager 管 `nav.sh explore` 子进程（idle→launching→
  exploring→finishing→stopped；孤儿检测→stopped+原因+后台 /nav_cancel 清死 TARE 残留
  航点）。诚实 oracle=TARE 自发 /exploration_finish Bool（源码核实）+ 里程计积分行程
  （explore_finished()/explored_progress() 双谓词，防"原地宣告完成"）。stop=SIGINT 自有
  子进程→/nav_cancel→resume 受 estop 闩锁守卫（绝不代放操作员急停）。OverlayLauncher+
  TravelTracker（go2w_hw_overlay.py）供 route 复用；世界层 explore 工具/技能/verify/
  vocab + 4 个 `# v2-extension point` 追加式接缝（并行 feature agent 插点）。
  57 新测全绿；tests/unit/hardware+tests/vcli 失败集与基线逐字节一致。
- **go2w（sim）E190 守卫补齐（0cce3a6+2f72679，opus APPROVE）**：ensure_finite_nav_goal
  进 4 个 LLM 可达 waypoint 落点；tripwire 证明拒绝先于发桥；守卫套件 20/20。
- **go2w 相对移动 + strategy↔skill 接缝修复（aaa25ae）**：半配置 vocab 清空 KNOWN_
  STRATEGIES 根因修复；move_relative 技能；裸名归一化；preflight 扩校验。
- **F1+F2 合入 main（3ead15b）**：BYO 世界一等公民化；go2w 内置；E2E 锚 verdict GROUNDED。

## Failed / 教训
- **go2w.py（sim 世界）E190 缺口（既存非本轮引入；已修，见 Works）**：navigate_to 曾裸发
  NaN 到桥，基线 b6b94b9 同红——教训：新增 goal sink 必须过 E190 元测试（AST 扫全部源码）。
- 半配置 DecomposeVocab 是 foot-gun：空集≠None 会清 registry 推导；要么不注入要么注入完整。
- 新 venv 装最新二进制→pinocchio 段错误；须 constraints.txt 镜像。
- .env gitignored 不随 clone；PTY/sim 测试对宿主负载敏感——parity 对照比"绝对全绿"诚实。

## 环境镜像清单（冷启动新机器必读）
本轮 .venv = python -m venv + `-c constraints.txt -e .[dev]`（systemd-run MemoryMax=9G）；
足够跑纯单测（含 cli 导入）。完整跑（sim/perception）另需 `[all]` + clip@git +
`-e ~/Desktop/go2-convex-mpc --no-deps`。gitignored 资产须从上游工作树同步：
mjcf/{go2,g1}/scene_*.xml（缺失致 6 个 sim 测 FileNotFound，既存环境性）、assets/、
config/{user.yaml,boundary.ply,workspace_calibration.yaml}、.env、robot_mode.txt。

## Next
1. **go2w_real 真机 E2E 验收（等 owner 在场）**：源 ros_env.sh → nav.sh start（40-60s）→
   `zeno --world go2w_real` → "站起来，往前走 2 米" → verify at(tx,ty,tol=1.5) GROUNDED；
   再"探索"→ explore_finished() 且 explored_progress()>N。E-stop 遥控在手。
2. 并行 feature agents 插 v2-extension point（route 复用 OverlayLauncher；工具名须加进
   tests/vcli/test_world_go2w_real.py::_EXPECTED_TOOLS——类目按相等断言）。
3. task#12 Zeno 身份修复（VectorEngine 改名、docs VECTOR_*→ZENO_）。
4. 待 CEO RULING：docs/RULES.md loop 章节悬空指针修剪；pyserial/scservo 依赖门。

## 关键背景
- go2w=Isaac 数字孪生（HTTP 桥 127.0.0.1:8042）；go2w_real=真机（nav 栈 ROS_DOMAIN_ID=20
  CycloneDDS，~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh）。同 CLI，sim↔real 对称。
- 真机 verify 唯一真值=/state_estimation 里程计（无 /gt）；栈健康唯一真值=nav.sh status。
