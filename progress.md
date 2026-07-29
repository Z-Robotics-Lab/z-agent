# Zeno — progress

更新：2026-07-29。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-manip** =
hw-go2w-real（导航/CLI-UI，NUC 侧 45d0b90 回灌）+ hw-go2w-real-vision（RynnBrain 视觉感知，操作前置）合并。
不动 main。叙事在 commit message 里；本文件只留当前状态。两条工作线的 Works 并列保留（导航/UI 在下半，感知在上半）。

## Works（已验证 / 单测 GREEN）
- **manip_stack_up() oracle + -p 静态验收全通（2026-07-29 深夜，0855316）**：bridge 加
  `status_publisher_count()`（/z_manip/task/status 的 DDS 图 publisher 数——FSM 自己的节点是唯一
  publisher，actor 不可伪造），世界注册 `manip_stack_up()` 谓词，manip_bringup start/bringup 档
  加有界 FSM 确认等待(60s)+verify_hint。真机验收：`zeno -p "启动 mobile manip"` exit=0
  **verified=true GROUNDED(1/1)**；`打开rviz` 本地弹窗 10.5s 无 verify 空转（legacy 路径 GUI 动作
  exit=2 属 verdict 语义，改动=CEO gate 留议）；`演练:去公司厨房拿水瓶放篮子` native 路由
  fetch_and_place，exit=0 verified=true，35.9s 零运动。65+51 tests GREEN。
- **P1 native 主路径接 prompt 缓存（能力线，研究报告 §3 P1 / 短板 E1，2026-07-29）**：native 每轮全量重发
  ~200 行静态 system prompt(~2216 tok) + 全套 tool schema(~794 tok) + 增长历史，全价重算。三处 cache_control
  断点（≤4）：① `_native_system_prompt` 静态块打点；② `_native_tool_schemas` 最后一个工具打点（Anthropic
  缓存整个 tools 数组）；③ `_native_messages` 在尾消息**最后一个稳定块**打**轮转**历史断点。关键：把每轮变的
  live-status 位姿行**从 system 块搬到消息尾部**（断点之后）——原来它夹在静态 system 与历史之间，任何中途变动
  都会击穿其后全部前缀缓存（Anthropic 断点与 DeepSeek 磁盘前缀缓存皆然）；搬到最末=整段前缀稳定可缓存，位姿
  仍是模型最后读到的最新一行。openai_compat（DeepSeek 主力后端）：static system 前缀本就自动命中；`parse_usage`
  补读 DeepSeek 顶层 `prompt_cache_hit_tokens`（原只读 OpenAI 形状→DeepSeek 命中恒显示 0）；`convert_messages`
  修混合 tool_result+text 尾消息（原会丢弃 live 文本→DeepSeek 看不到位姿）。Anthropic 后端纯透传 cache_control。
  **量化（代表性 manip 世界）**：静态前缀 ~3011 tok/轮；6 轮 turn cold=18066 tok→warm~=5268(**省 ~70%**)，
  10 轮省 ~78%（Anthropic 缓存读 0.1x/写 1.25x 计）。**实测活体延迟须 owner 在真栈上跑**（本 agent 红线禁运动/
  无 API key）：`zeno -p "<多回合指令>"` 改前/后各 2 次，读回合延迟 + usage.cache_read_input_tokens。测：hermetic
  prefix-稳定性 + 断点落位 + token-省量 + DeepSeek usage/convert 共 15 测新增(test_prompt_cache.py)、pose-hooks
  4 测改钉 live→消息尾；tests/unit/vcli 1215 pass（3 既存 cv2/macOS env fail 无关）。**Inv-1 零触碰**（纯计费/
  传输层，verify 语义不动）。
