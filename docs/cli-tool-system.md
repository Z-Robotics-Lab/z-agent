# VectorEngine — 统一执行引擎

## 概述

VectorEngine 是 Vector OS Nano 的唯一执行引擎。v2.0 起，CLI 和 MCP 共用同一引擎：

```
vector-cli  ─┐
             ├→ VectorEngine → VGG / tool_use → skill.execute()
vector-os-mcp┘
```

用户说自然语言，AI agent 通过工具系统同时控制机器人、编辑代码、诊断问题 —— 一个 session 里完成所有事。

```
用户: "探索的时候狗在转角撞墙"
  ↓
AI Agent (VectorEngine)
  ├── file_read("go2_vnav_bridge.py")     → 读路径跟随代码
  ├── file_edit(old="0.6", new="0.4")     → 改转弯速度
  ├── skill_reload("walk")                → 热加载，不用重启
  ├── explore()                           → 重新跑探索
  └── 回复: "改了转弯速度，重新探索中"
```

## 当前 producer 架构（2026-06 cutover 后 — 权威；本节覆盖下方任何冲突的旧叙事）

<!-- doc-drift-gate: default_producer=run_turn_native -->

路由不再靠关键词。**`native_loop.run_turn_native`(模型驱动的 tool-use producer)是默认 producer** ——
模型读工具描述自行路由，无关键词表。旧的 `IntentRouter` 关键词层(`should_use_vgg`/`_RULES`/…)+ 旧的
`vgg_decompose`/`vgg_execute` producer 正在被 strangle,**S8(CEO 闸门)退役**;`native_loop.should_attempt_native`
(注册表驱动,D74)是 `should_use_vgg` 的已验证替代(安全超集)。本节是权威;下方"系统架构""Tool Call 完整流程"
"IntentRouter""VGG 层"等描述的是**遗留 tool_use / 回退路径**,保留作参考。

**producer-per-path(当前默认):**

| 入口 | 默认 producer | 说明 |
|------|--------------|------|
| 交互 REPL 的动作轮 | `run_turn_native`(native) | 默认 ON via `_repl_native_enabled`;无动作→回退 legacy。`VECTOR_REPL_NATIVE=0` 关 |
| 交互 REPL 的闲聊/tool_use 轮 | `run_turn_unified` | 非-VGG 答复路径(LIVE,cli.py:2601) |
| `-p` / `--print`(机器验收面) | `run_turn_native`(native) | 默认 ON via `_print_native_enabled`(S5b/D73);无动作→回退 legacy。`VECTOR_PRINT_NATIVE=0` 关 |
| `--native-loop` | `run_turn_native`(纯 native,无回退) | 显式 force |
| legacy 回退 / `VECTOR_LEGACY_TURN=1` | `vgg_decompose`+`vgg_execute`(IntentRouter 关键词门) | 被 strangle;S8 删除 |

所有 producer 把同一形状的 `ExecutionTrace` 交给**未改动的诚实验证脊柱**(`VerdictReport.from_trace` /
`evidence_passed`)——producer 永不自算 `verified`。**plug-and-play 5 契约**(Embodiment/Policy/Skill/Capability/Verify)
详见 [docs/ARCHITECTURE.md](ARCHITECTURE.md)。CI 文档漂移闸:`tests/unit/vcli/test_doc_drift_gate.py` 断言上面的
`default_producer` 标记与实际默认(`_repl_native_enabled`/`_print_native_enabled` 默认 ON)一致,文档与代码不可再背离。

## 系统架构（LEGACY tool_use / 回退路径 — 默认路径见上方"当前 producer 架构"）

