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

## 本轮 orchestration round（DONE — turn/viz/where/快速状态/复合few-shot）
新增全部 **world 文件 only**,内核零改(cli/engine/native_loop/cognitive 自 1cfde15 逐字节不变已核):
- **turn 技能**：direction(left|right)+degrees(默认90,掉头=180)→signed delta→Go2WHardware.rotate
  (角速度-only /teleop_cmd_vel 5Hz,里程计 wrap-aware 追踪,到点早停,_nav_abort 取消缝,estop 快失败)。
  verify **turned(min_deg)**(里程计 yaw,首调捕原点返 False,|wrap delta|≥min_deg;wrap 封顶180°)。
  few-shot: 左转90°→turned(54)、掉头→turned(108),单步无 bringup。
- **viz/where 升格技能**：VizOverlaySession 单一 launcher 表(embodiment._viz==base.viz_manager,tool 与
  open_viz 技能共享,决不双开 RViz;已开=already_open 幂等)。where 读活位姿,里程计未到则诚实拒绝(0,0,0 非真位姿)。
- **bringup(status) 快速路径**：odom_fresh(<3s)→<1s 从驱动已知事实答(话题率/odom 龄/estop),陈旧/无 base
  才回落慢 nav.sh 探针。lifecycle ready-probe 同样 odom 新鲜即真、免烧 settle。
- **复合指令 few-shot + 规则 1d**：把丢 rviz 子句的旧 2 步例替成完整 3 步链(bringup←open_rviz←stand_up);
  capabilities 规则 1d = 复合请求每个子句都成一步,决不静默丢步。

## 复核（integrator, 2026-07-13）
- 新测 68 绿（9 unit rotate + 21 turn + 13 ops + 10 fast-status + 9 vocab-fewshot + 6 vocab-integrity）。
- 全套回归 **0 新失败**：tests/vcli 934 passed/33 skipped(15 fail 全既存基线);tests/unit/hardware
  267 passed(6 fail+63 collect-error 全既存)。interrupt cancel 隔离跑 2 passed(满载下才 timing flake)。
- 离线 smoke 绿：resolve_world→build_embodiment 有 turn/open_viz/where + _viz is base.viz_manager;
  decompose strategies==descriptions keys 含 3 新;verify ns 服务 turned;deny 12 不变;
  RealTurnSkill fake base 旋转+driver _nav_abort 取消缝解阻+estop 快失败,全绿。
- 内联清理(已提交):turn_skills 去未用 `Any` 导入 + 修正 yaw-rate guard 注释(1.0→驱动 MAX_YAW_RPS)。
- 未动他 agent 在飞的 DeepSeek v4-pro 改(working tree .env.example/install-launcher.sh/config.py + 已提交
  2d06aa9 RED,test_config_env_credentials GREEN 系其人所属),不入我 commit(NEVER-KILL-INFRA)。

## Next
1. **真机 E2E 验收（Inv-2:裸 zeno REPL+眼看硬件,等 owner+E-stop 在手）**:「左转90度」→ verify
   turned(54) GROUNDED;「启动导航,打开rviz,站起来」→3 步全执行不丢子句;bringup(status) 实测 <1s;
   物理倒车 twoWayDrive 复测;掉头 180° 里程计 wrap 越 ±pi 判定正确。
2. camera 若要一等 look_skill STRATEGY:注册 look 技能+_build_context 加 vlm 服务,走接缝。

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
