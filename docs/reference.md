# Reference — CLI tool system + Skill protocol
Merged from docs/cli-tool-system.md + docs/skill-protocol.md (git history keeps the long forms).

## VectorEngine 概述
<!-- pull: 想知道 vector-cli / MCP 的执行引擎是什么 -->

VectorEngine 是唯一执行引擎，CLI 和 MCP 共用:
`vector-cli / vector-os-mcp → VectorEngine → native tool-use producer (legacy VGG = 回退) → skill.execute()`。
用户说自然语言，agent 通过工具系统控制机器人、编辑代码、诊断问题 —— 一个 session 完成所有事。

## 当前 producer 架构（2026-06 cutover 后 — 权威）
<!-- pull: 哪个 producer 是默认 / 路由怎么走 -->

<!-- doc-drift-gate: default_producer=run_turn_native -->

路由不再靠关键词。**`native_loop.run_turn_native`(模型驱动的 tool-use producer)是默认 producer** ——
模型读工具描述自行路由，无关键词表。旧的 `IntentRouter` 关键词层(`should_use_vgg`/`_RULES`/…)+ 旧的
`vgg_decompose`/`vgg_execute` producer 正在被 strangle,**S8(CEO 闸门)退役**;`native_loop.should_attempt_native`
(注册表驱动,D74)是 `should_use_vgg` 的已验证替代(安全超集)。

**producer-per-path(当前默认):**

| 入口 | 默认 producer | 说明 |
|------|--------------|------|
| 交互 REPL 的动作轮 | `run_turn_native`(native) | 默认 ON via `_repl_native_enabled`;无动作→回退 legacy。`VECTOR_REPL_NATIVE=0` 关 |
| 交互 REPL 的闲聊/tool_use 轮 | `run_turn_unified` | 非-VGG 答复路径(LIVE,cli.py) |
| `-p` / `--print`(机器验收面) | `run_turn_native`(native) | 默认 ON via `_print_native_enabled`(S5b/D73);无动作→回退 legacy。`VECTOR_PRINT_NATIVE=0` 关 |
| `--native-loop` | `run_turn_native`(纯 native,无回退) | 显式 force |
| legacy 回退 / `VECTOR_LEGACY_TURN=1` | `vgg_decompose`+`vgg_execute`(IntentRouter 关键词门) | 被 strangle;S8 删除 |

所有 producer 把同一形状的 `ExecutionTrace` 交给**未改动的诚实验证脊柱**(`VerdictReport.from_trace` /
`evidence_passed`)——producer 永不自算 `verified`。**plug-and-play 5 契约**(Embodiment/Policy/Skill/Capability/Verify)
详见 [docs/ARCHITECTURE.md](ARCHITECTURE.md)。CI 文档漂移闸:`tests/unit/vcli/test_doc_drift_gate.py` 断言上面的
`default_producer` 标记与实际默认(`_repl_native_enabled`/`_print_native_enabled` 默认 ON)一致。

## Legacy paths — IntentRouter · tool_use `run_turn` · VGG decompose/execute · GoalDecomposer
<!-- pull: 遇到遗留回退路径的代码 -->

Ruled dead by D9; git history keeps the description. Still present only as the `VECTOR_LEGACY_TURN=1` /
zero-action fallback, pending S8 removal (CEO gate); 诚实验证脊柱不属于此遗留层。

## CategorizedToolRegistry — 分类工具注册表
<!-- pull: 工具怎么注册/分类/启停 -->

继承 `ToolRegistry`（完全向后兼容）；工具按类别分组，运行时可启停整个类别：

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

native producer 直接下发本世界工具集（关键词按-意图路由属 Legacy paths）。

## Tool Protocol — 工具协议
<!-- pull: 实现一个新工具的接口 -->

Protocol 类型，不需要继承：

```python
class Tool(Protocol):
    name: str                           # 工具名
    description: str                    # LLM 看到的描述
    input_schema: dict[str, Any]        # JSON Schema 参数定义

    def execute(params, context) -> ToolResult
    def check_permissions(params, context) -> PermissionResult
    def is_read_only(params) -> bool
    def is_concurrency_safe(params) -> bool
```

`@tool` 装饰器自动注入 permissions、read_only、concurrency 的默认实现。

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

## 内置工具清单 (19 内置 + 臂控技能)
<!-- pull: 有哪些工具 / 类别 / 权限默认 -->

带 `*` = 写操作，权限默认 ask；其余只读，默认 allow。

| 类别 | 工具 |
|------|------|
| code | file_read, file_write*, file_edit*, bash*, glob, grep |
| general | web_fetch |
| robot | world_query, scene_graph_query（+ 臂控时 10 个技能工具） |
| diag | ros2_topics, ros2_nodes, ros2_log, nav_state, terrain_status |
| sim | start_simulation*, stop_simulation* |
| system | robot_status, skill_reload*, open_foxglove |

臂控 10 技能（接入 arm agent 时动态注册）: home, wave, scan, detect, describe, pick, place,
gripper_open, gripper_close, handover。