- **P2 并行只读 tool call + P3 作动能力锁（能力线，研究报告 §3 P2/P3，2026-07-29）**：内核 `_run_concurrent`
  已在(engine.py)但 native 主路径对一条回复里的多个 tool_call 纯串行(native_loop for 循环)。**P2**：派发段按可
  并发性分区——只读工具(`_tool_is_read_only`=`is_read_only({})is True`，fail-safe 反面 of `_tool_is_effecting`：
  无访问器/异常→当作作动串行) ≥2 个才走 `_dispatch_readonly_batch`(ThreadPoolExecutor≤10)，结果按 tc.id 重排回
  **原序**(session/trace 顺序不变)；作动/verify/finish 严格串行、与只读批**互斥**(批先跑完再串行段)。只读经
  `runner.dispatch_readonly`**不开 step、不捕 baseline、不录 StepRecord、不认领能力**——只读永不改 actor 态，
  baseline 推迟到首个作动技能是评分中性，输出绝不进 verify 命名空间(守 R6 审计教训)。interject 已完成的只读观测
  照报、未跑的仍取消；事件在串行段按原序发(线程安全)。**P3**：`@skill(uses=[...])` 声明占用的作动资源，
  SkillWrapperTool.capabilities() 缺省从 motor/arm 元数据派生(arm/gripper 技能→{"arm","gripper"}、其余 motor→
  {"base"}、只读→空)，navigate 工具挂 {"base"}。新 `vcli/capability_lock.py`：CapabilityLock 非阻塞 claim
  registry(acquire 全或无原子、冲突返当前持有者名**明确拒绝而非死锁**、release 持有者作用域幂等、claim ctxmgr
  finally 释放)；runner.dispatch_skill 作动前 acquire、**finally 释放**(成功/异常/place 皆释放，抢占者永不楔住)，
  冲突回一条纠正 tool_result(同 post-place 守卫模式)。当前串行环里每作动 acquire+release 自身派发内，健康回合不
  自冲突；锁是 P2 并发批 + 未来后台/长时技能的安全轨。测 +14 hermetic(test_native_concurrency_caplock.py：
  barrier(3) 证只读真并发 + 原序稳定、barrier(2) 证作动不并发、锁冲突明确拒绝不死锁、异常路径 finally 释放、
  单只读走串行路径无回归)；native 回归 99 + import-firewall/verify-vocab 19 全绿。验收：`zeno -p "看看状态"`
  (dev 世界，零硬件零运动)exit 0、verdict GROUNDED verified=True(1/1)、session 零 motor 派发——行为无回归。
  **Inv-1 零触碰**(只读不产 StepRecord/不进 verify 命名空间；能力锁纯派发准入门、只会更严、不算 verified)。
- **fetch_and_place 复合技能（编排报告 P5 首个消费者，2026-07-29）**：新文件 `worlds/go2w_real_fetch_skills.py`
  = 显式阶段执行器（非通用图引擎）：bringup检查→goto_place(目标点)→approach_object(目标)→[gated]抓取→
  goto_place(篮子)→[gated]放置。失败即停：首个失败阶段停链并诚实报「哪一阶段/为什么/恢复建议/前序完成阶段无需
  重复」。**手臂双栅**：ZENO_ARM_ENABLE gate（默认关→跳过抓/放）+ 即便开也只 dry-run 规划（校验+日志，本文件零
  import piper/can、绝不触碰 CAN/executor）。**整链 dry_run**（或说“演练/预演”）：解析计划+查前置但**零 ROS 发布**
  （不发导航目标/manip 任务、不调任何子技能 execute）。**verify 守 Inv-1**：每阶段沿用既有 oracle（导航=at()、
  approach=approach_ready()），整体 verdict = 末态谓词合取（at(篮子) and approach_ready()）由脊柱评分，生产者从不
  自评 verified；dry-run 无物理主张→verify_hint="True"，失败→"False"。子技能可注入（hermetic 测）。对 go2w_real.py
  最小侵入（扩展标记处 1 import+1 register）。capabilities.md 同步（技能/阶段/arm gate 现状=未启用）。测 +12
  hermetic(test_world_go2w_real_fetch.py：dry-run 零发布/阶段顺序/gate 关跳过/gate 开仅规划/失败即停不越阶/
  bad_params/世界注册)；manip+fetch 71 pass、go2w_real 世界 29 pass。**验收**（无 API key→走真实生产线路而非
  LLM）：real 世界 embodiment→SkillWrapperTool→skill dry-run「去公司厨房拿水瓶放到篮子(演练)」exit 0、六阶段
  计划 grasp/place=would-skip(arm off)、verify_hint=True、零 ROS；fail-stop demo 无 bridge→bringup_check 停+
  no_manip_stack 恢复建议。**遗留**：LLM 驱动 `zeno -p` 活体验收 + real 全链(需 manip start + 底盘链)留 owner 现场。
