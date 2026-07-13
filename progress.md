# Zeno — progress

更新：2026-07-13（深夜）。fork 自 vector-os-nano @ R715 (12f3e15)。分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **P5.4 真机世界 go2w_real**：Go2WHardware 驱动(/way_point+里程计轮询;/teleop_cmd_vel 钳幅+deadman;
  Trigger standup/liedown/estop/resume/manual/nav_cancel)。世界同 CLI/工具/技能/verify 接缝。
- **v2 探索/route/camera**：ExploreManager/RouteManager/Camera(BEST_EFFORT,坏帧丢弃)。
- **sim→real 内核迁移 + world-layer 快赢 + moved() 驱动锚**：git log(d5d78a7→73ebe58),全绿 0 新失败。
- **verdict 谓词角色映射（CEO 批）** + **TYPED INTERJECT + /permissions 持久化**(0f361e9→0313891 签核)。
- **COURSE 航向意图追踪**(9035f96→2c475aa,签核 da1da47):CourseTracker 骑 base.course_tracker;turn 补偿
  wrap(course−actual),45° 上限重锚定;move 沿 course;自由导航/estop/interrupt 重置;course_locked() oracle。
- **全局位姿意识·钩子**(c7216a3→1499720):engine 世界可声明 world_context_ttl()(go2w_real=0.0,缺省 5.0s
  逐字节不变);native_loop 每次 backend.call 前重建 live_status_line 单块(pose 度+弧度|course drift|
  odom age;无里程计→诚实 '(no odometry)')。12 新测全绿。

## 本轮：空间会话记忆 PLACES — 起点/面包屑/命名地点（CEO 指令 2026-07-13 夜,4aa0bf3 RED→20783ba GREEN）
- **现场 bug**:操作员说'回到刚才的位置',模型无可解析对象,从对话文本臆造坐标开走。
- **go2w_real_places.py(新,399 行)**:PoseLedger=确定性会话记忆(Inv-1:模型可触发 mark/goto,坐标只来自
  里程计;odom_age_s()=None 拒写,绝无 (0,0,0) 假地点)。三事实:①ORIGIN 起点=首个新鲜里程计位姿一次性
  捕获;②面包屑 deque(N=20,(monotonic_t,x,y,yaw)),每个运动命令开始时压入(navigate/move_relative/turn/
  route_via/goto,latch 吞掉则不记);③命名地点 mark(name,pose),未命名自动 地点N。骑 base.pose_ledger +
  services['places'](同 explore/route/viz/course 接缝;无台账的外来 base 行为逐字节不变)。
- **mark_place 技能**(记住这里/标记这里[叫X]):存当前里程计位姿;params x/y 忽略;无里程计诚实拒绝。
- **goto_place 技能**(回到起点/回到刚才的位置/回去/回到X):解析 起点→origin、刚才/缺省→距当前≥0.3m 的
  最新面包屑(近处重复跳过)、否则命名地点(参数或话语内含名);estop 快拒;先 reset course(自由导航);
  压离开面包屑(goto 后还能'回去');base.navigate_to 驱动;verify_hint=at(解析目标,tol=1.0);
  未知地点拒绝并列出已知——绝不臆造坐标。
- **where 增强**:距起点距离+方位角、course+drift(锚定时)、已标记地点名;无里程计拒绝不变。
- **vocab+card**:策略 mark_place_skill/goto_place_skill;few-shot '回到起点'→单步 goto_place、
  '记住这里叫充电桩'→mark_place{name:充电桩};预算 5875/6000(裁 往前走2米+站起来,数学/单步教义他例已载)。
  能力卡 全局意识 节+诚实上限:地点活在当前 SLAM 图帧,**重启导航栈后地点失效**(持久化=重定位路线图项)。
- **测试**:test_world_go2w_real_places.py 51/51;全部 go2w_real 套件 269P;tests/vcli 全量
  15F/1064P/33skip/1xfail——15F 恰为基线集(基线 worktree da1da47 复现同 15F)。0 新失败。
- **集成签核**(本轮):内核仅两钩子 + 消费(缺钩子世界逐字节不变,已证);未动 cli/display/UI;
  三套件对基线 0 新失败(vcli 15F、hardware 6F+63err 均既存,interrupt 隔离 1P);离线 smoke 全绿。

## 路由取证（READ-ONLY,喂下一内核轮 — 坐下 未走 direct 短路）
- direct=True 短路只在 legacy 快速路径;native ReAct 截获 action-shaped 意图,has_unverified_action
  门强制 verify → 姿态技能转圈。修点:native 放行 direct 姿态技能或内建 posture verify;'angle' 抽参。

## Next
1. **真机 E2E 验收（Inv-2:裸 zeno REPL+眼看硬件,owner+E-stop 在手）**:方形路径闭环+航向补偿消息;
   places 现场:走几步→'记住这里叫充电桩'→绕开→'回到充电桩'/'回到刚才的位置'/'回到起点';
   重启导航栈后确认技能如实报地点失效。插队+permissions;verdict N/N 一并做。
2. **内核轮（喂:路由取证）**:native direct 姿态技能放行/内建 posture verify;'angle' 抽参。
3. camera 一等 look_skill STRATEGY:注册 look 技能+_build_context 加 vlm 服务。

## Failed / 教训
- **真机 E2E 未验收**:course/插队/位姿钩子/places 全 hermetic 单测,Inv-2 待硬件闭环(0.3m 召回距离、
  地点解析话术是否合身只能现场标定)。
- **既存失败（勿追,全环境性）**:playground/perception/courtyard/native-PTY(1)/level66(vcli 15) +
  mujoco/cv2/mcp collect-error/spawn-OOM + acceptance_env/vision_judge/d1_reexec(unit 5)。
- **结构债（既存）**:native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体);go2w_real 620。
- **缓办残留（诚实记录）**:跨步因果归因未分级,与 shadow-MjData re-step 同一 deferral,docstring 已明示。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042);go2w_real=真机(nav 栈 ROS_DOMAIN_ID=20 CycloneDDS,
  ~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh)。同 CLI,sim↔real 对称。verify 唯真值=/state_estimation
  里程计(无 /gt);栈健康唯真值=nav.sh status。测仅经 `bash scripts/run-tests`(内存封顶,勿裸 pytest)。
