# Zeno — progress

更新：2026-07-13（晚）。fork 自 vector-os-nano @ R715 (12f3e15)。分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **P5.4 真机世界 go2w_real**：驱动 go2w_hw.py::Go2WHardware（navigate_to 发 /way_point+轮询
  里程计；/teleop_cmd_vel 钳 0.6m/s+5Hz deadman；Trigger standup/liedown/estop/resume/manual/
  nav_cancel；rclpy 懒加载）。世界同 CLI/工具/技能/verify 接缝；禁内核 sim/diag/system。
  at/moved 只读 /state_estimation 里程计（Inv-1）fail-safe。
- **v2 探索/route/camera**：ExploreManager(/exploration_finish+行程双谓词)；RouteManager(far_planner
  /goal_point,route_reached)；Camera(/camera BEST_EFFORT,坏帧丢弃,look/describe)。
- **sim→real 内核迁移（CEO 特批,已复核 GREEN）**：内核只教/评在集谓词(schema tail + native 白名单 +
  verify_namespace_deny 12 stub + foreach 抑制)；dev+go2w(sim) 逐字节不变,verify 只更严(Inv-1)。
- **world-layer 快赢（d5d78a7→78961f2）**：turn 前缀别名+angle 镜像(堵 fast-path 45°→90° 实害)、
  诚实倒车提示(_stalled_hint,附加参 Inv-7)、后退1米 few-shot。18+168 绿,0 新失败。
- **moved() 驱动锚移植（c7ebba7→73ebe58）**：move_anchor_xy 命令起点采锚(同 turned() 修法),
  make_moved 只比活位姿 vs 驱动锚;NEVER re-run a move 教进 vocab。36 测绿。

## 本轮：verdict 谓词角色映射（CEO 门已批,c162d9a RED→5feb14f GREEN,**内核 cognitive/verdict 特批改动**）
- **现场 bug**：真机全绿轮显示 `verify stack_ready() ✓ (actor=NOT_GRADED)` 却 `verdict RAN
  verified=False (0/1 grounded)`。根因非因果分级:R1 裸调用 grounding 只认内核硬编码
  _PREDICATE_ORACLES,世界注册谓词(stack_ready/at/turned/…)永远 RAN。
- **修 1 谓词角色映射**：evidence_classifier.predicate_oracle 标记世界 bool 谓词;
  verify_predicate_names 与 oracle_names 同源同命名空间采集(rule 3,角色随被服务的 callable 走);
  附加参数(默认 frozenset()=旧行为,fail-closed)贯穿 classify_verify_expr/classify_step_evidence/
  evidence_passed/step_evidence_ok/VerdictReport.from_trace+全部产出点(REPL native 显示、-p 两分支、
  engine._evidence_ok、executor 奖励门)。角色只能认已服务 oracle,结构守卫(or-True/裸 state/重言/
  STEP-13/15/D17)全不变。go2w_real 标 at/moved/turned/stack_ready/route_reached/explore_finished;
  explored_progress 仍 STATE(只 vs 常量接地)。
- **修 2 观察语义**：verified 评「目标态真值」;actor 因果为每步注记。UNCAUSED 降级只对 ACTED
  步(非空 strategy——teleport/带动作的基线已满足 no-op 仍 RAN);verify-only 通过步=接地观察
  (「栈开着吗/在哪」诚实绿),永不掩盖失败动作步(所有 checked 步仍须全 GROUNDED)。
- **现场形状 pin**（tests/vcli/cognitive/test_verdict_grounding_semantics.py,13 测）：bringup
  stack_ready-✓/NOT_GRADED⇒1/1 verified=True;五步全绿⇒5/5;单谓词失败⇒False。旧语义 pin 更新 3 处
  (unit noop、devworld C.3 PTY、trichotomy NO-OP);teleport/acted-no-op pin 不动。
- **回归**：tests/vcli 15 failed/972 passed=基线同款 15 既存失败,0 新增;tests/unit/vcli 仅 5 环境性
  既存失败(stash 复跑验证)。docs/VERIFY.md 增 Grounding semantics 小节。

## 路由取证（READ-ONLY,喂下一内核轮 — 坐下 未走 direct 短路）
- direct=True 短路只在 legacy 快速路径;REPL 默认 native ReAct(cli.py:2719)截获 action-shaped 意图,
  has_unverified_action 门强制 verify → 姿态技能转圈。修点:native 放行 direct 姿态技能或给内建
  posture verify;native 抽参器认 'angle'。世界侧无法修（禁触内核）。

## Next
1. **真机 E2E 验收（Inv-2:裸 zeno REPL+眼看硬件,等 owner+E-stop 在手）**:「左转90度」→turned(54)
   GROUNDED;全绿轮应显 `verdict GROUNDED verified=True (N/N grounded)`（本轮修复的现场验证）;
   复合 3 步不丢子句;bringup(status)<1s;物理倒车 twoWayDrive;掉头 wrap;moved(2.0) 首查 True。
2. **内核轮（喂:路由取证）**：native direct 姿态技能放行/内建 posture verify;'angle' 抽参。
3. camera 一等 look_skill STRATEGY:注册 look 技能+_build_context 加 vlm 服务,走接缝。

## Failed / 教训
- **真机 E2E 未验收**：本轮全单测+PTY(dev-world 观察语义有真 cli.main 覆盖),Inv-2 待硬件闭环。
- **既存失败（勿追,全环境性）**：playground/perception/courtyard/native-PTY(1)/level66 +
  mujoco/cv2/mcp collect-error/spawn-OOM。
- **结构债（既存）**：native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体);go2w_real 516。
- **缓办残留（诚实记录）**：跨步因果归因（动作步捅状态+后续 verify-only 观察）未分级,与
  shadow-MjData re-step 同一 deferral,docstring 已明示。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042);go2w_real=真机(nav 栈 ROS_DOMAIN_ID=20 CycloneDDS,
  ~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh)。同 CLI,sim↔real 对称。verify 唯真值=/state_estimation
  里程计(无 /gt);栈健康唯真值=nav.sh status。测仅经 `bash scripts/run-tests`(内存封顶,勿裸 pytest)。
