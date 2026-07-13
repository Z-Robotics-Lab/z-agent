# Zeno — progress

更新：2026-07-13（夜）。fork 自 vector-os-nano @ R715 (12f3e15)。分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **P5.4 真机世界 go2w_real**：Go2WHardware 驱动(/way_point+里程计轮询;/teleop_cmd_vel 钳幅+deadman;
  Trigger standup/liedown/estop/resume/manual/nav_cancel)。世界同 CLI/工具/技能/verify 接缝。
- **v2 探索/route/camera**：ExploreManager/RouteManager/Camera(BEST_EFFORT,坏帧丢弃)。
- **sim→real 内核迁移 + world-layer 快赢 + moved() 驱动锚**：见 git log(d5d78a7→73ebe58),全绿 0 新失败。
- **verdict 谓词角色映射（CEO 批,c162d9a→3b2166c）**：世界注册 bool 谓词(stack_ready/at/turned/…)
  经 verify_predicate_names 同源接地;verify-only 通过步=接地观察;全绿轮 N/N grounded。

## 本轮：TYPED INTERJECT 插队 + /permissions 持久化（CEO 批 2026-07-13 "1,2 要做",0f361e9 RED→0313891 GREEN）
- **现场缺口（2026-07-11）**：任务执行中无法 prompt,Ctrl+C 是唯一通道。
- **zeno/vcli/interject.py（新,<800 ✓）**：InterjectReader 后台 stdin 读线程,仅在阻塞 turn 执行期间
  开窗(select 轮询 50ms,永不阻塞 readline;不可 select 的流自动缴械=回到旧 typeahead 行为);
  行 FIFO 入队;cancel_current_motion=从 _operator_interrupt 原样抽出的取消接缝(世界
  on_operator_interrupt→else request_abort),Ctrl+C 输出逐字节不变(测试 pin)。
- **内核安全边界（native_loop）**：迭代顶(每次模型 round-trip 前)+多 tool-call 轮内每个 motor
  dispatch 前查队列;命中→同 Ctrl+C 接缝取消运动(只一次)+本条及剩余 tool_call 全部回
  cancelled-by-operator(is_error)+落出诚实局部 trace(只评已跑的步)。app_state 无 reader=逐字节旧行为。
- **REPL**：队列行回显 `⏸ 插队: <text>` 并作为下一轮立即执行;native 无动作但被插队→OWN turn
  (legacy 绝不重跑被覆盖的目标);unified/legacy 阻塞 turn 也开窗(打进来的行下一轮接管)。
  多行排队语义:最新指令赢(旧插队轮在首个安全边界被下一条再取消),每条都回显。
- **stdin 碰撞修**：ask_permission 全程挂起 reader(挂起=完全不 select,字节留给 Prompt.ask),
  y/n/a 永不被偷。VGG async 路径 prompt 本来就活着,窗口不开。
- **/permissions 持久化**：auto|manual 经既有 config.yaml 机制存取;两条 setup 路径(REPL+-p)启动加载;
  --no-permission 旗标永远赢;auto 启动每次会话必打 REAL-ROBOT 警告(绝不静默 auto)。
- **测试**：test_operator_interject.py 19 测(os.pipe 假 stdin+FakeToolScriptBackend,全 hermetic 不碰 pty)。
- **INTEGRATOR 签核 2026-07-13**：内核改动限批准 scope(verdict/cognitive/trace_store+cli 显示/interject/
  permissions,全 additive 默认 frozenset()=旧行为);无跨流串改(sibling ui/c 85798ce 不在本支)。三套核对
  =文档基线 0 新失败:tests/vcli 15F/972P、unit/vcli 5F/1041P(+2 cv2 collect)、unit/hardware 6F/276P/63
  collect-err(devworld-PTY 已用 421f885 worktree 证实基线同款;go2w_hw_interrupt 隔离通过=满载 flake)。离线
  冒烟绿:go2w_real 解析;6 谓词 oracle 标记齐,stack_ready() role-map→GROUNDED/kernel-only→RAN;turn 45°;interject 可导入。

## 路由取证（READ-ONLY,喂下一内核轮 — 坐下 未走 direct 短路）
- direct=True 短路只在 legacy 快速路径;REPL 默认 native ReAct 截获 action-shaped 意图,has_unverified_action
  门强制 verify → 姿态技能转圈。修点:native 放行 direct 姿态技能或内建 posture verify;native 抽参器认 'angle'。

## Next
0. **ui/cli-experience 分支（UI-only）**：CLI UX 重设计提案已落 docs/CLI_UX_REDESIGN.md
   （CoT/执行链/verdict 卡片/诚实计时）；实现中,worktree 隔离,基线 ddf2208。
1. **真机 E2E 验收（Inv-2:裸 zeno REPL+眼看硬件,owner+E-stop 在手）**:走路中打字插队→nav 取消+
   新指令接管;`⏸ 插队` 回显;permission prompt 不被偷字节;/permissions auto 重启仍 auto+警告;
   上轮 verdict N/N grounded 现场验证一并做。
2. **内核轮（喂:路由取证）**：native direct 姿态技能放行/内建 posture verify;'angle' 抽参。
3. camera 一等 look_skill STRATEGY:注册 look 技能+_build_context 加 vlm 服务。

## Failed / 教训
- **真机 E2E 未验收**：插队/持久化全 hermetic 单测,Inv-2 待硬件闭环(打字回显 vs Rich Live 流的
  终端 echo 交织只能现场确认;插队已用 ⏸ 回显行兜底"打了什么")。
- **prompt-vs-stream 垃圾化(既存)**：permission prompt 与流式框互相穿插的旧现象,本轮只修了
  新路径的碰撞(reader 挂起);Live.paused() 已有;彻底修需 prompt 全局串行锁,未动(记录在案)。
- **既存失败（勿追,全环境性）**：playground/perception/courtyard/native-PTY(1)/level66 +
  mujoco/cv2/mcp collect-error/spawn-OOM + acceptance_env/vision_judge/d1_reexec(unit 5)。
- **结构债（既存）**：native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体);go2w_real 516。
- **缓办残留（诚实记录）**：跨步因果归因未分级,与 shadow-MjData re-step 同一 deferral,docstring 已明示。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042);go2w_real=真机(nav 栈 ROS_DOMAIN_ID=20 CycloneDDS,
  ~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh)。同 CLI,sim↔real 对称。verify 唯真值=/state_estimation
  里程计(无 /gt);栈健康唯真值=nav.sh status。测仅经 `bash scripts/run-tests`(内存封顶,勿裸 pytest)。
