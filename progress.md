# Zeno — progress

更新：2026-07-10。fork 自 vector-os-nano @ R715 (12f3e15)。分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证）
- **P5.4 真机世界 go2w_real**：驱动 go2w_hw.py::Go2WHardware（navigate_to 发 /way_point+轮询
  里程计；/teleop_cmd_vel 钳 0.6m/s+5Hz deadman；Trigger standup/liedown/estop/resume/manual/
  nav_cancel；rclpy 懒加载）。世界同 CLI/工具/技能/verify 接缝；禁内核 sim/diag/system；registry
  懒注册（Inv-4）。at/moved 只读 /state_estimation 里程计（Inv-1）fail-safe。
- **P5.5 探索**：Go2WExploreManager 管 `nav.sh explore` 子进程；oracle=/exploration_finish
  （TARE 自发）+里程计行程双谓词防"原地宣告完成"；stop=SIGINT→/nav_cancel→resume 受 estop 闩锁守卫。
- **v2 route**：Go2WRouteManager 复用 OverlayLauncher(`nav.sh route`/far_planner)；发 /goal_point
  一次，far_planner 自 republish；到达以里程计判定（Inv-1）；verify route_reached。frozen 加字段守 Inv-7。
- **v2 camera**：Go2WCamera+CameraMixin 订 /camera 图像（BEST_EFFORT，手工 decode 无 cv_bridge，坏帧丢弃）；
  接缝点亮 look/describe（VLM mock 端到端绿）；未改 frozen capability 权威。
- **产品面**：persona 由 go2w_real_capabilities.md 加载（改 md 即改自知，缺文件安全回退）；工具
  go2w_real_viz 经 OverlayLauncher 非阻塞拉 RViz（DISPLAY :0 兜底）；bringup_skill（启栈≠站立，阻塞到
  里程计就绪，verify stack_ready）+中文 few-shot；restart 仅 operator，settle-then-confirm 就绪，env
  指纹+result oplog；liveness 唯真值=里程计新鲜度（杀零位兜底 e969dfc）。

## sim→real 内核迁移（CEO 特批，本轮 integrator 复核 GREEN）
真机取证：内核教/评了本世界不服务的幻影谓词 → 'verdict 0/N grounded' 假 FAIL。全部 **ADDITIVE、
dev+go2w(sim) 逐字节不变**（无钩子/无字段=原文，守卫测已证），verify 只更严（Inv-1）：
- ①schema `_verify_teaching_tail`：只教在集谓词（at_position 在集=逐字节原文；at 在集教 at() tol
  语义不硬编码默认，tol 归世界 Inv-4；例句必来自在集）。
- ②native handle_verify 白名单=与 schema 同源 oracle 集；界外调用→纠错 is_error（不评估/不记步/
  不算 R274 spin 进展；已接受 verify 逐字节不变）。
- ③engine.verify_namespace_deny() 钩子（world merge 后 remove-only）；go2w_real deny 12 stub 名
  （含 get_position/get_heading——已核 world_context/actor_causation 直读 base 非 namespace，无载荷消费）。
- ④DecomposeVocab 末位 foreach_example（None=原样/''=删节/文本=替换）；go2w_real 抑制 foreach 例。
- 次级三项：恢复提示 no_base 去 start_simulation 幻影→agent.recovery_hints() 覆盖（go2w_real_bringup）；
  /reset supports_pose_reset()==False 诚实拒绝、不写 /tmp/vector_reset_pose、指站起来/resume；go2-SIM
  关键词梯 disable_keyword_ladder()==True 时改走本世界 registry 别名或响亮 fallback。
- 复核：新测 47 绿（24 unit + 23 vcli）；回归 ~505 passed / 9 skipped、**0 新失败**（native_loop/verify/
  cognitive/foreach/go2w-sim+real 世界/dev-world PTY/repl-cutover/arm PTY）；离线 smoke：dev+go2w_real
  裸 REPL 启动绿，go2w_real /reset 拒绝且不写旗标、dev /reset 仍写旗标（逐字节对称已眼验）。

## Failed / 教训
- **go2w_real 真机 E2E 未验收**：Inv-2 要裸 zeno REPL+眼看硬件；本轮全为纯单测（rclpy/subprocess mock）。
- **既存失败（勿追，全环境性，本分支未改涉及文件）**：vcli 6（scene_room.xml×4+PIL/mcp×2）；deepseek
  provider 3（仓根 .env 真钥被 load_dotenv 注入劫持断言，config/oauth 逐字节同基线）；mujoco/cv2/mcp
  依赖模块 collect-error/spawn-OOM。教训：测须 delenv 全部凭据源，不止 monkeypatch load_config。
- **结构债（既存，非本轮）**：native_loop 1666 / engine 2132 / cli 3115 / goal_decomposer 1161 行
  均 >800 硬上限（上游单体，本轮沿模块 append 保局部性，未拆）；go2w_real 468（>400 典型 <800）。

## Next
1. **go2w_real 真机 E2E 验收（等 owner 在场，E-stop 遥控在手）**：源 ros_env.sh → nav.sh start
   （40-60s）→ `zeno --world go2w_real` → 「站起来，往前走 2 米」→ **verify at(tx,ty) GROUNDED**（确认
   不再冒 at_position/detect_objects 幻影，纠错列表如触发则模型自修到 at）→「探索」explore_finished∧
   explored_progress>N →「去 (x,y)」route_reached →「看看前面」look/describe 出真实非黑帧。
2. 真机复测须确认：/reset 说"仿真专用、指站起来/resume"；no_base 失败提示指 go2w_real_bringup（非
   start_simulation）；decompose 提示零外来谓词；skill 失败纠错措辞对真机成立。
3. camera 若要一等 look_skill STRATEGY：注册 look 技能+_build_context 加 vlm 服务，走接缝（集合相等）。

## 关键背景
- go2w=Isaac 数字孪生（HTTP 桥 127.0.0.1:8042）；go2w_real=真机（nav 栈 ROS_DOMAIN_ID=20 CycloneDDS，
  ~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh）。同 CLI，sim↔real 对称。verify 唯真值=/state_estimation
  里程计（无 /gt）；栈健康唯真值=nav.sh status。测仅经 `bash scripts/run-tests`（内存封顶，勿裸 pytest）。

## 交接(2026-07-10 晚,会话中断点)
编排修复轮 workflow 中断于 Core 阶段(未落盘)。恢复方式(下个会话):
Workflow resume: scriptPath=~/.claude/projects/-home-yusenzlabnuc/eb4e2656-a625-4d5c-acf4-ca130b4846d0/workflows/scripts/orchestration-round-wf_4615d993-276.js, runId=wf_4615d993-276
或按规格重派,交付物:①turn技能(角速度5Hz经guard+turned(min_deg)谓词+左转/掉头few-shot)
②viz/where升格技能(VGG可编排,复合指令不丢步)③bringup status快速路径(odom新鲜<1s,免nav.sh六探针)
④复合指令few-shot(启动导航+rviz+站起来=完整3步计划)。
已验收:Ctrl+C安全中断✓ 幂等bringup✓ 词表整洁化✓ 倒车twoWayDrive✓(待物理复测)。
评分观感问题(全绿仍verified=False,actor因果NOT_GRADED)=脊柱缓办项,连同谓词角色映射设计。
