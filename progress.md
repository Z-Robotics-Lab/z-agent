# Zeno — progress

更新：2026-07-13（深夜）。fork 自 vector-os-nano @ R715 (12f3e15)。分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **P5.4 真机世界 go2w_real**：Go2WHardware 驱动(/way_point+里程计轮询;/teleop_cmd_vel 钳幅+deadman;
  Trigger standup/liedown/estop/resume/manual/nav_cancel)。世界同 CLI/工具/技能/verify 接缝。
- **v2 探索/route/camera**：ExploreManager/RouteManager/Camera(BEST_EFFORT,坏帧丢弃)。
- **sim→real 内核迁移 + world-layer 快赢 + moved() 驱动锚**：git log(d5d78a7→73ebe58),全绿 0 新失败。
- **verdict 谓词角色映射（CEO 批）**：世界 bool 谓词经 verify_predicate_names 同源接地,N/N grounded。
- **TYPED INTERJECT + /permissions 持久化（0f361e9→0313891,integrator 签核 2026-07-13）**：阻塞 turn
  中打字插队(取消运动+下一轮接管,Ctrl+C 逐字节不变);auto|manual 经 config.yaml 持久化+REAL-ROBOT 警告。

## 本轮：航向意图(COURSE)追踪 — 相对多步计划漂移补偿（CEO 现场 bug 2026-07-13 晚,9035f96 RED→2c475aa GREEN）
- **现场 bug**：'前进3米,右转90度,…'走方形歪掉 — 直线段局部规划器避障/修正微转,下一个"右转90°"
  从漂移后朝向转,误差逐边累积。CEO 意图:相对转向=相对预期航向;机器人自转必须入世界模型并补偿。
- **go2w_real_course.py（新,142 行）**：CourseTracker=地图系预期航向(None=未锚定);ensure() 首次锚定;
  resolve() 45° 上限(超限=绕行/人工接管→重新锚定,绝不静默大转);纯确定性(Inv-1,无 LLM 输入)。
  embodiment 持有,骑驱动 base.course_tracker + services['course'](同 explore/route 接缝)。
- **turn_skill 补偿**:command = requested + wrap(course−actual)(+12°漂移下右转90→实际下发-102°,
  requested+drift 保 >180° 请求的方向/幅度);补偿/重锚定诚实上报(result_data command_deg/
  compensation_deg/course_deg/course_reanchored + 中文消息);verify_hint=turned(0.6*|下发角|);
  成功 course:=target,失败/取消 reset(意图未知不猜)。
- **move_relative**:直线腿沿 COURSE 走(未锚定=活朝向即旧行为;移动不改 course)→方形边平行于意图。
- **reset 接缝**:navigate/route_via/explore start/stop(estop)/on_operator_interrupt 全重置 course。
- **course_locked(tol_deg=10) oracle**:|wrap(yaw−course)|≤tol,fail-safe False,predicate_oracle 标记;
  v2 标记点接线(namespace+vocab);set-equality 测试特意更新(_REAL_ORACLES/_ORACLES/_PRED_ROLES)。
- **vocab+card**:方形 few-shot('前进2米,右转90度'→move+turn,verify turned(54) and course_locked()),
  5966/6000 预算;能力卡新增 course 条目(补偿、45° 规则、reset 语义)。
- **测试**:test_world_go2w_real_course.py 36 测全绿(money test:+10°漂移右转90→下发-100°;方形 2 移 2 转
  终 course=-180°)。integrator 两套复核 0 新失败 vs baseline:tests/vcli 15F/1008P/33skip/1xfail
  (全=playground×10/perception×2/level66/native-PTY/courtyard);unit/hardware 6F/276P/63err
  (=g1_*×5 + go2w_hw_interrupt 满载 flake〔隔离 2P〕 + 63 sim-env collect-err)。offline smoke 三关全过。

## 路由取证（READ-ONLY,喂下一内核轮 — 坐下 未走 direct 短路）
- direct=True 短路只在 legacy 快速路径;native ReAct 截获 action-shaped 意图,has_unverified_action
  门强制 verify → 姿态技能转圈。修点:native 放行 direct 姿态技能或内建 posture verify;'angle' 抽参。

## Next
1. **真机 E2E 验收（Inv-2:裸 zeno REPL+眼看硬件,owner+E-stop 在手）**:方形路径闭环——'前进2米,右转90,
   前进2米,右转90'×2 => 回到起点闭合矩形;每个转向消息须显示航向补偿(航向补偿±N°,实际下发…°),
   verify 用 turned(54) and course_locked();看 oplog course/补偿行。插队+permissions 持久化;verdict N/N 一并做。
2. **内核轮（喂:路由取证）**:native direct 姿态技能放行/内建 posture verify;'angle' 抽参。
3. camera 一等 look_skill STRATEGY:注册 look 技能+_build_context 加 vlm 服务。

## Failed / 教训
- **真机 E2E 未验收**:course 补偿/插队全 hermetic 单测,Inv-2 待硬件闭环(真实漂移幅度、45° 上限
  是否合身只能现场标定;补偿消息已中文上报兜底可观察)。
- **既存失败（勿追,全环境性）**:playground/perception/courtyard/native-PTY(1)/level66(vcli 15) +
  mujoco/cv2/mcp collect-error/spawn-OOM + acceptance_env/vision_judge/d1_reexec(unit 5)。
- **结构债（既存）**:native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体);go2w_real 538。
- **缓办残留（诚实记录）**:跨步因果归因未分级,与 shadow-MjData re-step 同一 deferral,docstring 已明示。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042);go2w_real=真机(nav 栈 ROS_DOMAIN_ID=20 CycloneDDS,
  ~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh)。同 CLI,sim↔real 对称。verify 唯真值=/state_estimation
  里程计(无 /gt);栈健康唯真值=nav.sh status。测仅经 `bash scripts/run-tests`(内存封顶,勿裸 pytest)。
