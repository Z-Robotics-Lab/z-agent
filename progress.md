# Zeno — progress

更新：2026-07-13（深夜）。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-real**（未 push/未动 main）；UI worktree ui/cli-experience 已并入。

## Works（已验证 / 单测 GREEN）
- **CLI UX P1–P3.6（ui/cli-experience 并入,owner 批）**:CoT/ChainView/verdict 卡/trace+route；P3.3 composer；
  P3.4 owner ZENO 字标+响应式；P3.5 `●` 开放回答+去重复脚手架；P3.6 Thinking 心跳+tail 两行预览(`/why`展开)+
  `◇ Tool` 暗层+Logo 动画；markup 注入防线(16 审查 findings 修毕)；变更+邻接簇 191P+裸/DeepSeek PTY,0 新失败。
- **P5.4 真机世界 go2w_real**：Go2WHardware 驱动(/way_point+里程计轮询;/teleop_cmd_vel 钳幅+deadman;
  Trigger standup/liedown/estop/resume/manual/nav_cancel)。世界同 CLI/工具/技能/verify 接缝。
- **v2 探索/route/camera** + **sim→real 内核迁移+快赢+moved() 驱动锚** + **verdict 谓词角色映射** +
  **TYPED INTERJECT + /permissions 持久化** + **全局位姿意识钩子**(world_context_ttl=0;live_status 单块)。
- **PLACES 空间会话记忆**(4aa0bf3→20783ba):PoseLedger 起点/面包屑(20)/命名地点,mark_place/goto_place,
  where 增强;坐标只来自里程计,重启导航栈后地点失效如实报。51/51 绿。
- **COURSE→INTENT POSE**(本轮重设计,见下)。course_locked() oracle 不变。

## 本轮:INTENT POSE 重设计 — 现场事故 2026-07-13 15:32(ca5bc3e RED→272659e GREEN)
- **现场事故(真机)**:'前进3米,左转90,前进1米,右转90,前进3米'。腿1 短停 0.5m 于 (2.54,-0.02) 且
  朝向 -179.5°(twoWayDrive pathFollower 追点途中倒车翻转,导航栈侧并行修)。我方 >45° course 重锚定
  吞下了这个野 yaw,腿2 '前进3米' 倒着开 3m 到 (-0.36,-0.09)——自家补偿上限反转了操作员的计划。
  操作员判词:'避障会影响机器人对自己全局位置的判断,多个小任务组合执行不行'。
- **重设计(go2w_real_course.py)**:CourseTracker=完整计划坐标系(航向意图+**位置意图**)。
  ①move=位置追逐:目标=意图位置+d·course 方向;下发后意图前进**全额 d**(不管实际停哪)——短停/避障
  位移在下一腿自愈,不累积(操作员'全局意识'之位置半);②航向意图**绝不**被野 yaw 重锚定(resolve()
  只举旗,45°=大声上报阈值,REANCHOR_LIMIT_DEG 语义改);③turn 转向**绝对目标** wrap(course+delta),
  下发角按构造 ≤180°,>45° 偏差上报 '注意:检测到大幅航向偏离X°,已按计划航向补偿';④位置唯一可
  重锚定:腿起点偏离计划轨迹 >1.5m(POSITION_REANCHOR_M,大绕行/人工接管=计划系过期)→锚到实际并
  如实说;⑤manual 接管+resume(技能与工具双路径)重置意图;原 estop/stop/interrupt/自由导航照旧。
- **金测试**:test_world_go2w_real_intent_pose.py 逐字回放现场 oplog——腿2 目标 ≈(6.07,0.00) 且
  course 仍 +0.6°,绝不倒车;短停自愈跨两腿;>1.5m 诚实重锚定;>45° 大声上报;manual/resume 重置。
  course 套件语义变更处成心改(重锚定测试→保意图测试)。能力卡+vocab:位置+航向意图,move 瞄准计划轨迹。
- **oplog 卫生(同轮)**:真机日志 15:00-15:24 混入假测试事件(open_viz pid4242/teleport/mark'A'假坐标)。
  重定向改为 tests/vcli/conftest.py autouse fixture(全 vcli 测试写 tmp_path),删 6 处逐文件重复,
  test_oplog_hygiene.py 钉死默认路径测试期绝非 ~/go2w-nuc。
- **测试**:go2w_real 全套 310P + hardware 驱动套件 119P;0 新失败。并行会话 ui/cli-experience 合并
  期间等待其完结后才提交(NEVER-KILL-INFRA,无冲突:世界文件 vs vcli 核心)。

## Next
0. **UI 下一轮**:纯 CLI 可做长动作进度或 /history；GUI WebSocket tail 是新跨进程接口,待 CEO gate。
1. **真机 E2E 验收(Inv-2)**:重放 15:32 五步计划——短停+yaw 翻转下腿2 必须继续向前;>1.5m 绕行看
   诚实重锚定消息;places 现场;重启导航栈后地点失效话术。owner+E-stop 在手。
2. 导航栈侧 twoWayDrive 倒车翻转修复对齐后,复核 0.5m 短停(arrival radius)是否可收紧。
3. 内核轮(路由取证):native direct 姿态技能放行/内建 posture verify;'angle' 抽参。
4. camera 一等 look_skill STRATEGY。

## Failed / 教训
- **教训(本轮)**:'重锚定到实际'类安全上限必须区分**航向**与**位置**——航向重锚定会把执行器故障
  (倒车翻转)洗成'操作员意图',把 forward 变 backward;位置重锚定才是对的过期计划系处理。
- **真机 E2E 未验收**:intent-pose/places 全 hermetic 单测,Inv-2 待硬件闭环。
- **既存失败(勿追,全环境性)**:playground/perception/courtyard/native-PTY(1)/level66(vcli 15) +
  mujoco/cv2/mcp collect-error/spawn-OOM + acceptance_env/vision_judge/d1_reexec(unit 5)。
- **结构债（既存）**:native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体);go2w_real 620。
- **缓办残留（诚实记录）**:跨步因果归因未分级,与 shadow-MjData re-step 同一 deferral,docstring 已明示。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042);go2w_real=真机(ROS_DOMAIN_ID=20,
  ~/Z-Navigation-Stack)。同 CLI,sim↔real 对称；verify 唯真值=/state_estimation(无 /gt)；测仅经 `scripts/run-tests`。
