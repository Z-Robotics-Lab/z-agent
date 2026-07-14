# CLI UX 重设计提案（branch: ui/cli-experience）

状态：**P1+P2+P3.1+P3.2+P3.3+P3.4+P3.5+P3.6 已实施**（2026-07-13，基线 ddf2208）。
范围：**只动展示层**（vcli 渲染 + 显示回调接线），不动 verify 脊柱语义
（vcli/cognitive 的判定逻辑零改动，verdict 只读不再算）。

## 0. 实施状态（与提案的偏差，先读这个）

- ✅ P1.4 诚实计时：native StepRecord/trace 填真实 wall-clock；未测量渲染 "—"
  决不打 0.0s（fmt_duration）。
- ✅ P1.3 verdict 卡片：turn_render.render_verdict_card + explain_step 查表。
  **注意**：查表按 5feb14f（谓词角色映射 + grounded observations）后的新语义
  枚举——提案 §1 里"全绿仍 verified=False"的截图场景已被脊柱修复，卡片解释
  的是仍可达的组合（含回合级门槛兜底）。
- ✅ P1.1 事件流：turn_events.NativeEvent + native_loop on_event（additive，
  默认 None 字节等价）；ChainView 单 Live 活树替换 console.status；finish 事件
  携带 usage（native 路径首次读 response.usage）；on_reasoning 首次接进 native。
- ✅ P1.2 CoT：/cot off|tail|full（config 持久化）+ /why；chat 路径开放
  `◌/┆` thinking；native 路径经 reasoning 事件。P3.6 后 tail 回合留两行预览，
  `/why` 展开全量；推理只进显示缓冲，决不进 session。
- ✅ P1.5：**/trace 读会话内有界历史（5 条，native+VGG）而非磁盘**——取证发现
  产品从不调 save_trace，磁盘回放永远为空；/trace save 显式落盘。/route 只判
  路由不执行。
- ✅ P2：native/VGG 保留 route/model/tok/wall 页脚，普通 chat 在 P3.5 压为
  tok/wall（route/model 由 composer 常显）；步骤行符号单义
  ✓=GROUNDED、○=RAN 且检查过、✗=检查假；步骤行带诚实时长。
- ✅ P3.1 执行树持久化（owner ask 2026-07-13）：回合后 ⌂ goal 树（rounds/工具/
  verify/nudge）留在 transcript，活区消失的过程信息不再丢。
- ✅ P3.2 live status 同源上屏：只读现有 `world.live_status_line` hook，
  ChainView 每个 native round 刷新，prompt_toolkit 底栏显示同一行；失败清空
  防旧位姿，Rich/HTML 均转义；未动 native_loop/world/verify。
- ✅ P3.3 独立输入 composer（owner ask 2026-07-13）：裸单行 `PromptSession`
  替换为全宽 `Frame + TextArea`，最多 6 行滚动编辑；Enter 提交（CR/LF 均接受，
  保持 acceptance `sendline`），Alt+Enter 换行，Tab 补全，Ctrl+R 历史；提交后压成
  markup-safe `›` transcript。状态底栏收进输入区，Ctrl+C/EOF/插队契约不变。
- ✅ P3.4 Claude Code 风格收口（owner 截图反馈 2026-07-13）：去掉重复的 `Zeno`
  Frame 标题与四边框，改为短 rail + 开放输入面；启动内置 owner 指定的 6 行、38 列
  双色终端 `ZENO` 字标（亮色块字 + 石墨结构线 + SGR 斜体近似原稿斜切），≥38 列始终
  原样显示，更窄时才完整切换
  compact 版本，不截画。live status 按完整字段
  最多 3 行重排，续行与软换行正文均对齐。针对现代终端先 reflow 后 SIGWINCH 导致的
  重复 prompt，缩窄时按新宽度重算擦除原点，扩宽沿用原生路径；tmux 实测同一长 draft
  `100→40→100` 无残影。启动 metadata 在窄端也按字段折行并保持两格缩进。