## 权限系统 — 8 层检查（优先级从高到低）
<!-- pull: 某工具为什么被拒/放行 -->

1. `tool.check_permissions()` 返回 deny → 拒绝（**内在安全闸门，无条件硬停**：
   bash 黑名单 / 危险路径写入永不被 `--no-permission` 关闭）
2. `no_permission` 标志 → 放行所有非内在拒绝的工具
3. `deny_tools` 用户黑名单 → 拒绝（较软的偏好，`--no-permission` 可覆盖）
4. `tool.check_permissions()` 返回 allow → 放行
5. `session_allow`（用户说了 "always"）→ 放行
6. `is_read_only(params)` → 放行
7. `tool.check_permissions()` 返回 ask → 提示用户确认
8. 默认 → 提示用户确认

电机技能（navigate、walk、pick）→ 始终 ask。只读工具 → 始终 allow。

## ToolHookRegistry — 工具执行钩子
<!-- pull: 工具前后回调（验证/遥测/链式反应） -->

`add_pre_hook`/`add_post_hook` + `fire_pre`/`fire_post`(frozen `ToolHookContext`: tool_name,
params, result, duration)。钩子异常被吞掉，不中断工具执行。

## 动态系统提示（DynamicSystemPrompt + RobotContextProvider）
<!-- pull: LLM 每轮看到的机器人状态从哪来 -->

- `DynamicSystemPrompt` 是 list 子类重写 `__iter__()` —— 每次 API 调用重新遍历，机器人状态每轮最新。
- `RobotContextProvider` 每轮采集：位置/朝向(`base`)、当前房间 + SceneGraph 摘要(`scene_graph`)、
  探索/导航栈状态(`explore`)。
- 优雅降级：无 base → "No hardware connected"；无 SceneGraph → 省略房间数据。

## 非交互验收契约 — `-p / --json / VECTOR_VERDICT`
<!-- pull: 机器验收/退出码/判定字段 -->

契约全文在 **[docs/VERIFY.md](VERIFY.md)**（REAL-VERIFY 唯一 runbook）。开发者视角一句话：
判定由 `vcli/verdict.py` 的 frozen `VerdictReport` 承载，只从诚实脊柱（`evidence_passed`）构建，绝不二次推导。

## vcli/ 文件目录
<!-- pull: 找某个子系统的代码在哪个文件 -->

```
vcli/
├── cli.py                  # 入口、REPL 循环、斜杠命令
├── engine.py               # VectorEngine — 多轮 tool_use agent 循环
├── native_loop.py          # 原生 tool-use producer（run_turn_native，默认路径）
├── verdict.py              # VerdictReport（-p/--json 的 VECTOR_VERDICT 判决依据）
├── tool_execution.py       # 工具执行调度
├── turn_status.py          # 轮次状态
├── intent_router.py        # IntentRouter — 关键词路由（legacy，S8 退役）
├── hooks.py                # ToolHookRegistry
├── prompt.py / dynamic_prompt.py / robot_context.py   # 系统提示（静态+动态+机器人状态）
├── session.py              # JSONL session 持久化（原子写,50 条自动压缩）
├── config.py / oauth.py / permissions.py / eval_runner.py
├── primitives/             # 原子动作原语
├── backends/               # LLMBackend Protocol + 工厂; anthropic.py,
│                           #   openai_compat.py, text_llm_adapter.py, types.py
├── cognitive/              # VGG 认知层 + 诚实验证脊柱
│   ├── vgg_harness.py / goal_decomposer.py / goal_executor.py / goal_verifier.py
│   ├── strategy_selector.py / strategy_stats.py / template_library.py
│   ├── trace_store.py / evidence_classifier.py / actor_causation.py
│   │                       #   诚实判决脊柱（"护城河"，字节不变;verdict.py 在 vcli/ 顶层）
│   ├── vocab_from_registry.py / tool_dispatcher.py / code_executor.py
│   ├── object_goal.py / coord_goal.py / object_memory.py / observation.py
│   ├── abort.py / blackboard.py / predict.py / visual_verifier.py
│   ├── experience_compiler.py / types.py
│   └── capabilities/       # 能力 seam（Capability + CapabilityRegistry + chat/detector）
├── worlds/                 # 世界插件: base.py / dev.py / robot.py / registry.py
│                           #   + arm_sim_/go2_sim_/g1_perception_ oracle 谓词
└── tools/
    ├── base.py             # Tool Protocol, @tool, ToolRegistry, CategorizedToolRegistry
    ├── __init__.py         # discover_all_tools(), discover_categorized_tools()
    ├── file_tools.py / bash_tool.py / search_tools.py / web_tool.py
    ├── robot.py / scene_graph_tool.py / ros2_tools.py / nav_tools.py
    ├── sim_tool.py / sysnav_sim_tool.py
    ├── skill_wrapper.py    # SkillWrapperTool + wrap_skills() + 恢复提示
    ├── reload_tool.py      # skill_reload（热加载）
    └── viz_tool.py         # open_foxglove
```

