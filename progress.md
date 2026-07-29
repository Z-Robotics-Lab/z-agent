# Zeno — progress

更新：2026-07-22（整合）。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-manip** =
hw-go2w-real（导航/CLI-UI，NUC 侧 45d0b90 回灌）+ hw-go2w-real-vision（RynnBrain 视觉感知，操作前置）合并。
不动 main。叙事在 commit message 里；本文件只留当前状态。两条工作线的 Works 并列保留（导航/UI 在下半，感知在上半）。

## Works（已验证 / 单测 GREEN）
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
  (由 Inv-1 兜底不作验收证据，待加拒识)。测：相机单测重写为按需契约 27 绿 + 感知 21 绿。
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