```
┌─────────────────────────────────────────────────────────────────┐
│  vector-cli (vcli/cli.py)                                       │
│                                                                 │
│  用户输入 ──→ IntentRouter (意图分类)                             │
│                  │                                              │
│                  ↓                                              │
│              VectorEngine.run_turn()                             │
│                  │                                              │
│                  ├── DynamicSystemPrompt                         │
│                  │     ├── 角色设定 (缓存)                        │
│                  │     ├── 工具使用说明 (缓存)                     │
│                  │     ├── 硬件/技能/世界模型 (静态)               │
│                  │     └── [机器人状态] (每次刷新)                  │
│                  │           位置、房间、SceneGraph、              │
│                  │           导航状态、探索进度                     │
│                  │                                              │
│                  ├── CategorizedToolRegistry                     │
│                  │     ├── code:    文件读写编辑、bash、搜索        │
│                  │     ├── general: web_fetch                     │
│                  │     ├── robot:   场景图/世界查询 (+臂控技能)     │
│                  │     ├── diag:    ROS2话题/节点/日志、导航/地形   │
│                  │     ├── sim:     start/stop_simulation         │
│                  │     └── system:  状态、热加载、foxglove         │
│                  │                                              │
│                  ├── ToolHookRegistry                            │
│                  │     ├── pre_hook: 执行前回调                   │
│                  │     └── post_hook: 执行后回调(验证/统计)         │
│                  │                                              │
│                  ├── LLM 后端 (Anthropic / OpenRouter / 本地)     │
│                  ├── 权限系统 (8层检查)                            │
│                  └── Session (JSONL 持久化)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Tool Call 完整流程（LEGACY tool_use 路径 — native producer 见"当前 producer 架构")

```
1. 用户输入自然语言
2. IntentRouter 关键词分类 → 选择相关工具类别
   "去厨房" → robot+diag (省 68% token)
   "改代码" → code+system (省 72% token)
   "你好"   → 全部工具 (无法判断意图)
3. VectorEngine 序列化:
   - system_prompt (DynamicSystemPrompt 刷新机器人状态)
   - messages (对话历史)
   - tools (只发选中类别的工具 schema)
4. LLM 返回 tool_use 调用
5. 引擎分区执行:
   - 只读 + 并发安全 → 并行 (ThreadPoolExecutor, 10 workers)
   - 写入 / 电机控制 → 串行
6. 每个工具执行:
   a. pre_hook 触发 (日志/预检)
   b. 权限检查 → allow / deny / ask(用户确认)
   c. tool.execute(params, context) → ToolResult
   d. post_hook 触发 (验证/统计)
   e. 电机技能 → 自动附加执行后状态(位置/房间)
7. 结果追加到 session
8. 循环回步骤 3，直到 LLM 返回 end_turn
9. 最终文本渲染到 CLI 面板
```

## CategorizedToolRegistry — 分类工具注册表

### 设计思路

继承自 `ToolRegistry`（完全向后兼容）。核心能力：
- 工具按类别分组管理
- 运行时动态启用/禁用整个类别
- 配合 IntentRouter 按意图只发送相关工具

```python
class CategorizedToolRegistry(ToolRegistry):
    _categories: dict[str, list[str]]   # 类别 → [工具名列表]
    _disabled: set[str]                 # 已禁用的类别

    def register(self, tool, category="default") -> None
    def enable_category(self, category: str) -> None
    def disable_category(self, category: str) -> None
    def to_anthropic_schemas(categories=None) -> list[dict]  # 可按类别过滤
    def list_categories(self) -> dict[str, list[str]]
```

### 工具类别

| 类别 | 工具 | 用途 |
|------|------|------|
| `code` | file_read, file_write, file_edit, bash, glob, grep | 代码读写编辑 |
| `general` | web_fetch | 网页抓取 |
| `robot` | world_query, scene_graph_query（+ 臂控时 10 个技能工具） | 空间查询 + 机械臂控制 |
| `diag` | ros2_topics, ros2_nodes, ros2_log, nav_state, terrain_status | ROS2 诊断 |
| `sim` | start_simulation, stop_simulation | 仿真管理 |
| `system` | robot_status, skill_reload, open_foxglove | 系统状态与热加载 |

### 扩展策略

| 阶段 | 策略 | 效果 |
|------|------|------|
| v1（当前） | 全部启用，IntentRouter 按意图路由 | 平均省 52% token |
| v1.1 | 延迟 schema — 先发名字，LLM 需要时再请求完整定义 | 再省 60% |
| v2 | 外部插件 — pyproject.toml entry_points 注册第三方工具 | 无限扩展 |

### 添加新工具（开发者工作流）

```python
# 1. 新建文件: vcli/tools/my_tool.py
@tool(name="my_tool", description="...", read_only=True, permission="allow")
class MyTool:
    input_schema = { "type": "object", "properties": { ... } }
    def execute(self, params, context) -> ToolResult: ...

# 2. 在 vcli/tools/__init__.py 中:
#    - discover_all_tools() 里加 import + 实例化
#    - _TOOL_CATEGORIES["my_category"] 里加工具名