# SkillFlow — Skill Plug-in Protocol
<!-- pull: bring a skill / 写一个新技能 -->

**Status:** the `@skill` plug-in protocol is LIVE: adding a skill is one class + one decorator — no kernel
or routing-code edits (the North Star "bring a skill" contract). Skills describe themselves; routing is the
model's job (the native producer reads tool descriptions). Legacy alias/`auto_steps`/VGG keyword-routing
sections were ruled dead (D9/D62/D72–D74) — git history keeps them.

## The @skill decorator (the live contract)

```python
from vector_os_nano.core.skill import skill, SkillContext
from vector_os_nano.core.types import SkillResult

@skill(aliases=["grab", "grasp", "抓", "拿", "抓起"])
class PickSkill:
    name = "pick"
    description = "Pick up an object from the workspace"   # what the model reads to route
    parameters = {
        "object_label": {"type": "string", "description": "Object to pick"},
        "mode": {"type": "string", "enum": ["hold", "drop"], "default": "drop"},
    }
    preconditions = ["gripper_empty"]
    postconditions = ["gripper_holding_any"]
    effects = {"gripper_state": "holding"}

    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        ...
        return SkillResult(success=True)
```

Fields: `name` · `description` (routing signal) · `parameters` (JSON-schema) ·
`preconditions` / `postconditions` / `effects` (planner + verify hints) ·
`aliases` (multi-language synonyms carried into the tool description).
`direct` / `auto_steps` still exist on the decorator but no longer drive routing.

## Hardware requirements (arm | base | camera)
<!-- pull: 技能声明/查询硬件 -->

A skill queries hardware at run time through the `SkillContext` registries — `context.arm` / `context.base` /
`context.perception` (dict registries `arms` / `bases` / `perception_sources`, plus `context.has_arm()`).
Exposure is gated by the embodiment's capability profile (`embodiments/capability_profile.py::resolve_capability_profile`):
a skill needing an arm is only offered as a tool when the connected body has one. Missing hardware at
execute time → return `SkillResult(success=False, diagnosis_code=...)` — fail loud, never fake.

## SkillWrapperTool — how a skill becomes an LLM tool
<!-- pull: 技能包装为工具 / 失败恢复提示 -->

Every registered `@skill` is auto-wrapped by `vcli/tools/skill_wrapper.py::SkillWrapperTool`
under the `robot` tool category:
- motor detection: `effects` containing "move"/"navigate"/"arm" ⇒ permission = ask,
  not concurrency-safe;
- post-execution state: motor skills append current position/room to the result;
- recovery hints: on failure, `diagnosis_code` maps to a next-step suggestion for the model:

| diagnosis_code | 提示 |
|---------------|------|
| no_base | 没有连接机器人，用 start_simulation 启动仿真 |
| unknown_room | 房间不存在，用 scene_graph_query 查看可用房间 |
| room_not_explored | 房间未探索，先运行 explore |
| navigation_failed | 导航失败，用 nav_state 检查导航栈状态 |
| no_vlm | VLM 不可用，检查 Ollama 是否运行 |
| camera_failed | 摄像头未连接，用 robot_status 检查硬件 |

A skill may wrap an external VLA/VLM or a classical grasp/nav stack — the runtime routes to it by NL and
grades it like any other step. Register via `agent.register_skill(MySkill())` or drop the file in `vector_os_nano/skills/`.

## Binding a skill's goal class to a verify oracle (D69 — read this before shipping)
<!-- pull: 新技能上线前必读 — 物理动作的 GT oracle -->

A skill (or any actor) must NEVER author its own verify target. The D69 incident: a "grasp"
graded GROUNDED because the model wrote `grabbed.txt` and verified `file_exists(...)` — every
gate fired correctly for the wrong reason (tricky-bugs Case 10).

The rule: **a physical-action goal class requires a ground-truth oracle that is only true if
THAT physical work actually happened** — e.g. a grasp goal must carry a necessary
`holding_object()` conjunct, a place goal `placed_count()`; both read sim/robot state the
actor cannot write. When you add a skill that performs a new class of physical action:
1. add (or reuse) a world-side GT predicate in the world's verify namespace
   (`vcli/worlds/*_oracle.py`) that reads independent ground truth;
2. make it a NECESSARY conjunct for that goal class in the evidence gate — a generic oracle
   (file existence, timer PASS) never suffices for a physical claim;
3. never offer generic dev tools (`file_write`/`bash`) as action tools in a robot world.

Full verdict contract + acceptance runbook: [docs/VERIFY.md](VERIFY.md).

## Design principles

1. Skills describe themselves — description, parameters, pre/postconditions.
2. Adding a skill is one class + one decorator — zero kernel/routing edits.
3. Chinese and English are first-class — aliases and NL routing support both.
4. Success is proven by a GT oracle the skill cannot author — never self-reported.
