# Zeno — progress

更新：2026-07-06。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)，分支 main。

## Works（已验证）
- **verdict sentinel 身份切换（task#12 一环，D184 RULING，2026-07-06）**：--json 机器判决
  改双发 ZENO_VERDICT（主，居首）+ VECTOR_VERDICT（legacy 别名，居末，同一 payload）；
  pty_cli 扫描器双前缀兼容（verify_fetch_cli/visual_e2e 经 run_cli_turn 全覆盖）。外部
  消费者审计：vector_os_nano 零 z-agent 引用；go2w/README:104 + evolvingloop SPEC:112/272
  引用 legacy 串（双发保真）；正式移除 VECTOR_VERDICT = 另一 CEO 门（先改这两处再审计）。
  TDD RED→GREEN 21+27 绿（scripts/run-tests）。7c61021 + D184。
- **go2w 体验审计修复（工具面即插即用清理，2026-07-06）**：审计 8 findings 逐条处置。
  #1(headline) 内核关键词路由把"启动仿真/导航/探索/抓"映射到不含 go2w 类目的类目组，
  route() 过滤后 go2w_bringup/navigate/status 全部被挤出 schema→模型看不到唯一生命周期
  入口（实测：native 取不到动作时 fall through 到 legacy tool_use 路径，route() 仍活跃）。
  修法遵 Invariant 4（内核不命名世界）：IntentRouter 加不透明 essential_categories，
  route() 非 None 结果永远 union；BYO 世界经可选钩子 world.essential_categories() 声明，
  CLI 注入（缺钩子=空集=逐字节不变）；go2w 返回 {"go2w"}。#2 world_query 无条件
  agent._world_model 对无该属性的 go2w embodiment 崩 AttributeError→改 getattr fail-safe
  （通用 BYO 加固）。#3-#6 diag(nav_state/ros2_*/terrain_status 读 MuJoCo 时代路径/宿主域,
  看不到 docker 域42) + system(robot_status 谎报 connected/open_foxglove 错误域/skill_reload
  MuJoCo dev) 整组失真→register_tools 里 disable("diag")+disable("system")（两类目均无
  go2w 自家工具=零误伤；robot 类目【不禁】因 navigate/explore/pick wrap 进 robot）。
  #7/#8 对照/裁定不改（go2w.py 本身干净；docs VECTOR_* 属 task#12 身份 workstream）。
  端到端实测：启动仿真/导航/探索/抓 四路由路径 go2w 工具全部在场、陈旧工具全消、
  world_query 优雅降级。TDD 51 绿 + offline 单测 183 绿 + unified/routing/world-registry
  回归 63 绿。3 提交（f4f7f1a docs / cca2d0b go2w / 2c3a862 routing）。非 spine=非 CEO 门。
- **go2_piper.xml 网格路径修复**：仓库 zeno→z-agent 改名后烘焙的绝对 mesh 路径失效
  （test_scene_builder 2 红）；build_go2_piper 改为序列化后文本相对化（相对 go2/assets
  + meshdir="../go2/assets"，直载/include 双锚等价），加载端经 robot_meshes_dir 吸收
  （g1 同款缝）；test_scene_builder 6/6 + embodiments/sim_tool_env 31/31 绿。
- **F1+F2 合入 main（3ead15b）**：修剪确证死重（-895 行 -14MB，测试夹具全保）；
  BYO 世界一等公民化——world.register_tools 接通、--world/VECTOR_WORLD(_PLUGINS)、
  build_embodiment 正门、setup/health/teardown 生命周期钩子、go2w 内置世界
  （vcli/worlds/go2w.py + 10 单测）。**E2E 锚（零 shim）**：`--world go2w -p 导航…`
  → arrived+held d=0.32 → verdict GROUNDED verified=True EXIT 0。
  集成门：vcli chunk 失败集 ≡ F0 基线（2 个表面新失败=worktree 缺 gitignored
  场景资产，补齐后 31/31——资产清单教训再次验证）。