# 完成。不需要改引擎、后端、权限、或任何其他文件。
```

## IntentRouter — 意图路由器（LEGACY — 被 strangle,S8 退役;替代见 `should_attempt_native` D74)

> 旧的零成本关键词层。仍存在于 legacy/回退路径,但不再是默认路由;模型驱动的 native producer 取而代之。

零成本关键词匹配，在 LLM 调用前选择相关工具类别：

```python
class IntentRouter:
    def route(self, user_message: str) -> list[str] | None:
        # 返回类别列表，或 None（发全部工具）

# 规则示例:
# "改"/"edit"/"code"/"bug"  → ["code", "system"]
# "去"/"走"/"explore"       → ["robot", "diag"]
# "topic"/"log"/"为什么"    → ["diag", "system"]
# "你好" (无关键词匹配)     → None → 全部工具
```

Token 节省效果：

| 场景 | 改前 (19 内置工具全发) | 改后 (路由) | 节省 |
|------|----------------------|------------|------|
| "我在哪" | ~2500 tokens | ~800 tokens | 68% |
| "改速度" | ~2500 tokens | ~700 tokens | 72% |
| "你好" | ~2500 tokens | ~2500 tokens | 0% |
| 平均 | ~2500 tokens | ~1200 tokens | ~52% |

## Tool Protocol — 工具协议

每个工具实现这个接口（Protocol 类型，不需要继承）：

```python
class Tool(Protocol):
    name: str                           # 工具名
    description: str                    # LLM 看到的描述
    input_schema: dict[str, Any]        # JSON Schema 参数定义

    def execute(params, context) -> ToolResult          # 执行
    def check_permissions(params, context) -> PermissionResult  # 权限检查
    def is_read_only(params) -> bool                    # 只读？
    def is_concurrency_safe(params) -> bool             # 可并发？
```

`@tool` 装饰器自动注入 permissions、read_only、concurrency 的默认实现。

## SkillWrapperTool — 技能包装器

Robot skill（`@skill` 装饰器）自动包装为 LLM tool：

```
@skill(aliases=["stand", "站"]) class StandSkill  →  SkillWrapperTool("stand")
@skill(aliases=["navigate"])    class NavigateSkill →  SkillWrapperTool("navigate")
```

包装器增加的能力：
- **电机检测**: effects 中包含 "move"/"navigate"/"arm" → 需要用户授权
- **执行后状态**: 电机技能执行后，自动附加当前位置/房间到结果
- **恢复提示**: 失败时根据 diagnosis_code 给出下一步建议

```
成功: "Skill 'navigate' succeeded. Data: {room: kitchen}
       State: pos=(16.8, 2.3) room=kitchen"

失败: "Skill 'navigate' failed. (room_not_explored)
       Suggested: Room not explored yet. Run the explore skill first.
       Current state: {position: [10.0, 5.0], room: hallway}"
