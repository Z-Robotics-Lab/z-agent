# Zeno — progress

更新：2026-07-13。fork 自 vector-os-nano @ R715 (12f3e15)。分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **P5.4 真机世界 go2w_real**：驱动 go2w_hw.py::Go2WHardware（navigate_to 发 /way_point+轮询
  里程计；/teleop_cmd_vel 钳 0.6m/s+5Hz deadman；Trigger standup/liedown/estop/resume/manual/
  nav_cancel；rclpy 懒加载）。世界同 CLI/工具/技能/verify 接缝；禁内核 sim/diag/system。
  at/moved 只读 /state_estimation 里程计（Inv-1）fail-safe。
- **v2 探索/route/camera**：ExploreManager(`nav.sh explore`,/exploration_finish+行程双谓词)；
  RouteManager(far_planner /goal_point,route_reached)；Camera(/camera BEST_EFFORT,坏帧丢弃,look/describe)。
- **sim→real 内核迁移（CEO 特批,已复核 GREEN）**：内核只教/评在集谓词(schema tail + native 白名单 +
  verify_namespace_deny 12 stub + foreach 抑制)；dev+go2w(sim) 逐字节不变,verify 只更严(Inv-1)。

## 前轮 orchestration round（DONE,叙事在 commit 里）
- turn 技能(rotate+turned(min_deg) 驱动锚)、viz/where 升格技能(VizOverlaySession 幂等)、bringup(status)
  快速路径(odom_fresh<3s→<1s)、复合指令 3 步 few-shot+规则 1d(决不丢子句)。全 world 文件,内核零改。
- 复核 68 新测绿,全套 0 新失败;moved() 驱动锚移植(下详)。测试卫生 isolated fixture 上提。

## world-layer 快赢（2026-07-13,d5d78a7 RED→78961f2 GREEN,纯 world 文件）
- **turn 前缀别名 + angle 镜像（快速路径安全）**：加 往左转/向左转/往右转/向右转/原地转/原地左转/
  原地右转（router 前缀匹配,'往左转动30度'不再整跳 LLM）。engine 快速路径按 NAME 抽 generic 参
  （认 'angle' 不认 'degrees')→给 RealTurnSkill.parameters 加 'angle' 镜像(_parse_degrees 已读该键),
  堵住 fast-path '左转45度' 落 degrees-default-90 的 45°→90° 实害。engine READ-ONLY 已核。
- **诚实倒车提示**：move_relative backward 零位移且未 latch → _stalled_hint 说 local planner 疑拒倒车
  (已知 nav-stack 待查),给 掉头+前进 workaround（或报操作员),不再 resume-goose-chase。direction/latched
  加参附加化(Inv-7,旧 2 参 navigate 调用不变)。
- **后退1米 few-shot**：单步 move_relative{backward,1} verify at(1.0,1.0)（语义正确无关倒车修复落地;
  技能诚实失败）。examples 4568→~5.1k 字符,仍 <6k 预算,无需删例。
- 新测 18 绿(quickwins),go2w_real 全套 168 绿+驱动 rotate/anchor 42 绿,0 新失败。

## 路由取证（READ-ONLY,喂下一内核轮 — 坐下 未走 direct 短路之谜）
- direct=True 别名的短路（立即执行免 LLM 计划）只在 engine._try_skill_goal_tree（VGG **快速路径**,
  legacy tool_use 分支)里读 SkillMatch.direct。但 2026-06-19 cutover 起 REPL 默认先走 **native**：
  cli.py:2719 `_repl_native_enabled() and _intent_actionable()`→_repl_attempt_native→engine.run_turn_native。
- 坐下 是 action-shaped(_intent_actionable=classify_intent().use_vgg=True)→被 native ReAct loop 截获,
  native_loop.py:1124 `has_unverified_action` 门要求 finish 前先 verify → 转圈 'verify required before finish'。
  direct 短路根本没跑（它在被 strangler 淘汰的 legacy 路径上）。**内核轮修点**：native 侧需识别 direct 姿态
  技能(liedown/standup)→放行 finish 免强制 verify,或给它们一个内建 posture verify。世界侧无法修（禁触内核）。

## moved() 驱动锚移植（2026-07-13 下午,c7ebba7 RED→73ebe58 GREEN）
- turned() 双转竞态(316772c/25ba40a)在 moved() 尚存且在册(few-shot 往前走3米 verify=moved(2.0)):首调
  捕原点必返 False→模型重走;命名空间会话级只建一次,旧原点还能让 guard 吃掉的走假过(_moved_origin 系死桩)。
- 修法:navigate_to/walk 命令起点采 move_anchor_xy(guard 后,refusal 不重锚;rotate 不碰),make_moved 只比
  活位姿 vs 驱动锚(无每调状态);vocab 签名+能力卡教 NEVER re-run a move。36 测绿,回归 0 新失败(基线不变)。

## Next
1. **真机 E2E 验收（Inv-2:裸 zeno REPL+眼看硬件,等 owner+E-stop 在手）**:「左转90度」→ verify
   turned(54) GROUNDED;「启动导航,打开rviz,站起来」→3 步全执行不丢子句;bringup(status) 实测 <1s;
   物理倒车 twoWayDrive 复测;掉头 180° wrap 越 ±pi 判定正确;「往前走3米」→moved(2.0) 首查 True 不重走。
2. **内核轮（喂:上「路由取证」）**：native 侧放行 direct 姿态技能(坐下/liedown)免强制 verify,或给内建
   posture verify;并让 native 快速路径按 'angle' 抽参(世界已加镜像,但 native 抽参器仍在内核)。
3. camera 若要一等 look_skill STRATEGY:注册 look 技能+_build_context 加 vlm 服务,走接缝。

## Failed / 教训
- **真机 E2E 未验收**：本轮全纯单测(rclpy/subprocess mock),Inv-2 未闭环。
- **既存失败（勿追,全环境性,本分支未改涉及文件）**：playground/perception/courtyard/native-PTY/level66
  + mujoco/cv2/mcp 依赖 collect-error/spawn-OOM。
- **结构债（既存,非本轮）**：native_loop/engine/cli/goal_decomposer 均 >800 硬上限(上游单体,沿模块
  append 保局部性未拆);go2w_real 516(>400 典型 <800)。
- **脊柱缓办项**：全绿仍 verified=False(actor 因果 NOT_GRADED)=谓词角色映射设计,待专项。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042);go2w_real=真机(nav 栈 ROS_DOMAIN_ID=20 CycloneDDS,
  ~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh)。同 CLI,sim↔real 对称。verify 唯真值=/state_estimation
  里程计(无 /gt);栈健康唯真值=nav.sh status。测仅经 `bash scripts/run-tests`(内存封顶,勿裸 pytest)。
