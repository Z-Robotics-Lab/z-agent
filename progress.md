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

## 本轮：全局位姿意识 — 两个即插即用世界钩子（CEO 指令 2026-07-13 夜,c7216a3 RED→1499720 GREEN）
- **缺口(已证实)**:计划期 world context 被 5s TTL 缓存(0.6m/s 下最多 3m 陈旧);native 循环模型迭代间
  完全无位姿刷新。**钩子 A** engine._effective_world_context_ttl():世界可声明 world_context_ttl()
  (缺省/异常=5.0s 逐字节不变);go2w_real 返 0.0(位姿=驱动缓存属性,零成本)。**钩子 B**
  native_loop._live_status_block():每次 backend.call 前重读世界 live_status_line(agent),
  追加单条带标记 system 块(_LIVE_STATUS_PREFIX,替换不累积,不进 session;无钩子=同一 prompt 对象)。
- **go2w_real 行**:pose x/y(2位) yaw 度+弧度 | course 意图+drift | odom age;odom_age_s()=None →
  诚实 '(no odometry — stack down?)'(永真教训)。计划期上下文加"度"未做(需钩子外内核手术,已注记)。
- **测试**:test_world_pose_hooks.py(7,内核) + test_world_go2w_real_pose.py(5) 全绿;tests/vcli
  28F=15 基线 + 13 兄弟轮 places RED(4aa0bf3,其 GREEN 未落);unit/vcli 5F 全基线。0 新失败。

## 前轮（已签核）：航向意图(COURSE)追踪 — 相对计划漂移补偿（9035f96 RED→2c475aa GREEN,签核 da1da47）
- CourseTracker(go2w_real_course.py,确定性,骑 base.course_tracker):turn 补偿 wrap(course−actual),
  45° 上限重锚定;move_relative 沿 course;navigate/route/explore/estop/interrupt 重置;
  course_locked(tol_deg=10) oracle。36 测全绿,integrator 复核 0 新失败(基线见 Failed 节)。

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