- ✅ P3.5 消息层级 + CoT 收口（owner 要求截图审视 2026-07-13）：同一个
  `hello + /cot full` 真实 DeepSeek 回合前后对照。普通回答从带标题全边框收为 `●`
  开放消息，软换行对齐正文；answer-only 回合不再重复打 `answer done` / `VGG [PASS]
  answer`（动作步骤的执行链、verify、verdict 全保留）。普通对话 footer 不再重复
  composer 已常显的 route/model，只留诚实 tokens/time。CoT full 与 `/why` 改为
  `◌ Thinking` + `┆` 左轨的响应式开放块，provider 空白归一后自然换行；实时
  tail 去边框并严格限制为标题 + 单行尾巴。`off|tail|full` 兼容不变，推理仍不进 session。
- ✅ P3.6 实时反馈 + 层级再收口（owner 现场反馈 2026-07-13）：删除底栏无绑定的
  `? 快捷键`；`TurnStatus` 自带 1s UI 心跳，provider 55s 不送 reasoning chunk 时
  `Thinking` 仍逐秒增加，答案开始后立即停止心跳。tail 在 transcript 留标题+两行
  暗色预览，`/why` 是可兑现的全量展开；legacy/native 工具统一为更低对比的
  `◇ Tool · call ✓|×`层。Logo 仅在交互 TTY 以固定六行区域从左向右 0.9s
  浮现；pipe/JSON/测试直接输出最终帧，无延迟。
- ✅ P3.7 常驻 composer（owner ask 2026-07-13）：输入框永不让出终端。TurnRunner
  worker 跑回合、patch_stdout 上方落盘、忙时打字=插队（内核同一队列协议）、^C 忙时
  取消回合、ChainView 流式落盘替代 Live、⚙ 活动串+thinking 心跳进底栏。
  逃生门 VECTOR_COMPOSER_SYNC=1。已知边界：worker 内权限询问 UX 待专项（native
  电机技能自动放行,少触发）；chat 流式文本不再逐字上屏（完稿落盘,心跳在底栏）。
- ✅ P3.8 底栏排版（owner 真机反馈 2026-07-13）：⚙ 活动/⌖ 位姿/身份计数三区
  分色，odom age>3s 整片 amber 警示；执行期常驻+0.5s 自刷新；折行与文本不变。
- ✅ P3.9 降噪+composer 收口（owner 真机取证 2026-07-13 深夜）：流式模式卡片行
  省略（ⓘ 保留）、插队回显 4→2 行、tool_use 时长诚实档、● 答案表格真渲染、
  composer 空态 placeholder+全宽轨线。
- ✅ P3.10（owner 真机反馈）：placeholder 移入上轨线（输入行前不再有常驻文字）；
  ReasoningStreamer 句界流式 ┆ 落盘（chat+native 同款,off 静默,sync 保 P3.6 预览）;
  底栏 '回答中 · N 字'。
- ✅ P3.11 性能（owner: 交互卡）：live-status 200ms TTL 缓存,footer 重绘不再每次
  碰真机驱动读——打字/执行期高频落盘不再卡。
- ⏸ 未做：当前 transcript 是 Rich 静态 scrollback，旧行不再接收鼠标事件；
  真正“点击某个块原地展开”需要持久全屏 TUI 或 GUI，本轮不伪造可点击箭头。
  Ctrl+O 详略切换与 GUI（§6，WebSocket 需 CEO gate）仍待做。

## 7. 下一轮候选（2026-07-13 与 owner 讨论，#1 已落地）

1. ✅ **live_status 上屏（P3.2）**：pose hooks 轮（1499720）已给模型每轮重建 live_status_line
   （位姿/course drift/odom age）——同一数据渲染进 ChainView 头 + prompt_toolkit
   底栏，人和模型看同一份真值（单源，display-only）。
2. **长动作进度**：navigate/route 执行中在树节点上滚动 距目标剩余米数/航向
   （轮询里程计，display-only；world 层已有活位姿接缝）。