- **manip 管线 bug①② + 分级 bringup（2026-07-29）**：① 退出安全 cancel（真机 rclpy/DDS domain 20 活体验证）：
  Go2WManipBridge.connect() 在 add_node（注册 runtime.shutdown atexit）**之后**注册 _atexit_cancel → atexit LIFO
  先跑我们的 cancel（context 仍活、spin 线程仍在 flush）、只对在飞任务发一次（send_task 置位/cancel_task 清位）；
  send/cancel 用 _rclpy_ok() 守 context 已拆时静默返 False（不再喷 C 层 "context is invalid"）。活体：后台
  `ros2 topic echo /z_manip/task/cancel` 收到 `data: true`，退出进程 stderr 全净（无 rcl 报错）。② verdict per_step
  归因修正：原 chain[-1] 会把 approach 后补看的只读 find_object 记成 strategy；native_loop._effecting_strategy()
  回溯到最后一个**生效(非只读)**技能，纯感知步回退 chain[-1]。③ manip_bringup 分级：start=感知+任务FSM+UI
  **零运动风险**（manip start，不碰底盘链，回复必带 UI 地址 http://127.0.0.1:8766）；start_base=NUC 底盘链
  (reactive-live) 单独运动使能动作（manip component restart reactive-control）；bringup=整栈冷启含底盘；每级带
  motion_enabling/show_ui。approach 底盘链前置检查（注入式探针才 ssh，默认路径不 ssh NUC；确凿 down→no_base_chain
  + recovery hint，未知→放行；stall/timeout 文案也指向 start_base）。persona/vocab/capabilities 同步。测 +20
  hermetic（manip 59 + native _effecting 3 + 桥退出 6），99 pass。**疑点③ 源码实证已对上**：FSM _status_pub
  用 latched_debug=RELIABLE+TRANSIENT_LOCAL depth=1，桥订阅同 QoS，匹配，无需改。
  **遗留（安全阻断）**：z_manip_task 包在 4090 主机/容器均未 build（find share/z_manip_task=空），活体 FSM seam
  E2E / zeno "FSM alive" 验收 / 全链 UX 预演需先在 4090 build+launch FSM（大节点面、含 coarse_nav，运动风险）
  且确认 NUC 底盘链 down——超本轮零运动/禁 build 安全边界，留给 owner 现场窗口（脚本命令见下 Next）。
- **打开rviz 本机弹窗 + GUI/查询类 verify 豁免（2026-07-29，真机 E2E PASS，CEO 授权）**：两处"agent
  不智能"根因。① ssh transport（nav host=无屏 NUC，opens_local_gui False）下 open_viz 不再返 remote_gui
  stub，而在 4090 本机 spawn `rviz2 -d <config>`：`_WorkstationRvizTransport` 复用 OverlayLauncher
  spawn/SIGINT/dedupe 生命周期，source go2w-nuc/bringup/workstation/ros_env.sh(DDS domain 20)、按 nav.sh
  模式选 Z-Navigation-Stack-go2w 的 rviz config(main/route=vehicle_simulator, explore=tare_planner_ground)、
  start_new_session detached（REPL 退出不带走 RViz）、无 DISPLAY 诚实降级 Foxglove 指针；3D View3D(Foxglove,
  NUC 侧构建)保留指针。真机 E2E：`zeno -p 打开rviz` → 4090 出现 `rviz2 -d .../vehicle_simulator.rviz`
  进程、回合无 forced-verify nudge（grep=0）。② verify_exempt 元数据串起 @tool/@skill/SkillWrapperTool，
  native_loop._tool_verify_exempt 让 open_viz/where/manip_status/robot_status 这类 GUI/只读查询在 finish-gate
  的"verify 前不许停"催促门豁免——豁免工具开 0 checked step、录 0 StepRecord，verify 评分/verdict 语义
  逐字不变（内核只松催促门，CEO 授权注释在案）。杀了实录里 open_viz 强制 verify 空转~1min。测 +12
  (8 workstation-rviz + 4 verify-exempt e2e)，48 pass；`看看状态` verified=True(1/1) 不被催。
