# Zeno — progress

更新：2026-07-10。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)。
当前分支 **hw-go2w-real**（off main b6b94b9；未 push，未动 main）。

## Works（已验证）
- **P5.4 真机世界 go2w_real（本轮，hw-go2w-real 3 提交）**：CEO 2026-07-10 裁定解锁
  （本 NUC / 无 unitree_sdk2 / verify 真值=/state_estimation 里程计 / 只消费现有话题）。
  - 驱动 zeno/hardware/ros2/go2w_hw.py::Go2WHardware（BaseProtocol 面）：navigate_to
    发 /way_point 一次（栈锁存追踪）+ 轮询里程计（到达+停滞检测，超时/停滞经 /nav_cancel
    撤销）；walk/set_velocity 发 /teleop_cmd_vel 钳到 0.6m/s，walk 5Hz 刷新（<0.4s 死人
    开关）；Trigger 助手 standup/liedown/estop/estop_release(=resume)/manual/nav_cancel
    （go2w_hw_services.py 混入）。rclpy 懒加载（导入不需 ROS 环境），复用 ensure_finite_*。
  - 世界 zeno/vcli/worlds/go2w_real*.py::Go2WRealWorld（go2w 的真机孪生，同 CLI/工具/
    技能/verify 接缝）：工具 go2w_real_{bringup,navigate,where,stop,manual,resume}
    （bringup→nav.sh 子命令 start/stop/status/up/down，非零退出如实上抛）；技能
    navigate/move_relative/standup/liedown/stop 经 Go2WHardware；verify 命名空间
    at(x,y,tol=0.8)/moved(min_m) 只读 /state_estimation（Inv-1，真机无 /gt）无桥时
    fail-safe False；persona=真机措辞（E-stop、无 reset）；essential 类目 {go2w_real}；
    禁内核 sim/diag/system（真机上失真，零误伤）。registry.py 懒注册（Inv-4）。
  - TDD 红→绿：42 新单测（20 驱动 + 22 世界）全绿；引擎接缝实证 at/moved 经真
    VectorEngine 命名空间到达 verifier，--world go2w_real 解析出 Go2WRealEmbodiment+
    Go2WHardware（离线未连）。相邻回归 go2w/nav_client/registry/boundary 100 绿。
    每个新文件 <400 行（最大 388）。内核脊柱未动，无新依赖。
- **go2w（sim 世界）E190 守卫补齐（本轮 0cce3a6+2f72679，opus 评审 APPROVE）**：
  ensure_finite_nav_goal 进 4 个 LLM 可达 waypoint 落点（embodiment.navigate_to 镜像
  真机侧、_drive_and_hold、go2w_navigate 工具、pick._approach）；tripwire 行为测试证明
  拒绝先于发桥；守卫套件 20/20 + firstclass 17/17。冻结位姿回发免守卫成立（hypot 门拦 NaN）。
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
   `zeno --world go2w_real` → "站起来，往前走 2 米" → verify at(tx,ty,tol=1.5) GROUNDED。
   验收面=bare zeno REPL，Invariant 2；单测绿 ≠ 验收。E-stop 遥控在手。
2. task#12 Zeno 身份修复（VectorEngine 改名、docs VECTOR_*→ZENO_）。
3. 待 CEO RULING：docs/RULES.md loop 章节悬空指针修剪；pyserial/scservo 依赖门。

## 关键背景
- go2w=Isaac 数字孪生（HTTP 桥 127.0.0.1:8042）；go2w_real=真机（nav 栈 ROS_DOMAIN_ID=20
  CycloneDDS，~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh）。同 CLI，sim↔real 对称。
- 真机 verify 唯一真值=/state_estimation 里程计（无 /gt）；栈健康唯一真值=nav.sh status。