```

已知的恢复提示映射：

| diagnosis_code | 提示 |
|---------------|------|
| no_base | 没有连接机器人，用 start_simulation 启动仿真 |
| unknown_room | 房间不存在，用 scene_graph_query 查看可用房间 |
| room_not_explored | 房间未探索，先运行 explore |
| navigation_failed | 导航失败，用 nav_state 检查导航栈状态 |
| no_vlm | VLM 不可用，检查 Ollama 是否运行 |
| camera_failed | 摄像头未连接，用 robot_status 检查硬件 |

## 复杂 NL 任务的分解路径 — cognitive/ VGG 层

单工具调用（"pick the cup"）由 VectorEngine 的 agent 循环直接处理。**多步复杂任务**的自然语言分解由 `vcli/cognitive/` 负责：

```
vcli/cognitive/
├── vgg_harness.py        # VGG 主循环入口
├── goal_decomposer.py    # 将 NL 目标拆解为子步骤计划
├── goal_executor.py      # 逐步执行计划，调用 VectorEngine
├── goal_verifier.py      # 验证每步结果是否达标
├── strategy_selector.py  # 根据硬件/世界状态选择执行策略
├── capabilities/         # 能力映射（什么机器人能做什么）
└── worlds/               # 世界模型适配（sim / real / ros2）
```

该层实现 **decompose → plan → execute → verify** 循环。**注意(cutover 后)**:这是 LEGACY 的 producer 路径,
正在被 strangle(S8 退役);默认路径现在是 `native_loop.run_turn_native`(模型驱动,见"当前 producer 架构")。
`goal_verifier` / 诚实验证脊柱不属于此层、未改动,仍是所有 producer 的共用验收面。详见 [docs/ARCHITECTURE.md](ARCHITECTURE.md)。

## 非交互验收契约 — `-p / --json / VECTOR_VERDICT` (R2a acceptance instrument)

`cli.main` 既是 REPL，也是**机器可验收的验收面**。这是本项目 #1 历史失败（能力靠 `~/sandbox` 脚本"验证"、绕过产品；347 个测试只有 2 个碰 `cli.main`）的根治：引擎本就计算的诚实判定
`evidence_passed(trace, verify_oracle_names(agent, engine))` 现在能作为机器信号逃出 `cli.main`。

```
python -m vector_os_nano.vcli.cli -p "<prompt>" --json
```

- **`-p / --print TEXT`** — 跑 **一个** turn（不进 REPL）后退出。
- **`--json`** — 在 stdout 打印**恰好一行** `VECTOR_VERDICT {<json>}`（固定 sentinel）；所有 Rich/banner 改走 **stderr**。
- 该 turn 经 `engine.vgg_execute` **同步**执行（绝不 `vgg_execute_async` — 异步会在未完成的 trace 上抢先出判定）。
- 判定由 frozen `VerdictReport`（`vcli/verdict.py`）承载，**只**从既有 `classify_step_evidence` / `evidence_passed` 构建，**绝不**二次推导（契约：`VerdictReport.from_trace(trace, oracle).verified == evidence_passed(trace, oracle)`）。

`VECTOR_VERDICT` JSON 字段：

| 字段 | 含义 |
|------|------|
| `verified` | bool — `evidence_passed` 的结果（验收唯一真值；`verified == (exit==0)`） |
| `success` | bool — trace 是否成功（步骤都成功，未必有 grounded 证据） |
| `evidence` | `GROUNDED` \| `RAN` \| `FAILED` \| `NO_TRACE`（顶层证据等级） |
| `goal` | 本 turn 的 goal（来自 GoalTree） |
| `n_steps` / `n_grounded` | 步数 / 其中 GROUNDED 的步数 |
| `oracle_names` | 本世界 live verify 命名空间的可调用名（与 GoalVerifier 同源） |
| `per_step` | 每步 `{name, strategy, success, verify, verify_result, evidence}` |
| `error` | 仅 NO_TRACE/错误时填写 |

**退出码契约：** `0` = verified（GROUNDED）·`2` = ran-not-verified（RAN/FAILED）·`1` = error / NO_TRACE（chat/tool_use turn 无确定性 trace → fail-closed）。

**测试驱动（确定性、无网络）：** `VECTOR_FAKE_LLM=<json-path>` 环境变量在**单一** `create_backend` 接缝
(`create_backend_with_fake_seam`) 注入 `tests/harness/fake_backend.py::FakeBackend`，返回一份固定的 decompose 计划。
它**只**替换网络 LLM —— 真实的 decomposer / validator / skill / GoalVerifier / 证据门 / 判定**全部照跑**，所以
`verify='True'` 的假计划仍判 RAN → verified False（接缝绝不绕过任何 verify/permission 层）。未设该变量时，
`create_backend` 行为与生产完全一致。

**PTY 验收 + CI 门：** `tests/harness/pty_cli.py::run_cli_turn` 用 **stdlib `pty`**（不引入 pexpect 依赖）拉起真入口、
读 `VECTOR_VERDICT`、断言 `verified == (exit==0)`。CI 门：`cli_main` + `capability` 两个 pytest marker 已注册
(`pyproject.toml`)；`tests/conftest.py` 的 `pytest_collection_modifyitems` 会**判失败**任何带 `@capability` 却缺
`@cli_main` 的测试（杜绝回退到绕过脚本）。

## ToolHookRegistry — 工具执行钩子

在每个工具执行前后触发回调，用于：
- 自动验证（电机技能后检查位置变化）
- 统计遥测（记录工具调用频率/耗时）
- 链式反应（文件编辑后自动格式化）

```python
class ToolHookRegistry:
    def add_pre_hook(self, hook: Callable) -> None    # 执行前
    def add_post_hook(self, hook: Callable) -> None   # 执行后
    def fire_pre(self, ctx: ToolHookContext) -> None
    def fire_post(self, ctx: ToolHookContext) -> None