- **find_object 全幅退化框拒识门（2026-07-29，RED→GREEN）**：实测 2B 对不在场物体
  (chair/keyboard/person/bottle/monitor)恒返回同一原点锚定近全宽框 (0,0),(648,290)@640x480，技能曾据此
  报假"椅子左侧+12.1°"。纯函数 `rynnbrain.is_degenerate_box(box, image_wh)` 按双坐标读法判退化
  （名义[0,1000] + sent_size 像素帧；面积≥85% 或 原点锚定∧跨宽≥90%）——纯面积门在两读法下都抓不住实测框
  (18.8%/60%)，原点+跨宽子句才是钥匙；`sent_size()` 收敛 _encode_frame 缩放规则为单一来源。find_object
  过滤退化框：全退化→诚实 object_not_found（消息教先 scene_query 确认在场再换措辞）；混用余下合法框。
  偏向拒识（假"未找到"一次重问可恢复，假方位污染后续决策）。测 +6=感知 27 绿、相关 vcli 133 绿；
  9b-nf4 对不在场是否更诚实待真机 A/B（`RYNNBRAIN_MODEL_SPEC=9b-nf4` 重启服务即测）。
- **stack_down() 关导航栈 verify oracle（2026-07-29，真机 E2E PASS）**：字段缺口=`zeno -p 把导航栈关掉`
  实测 NUC 栈关干净但 verdict=RAN verified=False(0/1 grounded)——decomposer/verify 无可表达"栈已关"的
  可 ground 谓词。世界层 APPEND-only 扩展（不动 verify 脊柱内核 vcli/cognitive/verdict）：
  ① `go2w_real_verify.make_stack_down()`=stack_ready() 的精确反面，读同一真值源(/state_estimation
  odom 新鲜度)——连着的驱动上 odom 陈旧(≥3s)或从未收到⇒栈已停 True；fail-safe False（无 base/断连不是
  `not stack_ready()`，断连不能确证栈停）；predicate_oracle 标记。② build_verify_namespace + vocab
  verify_functions/signatures + bringup_skill 描述教 stop 用 stack_down()；③ `把导航栈关掉` few-shot
  (verify=stack_down(), bringup action=stop, 不走 liedown)。真机 E2E（legacy 分解 ZENO_PRINT_NATIVE=0,
  只起停栈无运动）：round1 启动导航 verified=true(stack_ready)；round2 把导航栈关掉 **verified=true
  1/1 GROUNDED on stack_down()**；NUC nav.sh status 全 NO_DATA（栈关干净）。测：lifecycle 新增 stack_down
  真值源语义 9 测 + few-shot 断言，_REAL_ORACLES 扩入 stack_down；146 pass。
- **RynnBrain 感知轮（视觉线）**：ac74ffa(RED)→GREEN。真机世界长出眼睛——本地 RynnBrain 具身 VLM
  （GPU 工作站服务，模型选择在其 start_rynn.sh 里）经 JSON 边车 http://127.0.0.1:8786 接入：
  ①`zeno/perception/rynnbrain.py`：RynnBrainClient（httpx 现有依赖、零新库；`read_env("RYNNBRAIN_URL")`
  ZENO_ 优先；坐标解析 parse_boxes/parse_points 为纯函数，[0,1000] 归一化；PIL 懒导入，JPEG q85/长边 640；
  仅 transport 错误重试 1 次，4xx 不重试）。
  ②`go2w_real_perception.py` 两只读技能（native LIVE 路径经 wrap_skills 可见——category 工具对 native
  不可见，故必须是 SKILL）：`find_object(description)`→画面侧别(左/中/右)+水平偏角(度,左正,D435i
  HFOV≈69°)+框；`scene_query(question)`→思考模式问答。取帧用 get_camera_image()（None-honest，
  黑帧兜底永不喂 VLM）；帧龄>2s 在结果里警告。诚实失败梯：no_base/bad_params/camera_failed/
  no_vlm(recovery_hints 指向 start_rynn.sh)/object_not_found(教改用真实外观措辞)。
  ③接线：embodiment 持单客户端（services['rynn']+base.rynn_client 双缝）；vocab 三集合同步
  （strategies/descriptions/params_help，set 全等测试通过）；capabilities.md Vision 段改为真实能力
  （感知=决策输入，验收仍 at()/moved()/turned()，无 'look skill' 字样）。
  ④措辞雷全部避开：MOTOR_KEYWORDS 七词不进 effects/description（wrap 后 is_read_only+
  is_concurrency_safe，有测试钉死）；技能名避开 native 特判 navigate/detect。