3. **/history**：回合级时间线（一行=goal+verdict+耗时），配合 /trace n 下钻。
4. **底栏升级**：model · world · odom age · estop · cot mode · permissions mode。
5. **/export**：上一回合导出 markdown 报告（树+verdict 卡+CoT），现场记录用。
6. **回合后快照提示**：ADR-002 PNG 已拍时打印路径。
7. **Ctrl+O 详略切换**：result_data/verify 原始值常显。
8. **GUI dashboard**：事件协议+trace 已结构化，`zeno --dashboard` WebSocket tail。
   注：WebSocket tail 会形成新跨进程接口，实施前必须过 CEO gate。
- 兼容性：ZENO_VERDICT 哨兵、verdict 行 `(n/m grounded)` 尾、`→ verify`/
  `actor=`/"native working" PTY 钉词、插队行、session 摘要全部原样保留；
  P3.5 历史 UI 簇 183P；P3.6 变更+邻接簇 191P/2skip + 裸 zeno PTY + 真实 DeepSeek
  chat/tool 回合全绿；全量 unit/vcli 1120P/5F（另 2 cv2 collect）、
  tests/vcli 1108P/32F/33skip/1xfail，失败全为环境或 UI worktree 未合入的 hw RED。

## 1. 现状诊断

REPL 有三条 turn 路径，渲染形态完全不同，信息密度都不够：

| 路径 | 何时走 | 执行期间看到什么 | 结束后看到什么 |
|---|---|---|---|
| **native**（动作类默认，cli.py:507-635） | classify_intent.use_vgg 且 native 路由成功 | 一行会消失的 spinner（`native working…`，72 字符 thinking 尾巴滚动） | 每步一行 `▸ 技能 → verify 谓词 ✓ (actor=…)` + 一行 verdict 摘要 |
| **VGG legacy**（cli.py:2928-3020） | LEGACY_TURN=1 或 native 未路由 | 预展示 plan + 异步逐步回调行 | run snapshot（[PASS]/[FAIL]） |
| **tool_use / chat**（cli.py:3022-3096） | 非动作类 | Live 面板流式文本 + 工具行 | 答案面板 + token 统计 |

截图（真机 go2w_hw，deepseek-v4-pro）暴露的具体问题：

1. **没有 CoT**。DeepSeek 的 reasoning_content 已经通过 openai_compat 的
   `on_reasoning` 流出来了，但 cli.py:2769-2772 只拿它维持 "thinking…" 计时，
   内容直接丢弃；native 路径更彻底——`run_turn_native` 的 `on_progress` 是
   `Callable[[str], None]`（native_loop.py:990），reasoning 根本没接线。
2. **没有执行链**。native 是模型驱动的 ReAct（每轮：模型思考 → 挑工具 → verify），
   这条链只在 spinner 里一闪而过，结束后压缩成两行摘要。用户看不到"模型正在
   干第几步、为什么挑这个技能"。
3. **verdict 是黑话**。`verdict RAN verified=False (0/1 grounded)` 和
   `(actor=NOT_GRADED)` 没有任何解释。VerdictReport.per_step 里有每步的
   strategy / verify 表达式 / evidence 分类 / diagnosis（verdict.py:87-104），
   全部没渲染。用户做完动作、机器人明明站起来了，屏幕却说 verified=False，
   还不告诉为什么——这是信任杀手。
4. **计时是假的**。native 路径 StepRecord.duration_sec / total_duration_sec
   硬编码 0.0（native_loop.py:833, 957），截图里满屏 "0.0s"（连答案面板里的
   "延迟 0.0s" 都是它）。显示假数据比不显示更糟。
5. **token 用量只有 tool_use 路径显示**，native / VGG 路径拿到了 usage 却不打。

## 2. 管道里已有、但被丢弃的信息（全量清单）