@dataclass(frozen=True)
class ToolHookContext:
    tool_name: str
    params: dict
    result: ToolResult | None   # pre-hook 时为 None
    duration: float             # pre-hook 时为 0.0
```

钩子异常被吞掉，不会中断工具执行。

## DynamicSystemPrompt — 动态系统提示

**问题**: System prompt 启动时构建一次，之后机器人状态就过期了。

**解决**: `DynamicSystemPrompt` 是 list 的子类，重写 `__iter__()`。VectorEngine 每次 API 调用都会遍历 system prompt，所以机器人状态每轮都是最新的。

LLM 每次对话都看到：
```
[Robot State]
Position: (10.2, 5.3, 0.28) — hallway
Heading: 23 deg (NNE)
SceneGraph: 8 rooms (6 visited), 7 doors, 12 objects
Exploring: no
Nav stack: running
```

## RobotContextProvider — 机器人状态采集

从多个来源实时采集状态：

| 字段 | 数据源 | 更新频率 |
|------|--------|---------|
| 位置 (x, y, z) | `base.get_position()` | 每轮对话 |
| 朝向 (度数 + 方位) | `base.get_heading()` | 每轮对话 |
| 当前房间 | `scene_graph.nearest_room()` | 每轮对话 |
| SceneGraph 摘要 | `scene_graph.stats()` + `get_room_summary()` | 每轮对话 |
| 是否在探索 | `explore.is_exploring()` | 每轮对话 |
| 导航栈运行中？ | `explore.is_nav_stack_running()` | 每轮对话 |

优雅降级：没有 base → "No hardware connected"。没有 SceneGraph → 省略房间数据。

## 权限系统

8 层检查（优先级从高到低）：

1. `tool.check_permissions()` 返回 deny → 拒绝（**内在安全闸门，无条件硬停**：
   bash 黑名单 / 危险路径写入永不被 `--no-permission` 关闭）
2. `no_permission` 标志 → 放行所有非内在拒绝的工具
3. `deny_tools` 用户黑名单 → 拒绝（较软的偏好，`--no-permission` 可覆盖）
4. `tool.check_permissions()` 返回 allow → 放行
5. `session_allow`（用户说了 "always"）→ 放行
6. `is_read_only(params)` → 放行
7. `tool.check_permissions()` 返回 ask → 提示用户确认
8. 默认 → 提示用户确认

电机技能（navigate、walk、pick）→ 始终 ask。
只读工具（file_read、grep、ros2_topics）→ 始终 allow。

## 完整工具清单 (19 内置 + 臂控技能)

### 内置工具

| 工具 | 类别 | 只读 | 权限 | 说明 |
|------|------|------|------|------|
| file_read | code | 是 | allow | 读取文件（带行号） |
| file_write | code | 否 | ask | 创建/覆盖文件 |
| file_edit | code | 否 | ask | 搜索替换 |
| bash | code | 否 | ask | 执行 shell 命令 |
| glob | code | 是 | allow | 按模式查找文件 |
| grep | code | 是 | allow | 搜索文件内容 |
| web_fetch | general | 是 | allow | 抓取 URL |
| world_query | robot | 是 | allow | 查询世界模型对象 |
| scene_graph_query | robot | 是 | allow | 查询房间/门/物体/路径 |
| ros2_topics | diag | 是 | allow | 列出/hz/echo ROS2 话题 |
| ros2_nodes | diag | 是 | allow | 列出/info ROS2 节点 |
| ros2_log | diag | 是 | allow | 读取机器人日志 |
| nav_state | diag | 是 | allow | 导航/探索状态 |
| terrain_status | diag | 是 | allow | 地形地图文件信息 |
| start_simulation | sim | 否 | ask | 启动 MuJoCo 仿真 |
| stop_simulation | sim | 否 | ask | 停止 MuJoCo 仿真 |
| robot_status | system | 是 | allow | 硬件连接状态 |
| skill_reload | system | 否 | ask | 热加载技能模块 |
| open_foxglove | system | 是 | allow | 打开 Foxglove 可视化 |

### 机械臂技能工具（接入臂控 agent 时动态注册，robot 类别，10 个）

连接 SO-101 arm agent（`vector-cli --sim` 或实体臂）时，以下技能自动包装为 robot 类别工具：

home, wave, scan, detect, describe, pick, place, gripper_open, gripper_close, handover

## Session 持久化

JSONL 格式，原子写入 + fsync：
```
{"type":"user","content":"去厨房","ts":"..."}
{"type":"assistant","text":"","tool_use":[{"name":"navigate","input":{"room":"kitchen"}}],"ts":"..."}
{"type":"tool_result","results":[{"content":"Skill 'navigate' succeeded..."}],"ts":"..."}
{"type":"assistant","text":"到了厨房，你要我看看有什么吗？","ts":"..."}
```

50 条记录自动压缩，防止上下文溢出。

## 探索事件流

探索期间，房间发现事件实时显示在 CLI：

```
vector> explore
  start_simulation(sim_type="go2") ... ok 2.1s
  explore() ... ok
  Entered hallway (1/8)
  Entered kitchen (2/8)
  Entered dining_room (3/8)
  ...
  Exploration finished — 8 rooms