- **CEO 门裁决（owner 2026-07-22 批准本轮计划即过门）**：新跨进程接口=RynnBrain JSON 边车
  http://127.0.0.1:8786（POST /infer{image b64,text,think}→{reply}，GET /health）；**零新依赖**
  （httpx/numpy 现有，Pillow 在 [perception] tier）。服务端边车在 Learning_based_model 仓（用户侧），
  与 ws://8782 同进程共存、共享推理锁；NUC 部署设 ZENO_RYNNBRAIN_URL=http://<工作站IP>:8786。
- **感知测试**：`test_world_go2w_real_perception.py` 21/21 全绿（解析纯函数/方位数学 cx=750→右-17.25°/
  三条诚实失败/思考透传/只读判定/接线/能力卡）。回归：tests/vcli -k go2w_real = 363 pass/3 fail——
  3 个全是既存环境性 viz_3d（本工作站无 ~/go2w-nuc，干净树复现相同失败，非本轮引入）；
  vocab/seam/lifecycle/verify_vocab_integrity 子集 97/97 全绿。
- **相机命名空间修复 + 视觉 E2E 真机验收（Phase 3，2026-07-29）**：默认相机话题 →
  **/nuc/camera/color/image_raw**（d435i.service /nuc 命名空间，BEST_EFFORT；env `ZENO_GO2W_COLOR_TOPIC`
  可覆盖）。带宽策略=**按需短命订阅 raw**：connect 不再持续订阅（跨机 raw 640x480@15Hz≈13MB/s 会饿死共享
  DDS 的里程计；感知只在 agent 决定"看"时触发）——取帧时才临时开 BEST_EFFORT depth=1 订阅→等一帧→退订，
  零基线带宽，复用现有 numpy 解码（无 cv2/compressed，相机侧零新依赖）。4090 跨 WiFi 实测取一帧 5/5、
  0.54–1.36s（中位 ~0.94s）。RynnBrain 编码需 Pillow→新增 **[perception-client]** tier（仅 pillow，非
  [perception] torch 栈）装进 venv。**真机 E2E（狗只上相机、nav/loco 全下，运动话题零订阅者→物理不可动）**：
  round1 `看看周围有什么`→native 路由 scene_query→真帧→"一个大的黑色箱子/black suitcase"（画面确为地毯上黑
  flight case）；round2 `找黑色的箱子在哪边`→find_object→side=左 +12.1°（箱子确在左上），79s。**两轮 verdict
  恒 RAN verified=False——视觉只作决策输入、Inv-1 未被污染**。已知限：2B 对不在场物体(椅子)返回全幅框→假定位
  (由 Inv-1 兜底不作验收证据；2026-07-29 已加拒识门，见上)。测：相机单测重写为按需契约 27 绿 + 感知 21 绿。
  （早期离线冒烟：真 PNG(448²)→JPEG(≤640)→假模型 HTTP 往返→方位+13.7°，仍在。）