| 信息 | 在哪 | 现状 |
|---|---|---|
| 模型推理链（CoT） | openai_compat `on_reasoning` 流式 chunk | chat 路径丢弃；native 路径未接线 |
| 每步 evidence 分类 | VerdictReport.per_step[].evidence（GROUNDED/RAN/FAILED） | 只显示聚合计数 |
| 失败诊断 | StepRecord.failure_class + result_data['diagnosis'] | 不显示 |
| actor 因果语义 | ActorCaused 枚举 + 判据（actor_causation.py） | 只打枚举原文，无解释 |
| 步骤结构化输出 | StepRecord.result_data（位姿、对象列表、verify 原始值） | 不显示 |
| oracle 名单 | verify_oracle_names()（哪些谓词算真值） | 不显示 |
| 路由决策 | classify_intent → native/vgg/tool_use | DEBUG 日志 only |
| decompose 反馈 | GoalTree.validation_notes / SubGoal.cleared_strategy（幻觉策略被清除） | 不显示 |
| native 护栏事件 | unverified-action nudge / degenerate-spin（native_loop.py:694-749, 1189-1196） | 不显示 |
| 完整 trace | ~/.zeno/traces/trace-*.json（schema v4，可回放） | 无任何 CLI 入口 |
| token 用量 | TurnResult.usage（含 cache 读写） | 仅 tool_use 路径 |

结论：**这不是"要新造数据"的问题，是渲染层把现成数据扔了**。CLI 远没到
"已经 OK"的程度，优先做 CLI；GUI 见 §6。

## 3. 硬约束（改 UI 前先背下来）

- `ZENO_VERDICT` / `VECTOR_VERDICT` 哨兵行是机器契约（verdict.py:48-49，
  PTY harness / CI 靠它），一个字节不能动。
- 身份文案 "Zeno" 被 test_product_identity_labels / test_agent_panel_identity 钉死。
- UI **只读** VerdictReport / ExecutionTrace / StepRecord，永不自己算 verified
  （verdict.py 模块 docstring 的契约；显示层给解释文案可以，给第二意见不行）。
- 单 Live region 纪律：一个 turn 只能有一个活动 Live，打印外来行必须
  `status.paused()`（turn_status.py 存在的全部理由，DeepSeek 长思考时框会叠帧）。
- reasoning 内容只进显示缓冲，**不进 session**（避免污染上下文与回放）。
- CJK 宽度靠 Rich 的 wcwidth，自绘对齐时禁止按 len() 数宽度。

## 4. 方案

### P1 — 信息密度（先把已有数据画出来）

**P1.1 活的执行链（核心改动）**
把 native 的 `on_progress: str` 升级为结构化事件回调（additive：保留旧参数，
新增 `on_event: Callable[[NativeEvent], None] | None = None`，display-only）：

```
事件类型：round_start / reasoning_chunk / tool_call / tool_result /
          verify_call / verify_result / nudge / finish
```

REPL 用单个 Live region 渲染成一棵活树，节点原地更新：

```
zeno> 往左转动30度

  ⠋ 思考 8s · deepseek-v4-pro
  ┆ 用户要左转30度。turn 技能收 direction+degrees，verify 用
  ┆ turned(18)（60%阈值），单步即可，无需 bringup…        ← CoT 尾巴，dim，可关

  ● turn(direction=left, degrees=30)          执行中 2.1s
  └─ verify turned(18) …

（完成后树定格为：）
  ✓ turn(direction=left, degrees=30)                3.4s
  └─ verify turned(18) ✓ GROUNDED · yaw Δ29.8°（oracle: /state_estimation 里程计）

  verdict GROUNDED verified=True (1/1 grounded)
  route=native · in=8,214 out=612 tok · 14.2s
```

**P1.2 CoT 展示**
- reasoning chunk 流进 Live region 里一个 dim 滚动窗（默认尾部 3 行）；
- `/cot off|tail|full` 三档（默认 tail）；`/why` 打印上一 turn 的完整 reasoning
  （显示层缓冲，session 不存）；
- chat 路径同样接（on_reasoning 现成，改 cli.py:2769 即可）。

**P1.3 verdict 卡片 + 人话解释**
每 turn 结束渲染 per_step 表（数据全部来自 VerdictReport，零重算）：

```
  verdict RAN verified=False (0/1 grounded)
   #  步骤      动作          verify         证据   actor       诊断
   1  standup   BalanceStand  stack_ready ✓  RAN    NOT_GRADED  —
  ⓘ 为什么不是 verified？stack_ready 通过了，但该步证据分类为 RAN：
    谓词与动作角色不匹配（已知脊柱遗留项，见 progress.md"谓词角色映射"）。
```

