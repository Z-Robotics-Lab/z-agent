# Zeno — progress

更新：2026-07-06。fork 自 VectorRobotics/vector-os-nano @ R715 (12f3e15)，分支 main。

## Works（已验证）
- **go2w 相对移动 + strategy↔skill 接缝修复（2026-07-06，aaa25ae）**：REPL 实测两缺口
  （"往前走几米"→unmatched；"navigate is not a skill (valid 含 navigate)" 自相矛盾）。
  根因=半配置 DecomposeVocab 把 strategies=frozenset()（非 None）注入 decomposer 清空
  KNOWN_STRATEGIES+prompt 清单（DEBUG.md H1-H4 全 CONFIRMED，含潜伏 navigate execute
  签名 TypeError）。修：go2w 完整 vocab（4 策略+params help+verify 签名+双示例）、新
  move_relative 技能（pose+yaw 运行时换算 waypoint，与 navigate 共用 _drive_and_hold）、
  decomposer 裸名归一化（X→X_skill，真幻觉仍 fail-loud）、preflight 扩校验 strategies 集
  +零策略 warning。TDD 12 红→14 绿；回归 vcli/harness 子集 410 绿（2 r2b PTY 失败为存量）。
- **verdict sentinel 身份切换（D184，7c61021）**：--json 双发 ZENO_VERDICT（主）+
  VECTOR_VERDICT（legacy 别名）；pty_cli 双前缀兼容。正式移除 legacy = 另一 CEO 门。
- **go2w 体验审计修复（2026-07-06，f4f7f1a/cca2d0b/2c3a862）**：8 findings 处置。#1 路由
  挤掉 go2w 工具→IntentRouter essential_categories 钩子（内核不命名世界）；#2 world_query
  fail-safe；#3-#6 go2w 禁 diag/system 类目（MuJoCo 时代/错误 ROS 域，零误伤；robot 类目
  保留——navigate/explore/pick wrap 在内）。端到端四路由路径实测通过。
- **go2_piper.xml 网格路径修复**：烘焙绝对路径改相对化（相对 go2/assets），双锚等价。
- **F1+F2 合入 main（3ead15b）**：BYO 世界一等公民化（--world/build_embodiment/生命周期
  钩子/go2w 内置）；E2E 锚：`--world go2w -p 导航…` → verdict GROUNDED EXIT 0。
- F0 关门：全套基线 parity 达成 fork 零回归（残余失败均与上游一致：8 环境性 PTY、
  level71 段错误、ik_solver 17 错=pinocchio 本机怪癖+仓库外绝对路径）。
- 环境固化：constraints.txt = 上游 venv 逐版本镜像（207 包）。

## Failed / 教训
- go2 复合指令（"左转90度再前进一米"）：第二腿模型用只读查询冒充行走→actor-causation
  判 RAN（moat 正确拒绝）。producer 教学缺口，非运动学问题。简单行走 2/2 GROUNDED。
- 半配置 DecomposeVocab 是 foot-gun：as_kwargs() 全字段无条件注入，空集≠None 会清掉
  registry 推导；世界要么不注入 vocab（走推导），要么注入完整（接缝测试钉死一致性）。
- 新 venv 装最新二进制→pinocchio 段错误；必须 constraints.txt 镜像 +
  `-e ~/Desktop/go2-convex-mpc --no-deps`。
- .env gitignored 不随 clone——PTY 测试要真 CLI，必须手动复制。
- PTY/sim 测试对宿主负载敏感（Isaac 双容器在跑时稳定失败）——parity 对照比"绝对全绿"诚实。

## 环境镜像清单（冷启动新机器必读）
venv: uv pip install -r constraints.txt + clip@git(577b3cfa…d93eb3be) +
-e ~/Desktop/go2-convex-mpc --no-deps + -e . --no-deps。另从上游工作树同步 gitignored
资产：hardware/sim/mjcf/{go2,g1}/scene_*.xml、assets/、config/{user.yaml,boundary.ply,
workspace_calibration.yaml}、.env、robot_mode.txt。

## CEO 方针（2026-07-06 裁定）
轻量化点到为止：保留 MuJoCo sim 与全部核心代码（脊柱回归夹具与基座）；深度剥离与
包改名（zeno → z_agent/za）推迟到后期架构重构一并做。

## Next
1. go2w 相对移动补实测：真 Isaac 栈起后 REPL 跑 "往前走几米"/复合指令，确认 GROUNDED
   （本轮为离线单测绿，验收面=bare zeno REPL，Invariant 2）。
2. task#12 Zeno 身份修复 workstream（Opus）：VectorEngine 改名、docs/reference.md+VERIFY.md
   VECTOR_* 示例改 ZENO_ 主名；prompt.py:95 ROBOT_TOOL_INSTRUCTIONS 硬编码兄弟仓路径同归。
3. P5.4 真机（等 CEO 三决策：verify 语义 / NUC vs Orin / unitree_sdk2 依赖）。
4. 待 CEO RULING：docs/RULES.md loop 章节悬空指针修剪。
5. 已知存量失败：r2b PTY 2 个（clean HEAD 同红）；test_native_first_covered_go2_routes_
   to_native sim 动力学 flaky（基线同红）。

## 关键背景
- go2W_Sim 仓库 = 数字孪生（Isaac 资产/CMU navstack/桥）；z-agent 经 HTTP 桥
  (127.0.0.1:8042) 控它；桥 API 是 sim/real 对称的合同面。
- TARE 在栈内现成、/explored_volume 是独立探索裁判（四份调研报告见 go2W_Sim 会话档案）。