- **CLI UI 立体化：braille 加载进度条 + 精简圆点树（导航/UI 线，设计工作流 w378ob0re + owner 定稿）**。
  纯显示层（turn_render.py），非 CEO 门槛。v1 三态箭头条(`●━→▶┄→○`)被 owner 否("箭头/方块圆圈不好看、
  没进度条感")，改 AskUserQuestion 出 5 套真实渲染让其拍板→选定：① **状态机=braille 加载条 + N/5 计数**：
  `⣿⣿⣿⣿⣿⣿⣀⣀⣀⣀⣀⣀⣀⣀⣀  执行 3/5`——统一 braille 字形(⣿ 已填/⣀ 未填,15 格=5 阶段×3)按 阶段/5 比例填充,
  只显当前阶段名 + 诚实 N/5(固定 5 阶段机,非伪百分比);sink 每进新阶段重发,scrollback 里填充向右推进;
  `完成 5/5` 转绿;分支(恢复/让位)用 reached_rank **冻结**计数在最后真实阶段、绝不假进(挂琥珀 `⑂`)。
  ② **behavior tree=精简圆点**：`├─ ● name` 挂 ⌂ 主干(去掉旧 `◇ Tool·` 杂讯)、状态 ✓/×/… 右对齐到固定列
  成清单(CJK 宽度用 rich cell_len,长名优雅溢出)、`│  └ verify …` 深一层缩进为工具子节点;流式恒 `├─`
  (append-only 不知末 child,诚实开放),final_lines 才闭合末节点 `└─`。诚实:只画已发生节点、无伪造未来/
  百分比/时长(守 Inv-1)。测:owner 定新设计→更新旧钉死字形(▶/◇Tool·/5阶段名/→)的断言到 braille+● 契约;
  120 显示测 GREEN(含 .venv 全依赖);4 场景(顺利/失败恢复/操作员让位/超长)真实渲染肉眼验收。真机 sink 待现场。
- **routed 导航不再让 agent 重规划**：routed stall 不 abort 而 RE-NUDGE far_planner（park+重发 /goal_point），
  同一次调用继续开；只有 overall timeout(120s)/操作员/far_reach 到达才结束，MAX_RENUDGE=8 兜底。navigate_to
  信 far_planner /far_reach_goal_status（到达=里程计 OR far_reach 且里程计 1m 内，绝不 far_reach 单独，守 Inv-1）。
- **框架结论=押注 native**（工作流 wv23zizqc）；VGG 保留休眠不复活其分解器。
- **Fix B（bag 实锤）**：navigate_to 发 /goal_point 让 far_planner 独占 /way_point（单写者），修掉 park 适得其反
  的零位移冻住。无 far_planner 回退直发 /way_point。RViz far_planner 4 display 并入 vehicle_simulator.rviz。
- **地标实时重读 + 模糊匹配**：refresh_marks_from_disk 每次调用前重读 places.json；_resolve_mark 精确→大小写无关
  →无歧义子串，多候选拒绝并列（Inv-1）；RealListPlacesSkill 答"能去哪"。`run-tests -k go2w_real`=352 pass。
- **电量% + 电压上状态栏**：unitree_control.py 转发 lowstate bms → /battery_state（035abfb，owner 批）；zeno
  订阅显示 `电量 NN%`（无源/陈旧→不显示，绝不编数）。**真机需 colcon build + nav 重启生效，待验。**
- **/clean 双确认清空地点**（INTEGRATOR 复核过）：clear_places 原子备份+清空，home 从 start_pose.txt 自动复原。
- **bringup 双模 transport（Phase 2，c4a17ee）**：`zeno/hardware/ros2/nav_transport.py` 收敛 nav.sh 执行——
  `GO2W_NAV_TRANSPORT=auto|local|ssh`（auto=本机有 nav.sh 则 local 否则 ssh；host=GO2W_NAV_SSH_HOST）。
  bringup 工具/skill、OverlayLauncher、route 常驻探针、viz 都调它，不散落 if-ssh。短命令 local `bash nav.sh`
  / ssh `ssh host 'bash ~/…/nav.sh'`（nav.sh start=systemd-run transient unit，ssh 短连接返回后 unit 续跑）；
  overlay(explore/route 是前台 exec ros2 launch)ssh 拆卸=pidfile 记远端 PID→`ssh host kill -INT <pid>`
  精确 SIGINT，守 NEVER-KILL-INFRA；viz ssh 下不远程开 RViz（NUC 无屏），提示 4090 本地 Foxglove/RViz。
  单测 test_nav_transport（新）+ overlay/route/lifecycle/bringup 子集全绿。
- **SSH bringup 真机 E2E（0963c00，PASS）**：`tests/e2e/e2e_nav_ssh_bringup.py` 走真工具+真 ssh transport,
  4090 起停 NUC 栈，独立判据 4090 侧 `ros2 topic hz /state_estimation`。实测(狗未上电,预建图重定位)：
  start map=zeno_office→NUC 起 zdog+zdog-route→/state_estimation 跨机 48Hz→where 读位姿→stop 干净拆栈,
  NUC 事后零残留。只读:不发运动话题、finally 必 stop。可重复：`tests/e2e/run_e2e_nav_ssh_bringup.sh`。
- **RynnBrain VLM 服务产品化收编进仓（Phase 3）**：`scripts/rynnbrain/{server.py, rynn_http.py,
  start_rynn.sh, install-service.sh, README.md}`——把桌面 rynnbrain_test 的服务端统一、参数化（原件不动
  不删）。默认 2B bf16（server 进程实测显存 ~4.7GB；grounding 冷 1.09s/热 0.51s、describe 0.4s），9B NF4
  是即插 `RYNNBRAIN_MODEL_SPEC=9b-nf4` 配置项。配置全走 `Environment=`（spec/路径/端口/设备/ws）；server.py
  不 import zeno、跑 `~/envs/rynnbrain` venv。HTTP 边车(8786)=z-agent 契约恒在（bind 失败即崩→systemd 兜），
  ws+msgpack(8782)老客户端边车默认关、opt-in（放 daemon 线程，绑定失败只记日志不拖垮 http）。生产态
  systemd --user：install-service.sh 生成 unit（Restart=on-failure、TimeoutStartSec=300、覆盖前备份到
  ~/deploy-backups-20260729）；4090 上 `enable --now` 已起并 enabled，`/health` 200 {"ok":true,"model":
  "2b-bf16"}，回复框 `<object>(x1,y1),(x2,y2)` 可被 parse_boxes 直吃。桌面 start_rynn.sh 仍可另跑(LIBERO)。

## CEO 现场验收清单（真机，owner+E-stop 在手 — 本轮未做）
① 工作站重启 start_rynn.sh（拾取 8786 边车），`curl http://127.0.0.1:8786/health` 应回 {"ok":true}。
② NUC 上 export ZENO_RYNNBRAIN_URL=http://<工作站IP>:8786；d435i.service 在流。
③ `zeno('看看金属碗在哪')`→find_object 报侧别+偏角；`zeno('桌上有什么')`→scene_query 思考问答。
④ 组合链：find_object→turn 对准→靠近→at()/turned() 里程计判绿（感知永不自证）。
⑤ 上一轮遗留：/clean 全流程 + /place_markers 3D 标签现场验收仍待执行。

## Next
0. **[2026-07-29 深夜已完成]** FSM 原来一直构建在 z-manip-runtime 镜像层（非"未构建"），缺的是生命周期
   owner——Z-Mobile-manip 已补 `manip start`(零运动:FSM+UI)/`manip fsm`/`manip start-base` 分级
   (e70352c..d8f2db9)，seam E2E 实录于该仓 docs/task-fsm-seam-e2e-2026-07-29.md；zeno 静态验收全通
   （见 Works）。**剩余=owner 现场活体窗口**：开 NUC/机器狗电源→`打开导航栈`→`manip_bringup(action=
   'start_base')`（急停旁）→真机 approach。当前留跑：FSM+UI 域 20、模型服务容器×4、RynnBrain :8786。
1. 真机执行上述感知清单（本轮 hermetic 21/21 + E2E 冒烟，硬件闭环未做）。
2. native 错配修复轮（独立分支）：native 通用提示教 at_position 但本世界 deny 之（真谓词 at）、
   native 丢世界 navigate 技能——感知教学在 native 靠技能 description 已覆盖，但整体错配待修。
3. 深度融合阶段2：订 depth 话题→像素+深度→map 米制目标（bearing 伺服先跑通再上）。
4. few-shot 预算：REAL_DECOMPOSE_EXAMPLES 护栏 2026-07-29 由 ~6000→6400（三处世界层测试同步），
   容纳新增 `把导航栈关掉` stack_down few-shot（现 6275/6400）；感知 few-shot 仍主动省略
   （descriptions+params_help 已承载教学）；若 legacy 分解实测不足再议腾挪。
5. **真机验收本轮 UI**：重启 zeno 跑一圈（站起/去地标/回home/失败恢复），眼看状态条填充 + 树轨是否更易读立体。
6. **电量真机验证**：`colcon build --packages-select unitree_webrtc_ros` + `nav stop && nav start zeno_office`；
   看状态栏 `电量 NN%`；首帧 `lowstate keys=…` log 确认电压字段名，不对则按真机字段微调 _on_lowstate。
7. operator RViz-goal detection 已 GREEN，真机闭环待现场。map-color-publisher.service 需 NUC 重启拾新代码。
8. **ssh 默认地图解析是客户端侧（遗留）**：resolve_bringup_map 查本机 ~/maps，4090 无地图库→默认 start 走"从零"
   而非 zeno_office（显式传 map 名可透传到 NUC 的 nav.sh 校验，E2E 即这么做）。Phase 3+ 若要 4090 默认预建图，
   需把默认地图探测也走 transport（ssh ls ~/maps）或读 NUC 的 current_map 握手。
9. **camera 话题命名（遗留，Phase 3 统一）**：go2w_hw_camera.py 订阅 /camera/camera/color/image_raw，
   NUC 现发布在 /nuc/camera/color/image_raw——接视觉时统一。

## Failed / 教训
- **全量 `tests/vcli/` 在 4090 工作站被 OOM kill**（sim 栈导入 + 共存 Rynn/ROS 服务；团队基线机不同）
  ——本轮以定向子集 + 干净树对照代替全量；勿在本机跑全量，分块跑。
- **例子预算是硬闸**：三个测试钉 ≤N 字符，append-only 纪律下新 few-shot 挤不进——感知轮先写紧凑版仍超
  最终省略；stack_down 轮（2026-07-29）判为必要能力，护栏 6000→6400 容纳而非删既有教学信号。
- **既存环境性失败（勿追）**：viz_3d ×3（本机无 ~/go2w-nuc）+ tests/vcli 少数（playground/go2_perception/
  level66/go2_courtyard）+ unit/vcli 缺 PIL/cv2/mujoco + hardware sim 计时 flake + sim-env collect error。
  裸环境缺 prompt_toolkit/cv2 → 经 `scripts/run-tests`（.venv）跑显示测才有依赖。
- **真机丝滑天花板=导航栈地形**（obstacleHeightThre=0.1m，95% 零长度局部路径）=CEO 门槛；agent 侧只能去掉
  重规划、去不掉障碍处物理停顿。
- **结构债（既存上游单体）**：native_loop/engine/cli/goal_decomposer >800 行硬上限；go2w_real 620+。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042)；go2w_real=真机(ROS_DOMAIN_ID=20,
  ~/Z-Navigation-Stack)。同 CLI，sim↔real 对称；verify 唯真值=/state_estimation(无 /gt)；测仅经
  `scripts/run-tests`。预建图：`~/maps/zeno_office/`（places.json 命名点，start_pose.txt 首行=home）。
  nav.sh/map_color_publisher 在 go2w-nuc 兄弟仓（独立提交）。
- **现场跑 sink 模式**（持久 composer，从不调 render_lines）——UI 改动的可见性必须走 sink 流式路径验证。
- 感知：RynnBrain 服务已收编进仓 `scripts/rynnbrain/`（server.py 跑 ~/envs/rynnbrain venv、systemd --user
  托管，install-service.sh 生成 unit；默认 2B、HTTP:8786=z-agent 契约恒在，ws:8782 老客户端边车 opt-in）；
  桌面 rynnbrain_test 原件不动不删（LIBERO/ab_compare 老客户端仍可 start_rynn.sh 另跑）；z-agent 侧只做
  httpx 客户端+两只读技能，感知永不进 verify。