解释文案是**显示层查表**（evidence×actor 枚举组合 → 一句人话），不碰分类器。

**P1.4 诚实计时 + 全路径 token 页脚**
- native_loop 给 StepRecord.duration_sec / total_duration_sec 填真实 wall-clock
  （字段已存在，填真值不是语义变更）；测不到就**不显示**，禁止打 0.0s。
- 三条路径统一页脚：`route=<native|vgg|tool_use> · model · in/out tok · 总耗时`。

**P1.5 `/trace [n]` 回放**
读 ~/.zeno/traces 最近 n 条，全量展开：goal tree、每步 result_data、verify
原始值、oracle 名单、validation_notes。深信息放这里，默认视图保持克制。

### P2 — 视觉语言（统一三条路径的 turn 块）

每个 turn 一个固定四段结构：**头（goal+route）→ 链（活树）→ verdict 卡 → 页脚**。

- 证据色板全局唯一：GROUNDED=绿 · RAN=黄 · FAILED=红 · NOT_GRADED/未知=dim。
  现在 `✓` 在 native 步骤行里表示 verify_result=True（cli.py:595），但 verdict
  又说没 grounded——同一屏两套语义。改为：`✓`=GROUNDED、`○`=RAN、`✗`=FAILED，
  勾号只留给真正落地的证据。
- 符号：`●` 回答、`✓/○/✗` 证据定格态、`┆` CoT、`ⓘ` 解释、`◇ Tool` 工具。
- 普通答案用 `●` 开放消息，不再用全边框 Panel；宽度仍 min(width, 80)。
- 进度纪律不变：全 turn 单 Live，外来行走 paused()。

### P3 — 交互面

- `/cot`、`/why`、`/trace` 如上；`/route` 显示本 turn 路由决策及原因（classify_intent 结果）。
- 静态 scrollback 不宣称支持原地鼠标展开；compact 预览用 `/why`/`/trace`
  进入完整视图。鼠标折叠依赖全屏持久 TUI 或 GUI 消费同一事件流。
- 输入面为独立全宽 composer：标题/多行编辑/补全菜单/历史搜索/动态状态底栏
  共一个 prompt_toolkit Application；提交后清掉编辑 chrome，scrollback 只留 `›` 用户消息。
- Ctrl+O 循环 compact/verbose（verbose 常显 result_data 与 verify 原始值）。
- `-p/--json` 路径**零变化**（机器面不动）。

## 5. 落地顺序（每步独立可验收，TDD）

1. P1.4 诚实计时（最小、独立、先还债）→ 单测钉"duration>0 或不显示"。
2. P1.3 verdict 卡片 + 解释查表（纯显示，输入是现成 VerdictReport）。
3. P1.1 native 结构化事件 + 活树（最大块；on_event additive，旧 on_progress 保留）。
4. P1.2 CoT（chat 路径先行一行改，native 随 P1.1 事件流）。
5. P1.5 /trace、P3 命令、P2 统一收口。

测试策略：渲染函数纯化（输入 dataclass → 输出 Rich renderable/字符串），
snapshot 断言用 plain-text 捕获；PTY 集成测试只加断言不改哨兵；
`bash scripts/run-tests` 全程（内存封顶，勿裸 pytest）。

## 6. GUI 展望（CLI 之后，不是替代）

trace JSONL（~/.zeno/traces）+ session JSONL（~/.zeno/sessions）已经构成完整
可回放事件源，GUI 只是另一个读者：

- **第一步（零后端）**：`zeno --dashboard` 起本地静态页 + WebSocket tail trace
  目录，时间轴视图 = turn 块的网页版（链树可折叠、CoT 可展开、verdict 卡片）。
- **机器人遥测不重造**：repo 已有 foxglove/ 面板（ROS 话题、位姿、点云），
  认知层时间轴做成独立面板与 Foxglove 并排，而不是往 Foxglove 里塞 LLM 文本。
- **中间形态**：若要富终端而非浏览器，Textual（TUI）可复用同一套事件流；
  但事件协议（P1.1 的 NativeEvent）先落地，UI 形态才可插拔——这也是为什么
  P1.1 是本分支最重要的一步。