- F0：完整历史已推 Z-Robotics-Lab/z-agent；loop 机器已剥；新宪法 AGENTS.md 落盘。
- **F0 关门：全套基线 parity 达成，fork 零回归**。tests/vcli 失败集逐项一致（8 个
  环境性 PTY 失败）；tests/unit 拆 4 子块全部 parity OK（唯一 delta
  test_cancel_exploration 双侧复跑均 ~50% 抖动=既有 flaky）；level71 段错误与
  ik_solver 17 错误（pinocchio 4.0 对 package:// 的本机解析怪癖 + 测试引用仓库外
  ~/Desktop/vector_ws 绝对路径）双侧一致。
- 环境固化：constraints.txt = 上游 venv 逐版本镜像（207 包）；venv 重建命令见下。

## Failed / 教训
- 新 venv 装最新版二进制（pin 4.x 最新/coal/numpy 组合）→ pinocchio 段错误；
  必须 `uv pip install -r constraints.txt` 镜像上游版本 + 另装本地包
  `-e ~/Desktop/go2-convex-mpc --no-deps`（PEP610 direct install，不在 PyPI）。
- .env（provider 密钥）gitignored 不随 clone——PTY 测试要真 CLI，必须手动复制。
- PTY/sim 测试对宿主负载敏感（Isaac 双容器在跑时 8 个 PTY 测试稳定失败，
  上游同样失败）——parity 对照是比"绝对全绿"更诚实的门。

## 环境镜像清单（冷启动新机器必读）
venv: uv pip install -r constraints.txt + clip@git(577b3cfa…d93eb3be) +
-e ~/Desktop/go2-convex-mpc --no-deps + -e . --no-deps。另需从上游工作树同步
gitignored 运行资产：hardware/sim/mjcf/{go2,g1}/scene_*.xml、assets/（g1 步态）、
config/{user.yaml,boundary.ply,workspace_calibration.yaml}、.env、robot_mode.txt。

## CEO 方针（2026-07-06 裁定）
轻量化点到为止：**保留原有 MuJoCo sim 与全部核心代码**（它们是脊柱回归测试的
夹具与必要基座），在此基础上叠加新能力；深度剥离与包改名（zeno →
z_agent / za）**推迟到后期架构重构时一并做**。F1 已做的仅是零引用死重
（-895 行 -14MB，全部经依赖审计），无需回退。

## Next
1. （改名推迟，见上方 CEO 方针）
2. ~~P5.1 go2w bringup/status 工具~~ 已完成（go2w.py 内 Go2WBringupTool/Go2WStatusTool）。
3. ~~P5.2 explore 技能 + Δexplored_volume 谓词~~ 已完成（Go2WExploreSkill + explored_volume）。
4. task#12 Zeno 身份修复 workstream（Opus）：VectorEngine 类重命名、docs/reference.md
   + VERIFY.md 的 VECTOR_* 环境变量示例改 ZENO_ 为主名 / VECTOR_ 标 fallback（.env.example
   已正确声明 ZENO_ 优先，文档滞后）；DECISIONS/LESSONS/decisions-index append-only 台账禁改
   （新 RULING 可追加）。~~verdict sentinel 部分~~ 已完成（D184 双发过渡，见 Works）。
5. prompt.py:95 ROBOT_TOOL_INSTRUCTIONS 仍硬编码 'bash ~/Desktop/vector_os_nano/scripts/
   launch_explore.sh' 且指向兄弟仓——dev/robot 基座 persona 陈旧内容（go2w 因有 persona_blocks
   不受影响，但任何无 persona_blocks 的机器人世界会吃到）。归 task#12 身份修复。
6. P5.4 真机（等 CEO 三决策：verify 语义 / NUC vs Orin / unitree_sdk2 依赖）。
7. 待 CEO RULING：docs/RULES.md loop 章节悬空指针修剪（F1 agent 依纪律停在 gate 前）。
8. 已知 flaky（非本轮引入）：test_native_first_covered_go2_routes_to_native 在本机 sim
   走不到 (11,3) 目标点 verify=False（基线同样红，与路由/工具面修复无关，属 sim 动力学）。

## 关键背景
- go2W_Sim 仓库 = 数字孪生（Isaac 资产/CMU navstack/桥）；z-agent 经 HTTP 桥
  (127.0.0.1:8042) 控它；桥 API 是 sim/real 对称的合同面。
- 四份调研报告（zeno 生命周期 / go2w 编排 / TARE+RViz / 真机路径）：
  见 go2W_Sim 会话档案；TARE 在栈内现成、/explored_volume 是独立探索裁判。
