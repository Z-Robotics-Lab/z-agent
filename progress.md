# Zeno — progress

更新：2026-07-10。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)。
当前分支 **hw-go2w-real**（off main b6b94b9；未 push，未动 main）。

## Works（已验证）
- **P5.4 真机世界 go2w_real（hw-go2w-real）**：CEO 2026-07-10 裁定解锁（本 NUC /
  无 unitree_sdk2 / verify 真值=/state_estimation 里程计 / 只消费现有话题）。驱动
  go2w_hw.py::Go2WHardware（navigate_to 发 /way_point+轮询里程计；/teleop_cmd_vel 钳
  0.6m/s+5Hz deadman；Trigger standup/liedown/estop/resume/manual/nav_cancel；rclpy
  懒加载）。世界 go2w_real*.py 同 CLI/工具/技能/verify 接缝；禁内核 sim/diag/system；
  registry 懒注册（Inv-4）。at/moved 只读 /state_estimation（Inv-1）fail-safe。
- **P5.5 TARE 探索（RED 5306abc→GREEN e7935bc）**：go2w_hw_explore.py::Go2WExplore
  Manager 管 `nav.sh explore` 子进程（idle→launching→exploring→finishing→stopped；
  孤儿检测→后台 /nav_cancel 清死航点）。oracle=TARE 自发 /exploration_finish Bool（源码
  核实）+里程计行程，双谓词防"原地宣告完成"。stop=SIGINT 自有子进程→/nav_cancel→resume
  受 estop 闩锁守卫。OverlayLauncher+TravelTracker 供 route 复用；4 个 v2-extension 接缝。
- **v2 route（RED c388cbf→GREEN 63de802）**：go2w_hw_route.py::Go2WRouteManager 复用
  OverlayLauncher("route")=`nav.sh route`（far_planner 前台子进程，SIGINT 拆卸+孤儿检测+
  estop 守卫 resume）。发 /goal_point(PointStamped, map 帧)一次；far_planner 自republish
  /way_point（route 从不发 /way_point）。到达以里程计接近判定（Inv-1）；/far_reach_goal_
  status 仅作 liveness，绝非唯一到达权威。工具 go2w_real_route + 技能 route_via/stop_route
  + verify route_reached。RouteConfig/RouteStatus frozen（Inv-7）。
- **v2 camera（RED 136aff9→GREEN adac419）**：go2w_hw_camera.py::Go2WCamera+CameraMixin 订
  /camera/camera/color/image_raw（BEST_EFFORT depth1，骑现有节点，无新节点/spin/依赖）；手工
  decode（np.frombuffer+step 步幅裁剪，无 cv_bridge），坏帧丢弃保上一好帧。消费接缝 get_camera_
  frame(w,h)→(H,W,3)uint8（未流黑帧+1s staleness 警告，Go2ROS2Proxy 对齐）+has_camera()/get_
  camera_image() liveness → capability_profile.camera 报 True，点亮 look/describe（look.py 端到
  端绿，VLM mock）；未改 frozen capability 权威。
- **集成核验（本轮 integrator，独立复跑）**：8 工具/9 技能/services{explore,route}/5 verify/9
  strategies 集合相等（strategies==descriptions，每策略有同名注册技能，verify_functions==namespace），
  离线 smoke 全绿（无 ROS/sim）。内核零改；全文件 <400（go2w_hw 398/route 397/go2w_real 357 顶格）；
  无重复注册/冲突标记/硬编码密钥；4 接缝完好。实测 v2 世界+驱动 6 文件 97 绿；hardware ros2 全
  surface 104 绿；vcli 833 绿。

## Failed / 教训
- **go2w_real 真机 E2E 未验收**：Inv-2 要求裸 zeno REPL+眼看硬件；本轮全为纯单测（rclpy/
  subprocess mock）。真机首验收待 owner 在场（见 Next 1）。
- **deepseek provider 测 3 红=既存非本轮**：仓根真 .env(gitignored, DEEPSEEK_API_KEY) 被
  resolve_credentials 自动 load_dotenv 注入 os.environ；测未 delenv DEEPSEEK_API_KEY→真钥
  劫持断言。config.py/oauth.py 与基线逐字节一致，route/camera 未碰。教训：测须 delenv 全部
  凭据源，不止 monkeypatch load_config。（冷启动环境镜像：constraints.txt 镜像防 pinocchio
  段错误；.env gitignored 不随 clone；半配置 DecomposeVocab 空集会清 registry 推导——见 memory。）
- **产品面收口(RED e06c3b4→GREEN f2a3158+d9029df)**:persona 改由 go2w_real_capabilities.md 加载(agent 能力说明书,改 md 即改自知,缺文件安全回退);新工具 go2w_real_viz(open/close,view=main|explore|route)经 OverlayLauncher 非阻塞拉 RViz(nav.sh rviz* 已加 DISPLAY :0 兜底);launcher 尊重 ZENO_WORLD+条件 source NUC ros_env——本 NUC 裸 `zeno` 即真机世界(离线冒烟过:persona 843+2834 字加载成功)。
- **首触修复(RED→GREEN 同日)**:bringup_skill(启动导航栈≠站立,阻塞到里程计就绪,verify stack_ready())+ 中文 few-shot 消歧;explore/route 管理器经 driver 兜底(VGG 上下文无 world services——引擎属内核,世界侧走 base 属性)。真机 REPL 复测待跑。
## Next
1. **go2w_real 真机 E2E 验收（等 owner 在场，E-stop 遥控在手）**：源 ros_env.sh → nav.sh
   start（40-60s）→ `zeno --world go2w_real` →「站起来，往前走 2 米」→ at(tx,ty,tol=1.5)
   GROUNDED；「探索」→ explore_finished()∧explored_progress()>N；「去 (x,y)」route_via →
   route_reached()；相机「看看前面」→ look/describe 出真实非黑帧。
2. camera 若要一等 look_skill STRATEGY：注册 look 技能 + _build_context 加 vlm 服务（懒建
   Go2VLMPerception）+ look_skill 入 strategies∧strategy_descriptions（集合相等），走接缝。
3. task#12 Zeno 身份修复（VectorEngine 改名、docs VECTOR_*→ZENO_）。
## 关键背景
- go2w=Isaac 数字孪生（HTTP 桥 127.0.0.1:8042）；go2w_real=真机（nav 栈 ROS_DOMAIN_ID=20
  CycloneDDS，~/Z-Navigation-Stack via ~/go2w-nuc/scripts/nav.sh）。同 CLI，sim↔real 对称。真机
  verify 唯一真值=/state_estimation 里程计（无 /gt）；栈健康唯一真值=nav.sh status。
- 既存失败集（勿追，全环境性，涉及文件本分支均未改）：本轮实测 vcli 6 fail（scene_room.xml
  缺×4+PIL/mcp×2）+ deepseek provider 3 fail（仓根 .env 真钥劫持断言，config/oauth 逐字节同基线）；
  hardware/sim/* 及 mujoco/cv2/mcp 依赖模块 collect-error/spawn-OOM（本轮未整跑 sim 子集，非回归）。