```

由 `explore.py` 的 `set_event_callback()` 驱动，在 `vcli/cli.py` 启动时接入。

## 文件目录

```
vcli/
├── cli.py                  # 入口、REPL 循环、斜杠命令
├── engine.py               # VectorEngine — 多轮 tool_use agent 循环
├── intent_router.py        # IntentRouter — 意图路由（关键词 → 类别）
├── hooks.py                # ToolHookRegistry — 工具执行钩子
├── prompt.py               # 系统提示构建器（静态 + 动态块）
├── robot_context.py        # RobotContextProvider（实时机器人状态）
├── dynamic_prompt.py       # DynamicSystemPrompt（每轮自动刷新）
├── session.py              # JSONL session 持久化
├── config.py               # ~/.vector/config.yaml 加载器
├── permissions.py          # 7层权限检查器
├── backends/
│   ├── __init__.py         # LLMBackend Protocol + create_backend 工厂
│   ├── anthropic.py        # Anthropic Messages API（流式）
│   └── openai_compat.py    # OpenRouter / Ollama / vLLM
├── cognitive/               # VGG 认知层 + 诚实验证脊柱（~22 模块）
│   ├── vgg_harness.py        # VGG 主循环（复杂 NL 任务分解入口）
│   ├── goal_decomposer.py    # NL → 子步骤计划
│   ├── goal_executor.py      # 执行计划（skill/primitive/code/tool/capability 派发）
│   ├── goal_verifier.py      # 验证步骤结果（AST 沙箱谓词）
│   ├── strategy_selector.py  # 策略选择
│   ├── trace_store.py / evidence_classifier.py / verdict.py / actor_causation.py
│   │                         #   诚实判决脊柱（"护城河"，字节不变）
│   ├── vocab_from_registry.py # 从注册表单源 decompose 词表
│   └── capabilities/         # 能力 seam（Capability + CapabilityRegistry + chat/detector）
├── worlds/                  # 世界插件（在 vcli/ 下，不在 cognitive/ 下）：
│   │                        #   dev / robot / registry + arm_/go2_/g1_ sim-oracle 谓词
├── native_loop.py           # 原生 tool-use producer（run_turn_native，bare CLI 默认路径）
├── verdict.py               # VerdictReport（-p/--json 的 VECTOR_VERDICT 判决依据）
└── tools/
    ├── base.py             # Tool Protocol, @tool 装饰器,
    │                       # ToolRegistry, CategorizedToolRegistry
    ├── __init__.py         # discover_all_tools(), discover_categorized_tools()
    ├── file_tools.py       # file_read, file_write, file_edit
    ├── bash_tool.py        # bash
    ├── search_tools.py     # glob, grep
    ├── robot.py            # world_query, robot_status
    ├── sim_tool.py         # start_simulation, stop_simulation
    ├── web_tool.py         # web_fetch
    ├── skill_wrapper.py    # SkillWrapperTool + wrap_skills() + 恢复提示
    ├── scene_graph_tool.py # scene_graph_query（7种查询）
    ├── ros2_tools.py       # ros2_topics, ros2_nodes, ros2_log
    ├── nav_tools.py        # nav_state, terrain_status
    ├── reload_tool.py      # skill_reload（热加载）
    └── viz_tool.py         # open_foxglove（原 foxglove_tool.py）
```
