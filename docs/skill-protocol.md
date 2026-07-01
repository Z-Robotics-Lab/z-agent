# SkillFlow — Skill Plug-in Protocol (+ legacy alias routing)

**Version:** 1.0
**Status:** the `@skill` PLUG-IN protocol (declare a skill = one class + one decorator, no kernel edit) is LIVE. The alias / `auto_steps` / VGG-GoalDecomposer **keyword routing** it originally shipped with is **LEGACY — being strangled at S8 (pending CEO approval)**; the model-driven native producer routes now (see docs/cli-tool-system.md "当前 producer 架构" + docs/DECISIONS.md D62/D72–D74). Sections tagged **[LEGACY routing]** below describe that fallback path, kept for reference — NOT removed until S8 lands.

## Overview

SkillFlow is Vector OS Nano's skill plug-in protocol: a `@skill` decorator declares how each skill is discovered, its params, and its pre/postconditions, so **adding a skill is one class + one decorator — no kernel or routing-code edits** (the North Star "bring a skill" contract). It originally also did all command routing by keyword-matching skill `aliases`; that routing layer is now legacy (see the status note above).

The core principle: **skills describe themselves.** (Routing is now the model's job, not alias matching.)

## How It Works [LEGACY routing]

> Alias-match → `auto_steps` expansion (zero-LLM). Retiring at S8 (pending CEO approval); the model now routes by reading tool descriptions.

```
User Input: "抓杯子"
      |
      v
SkillRegistry.match("抓杯子")
      |
      +-- Check all @skill aliases
      |   "抓" matches PickSkill (alias)
      |   extracted_arg = "杯子"
      |
      +-- PickSkill.direct = False
      |   PickSkill.auto_steps = ["scan", "detect", "pick"]
      |
      +-- Is this complex? (destinations, multi-object?)
      |   No → execute auto_steps directly
      |
      v
Execute: scan → detect(杯子) → pick(杯子)
      |
      v
Done. Zero LLM calls.
```

## The @skill Decorator

> **LIVE plug-in protocol.** The decorator + its fields (`parameters`, `preconditions`, `postconditions`, `effects`) are how a skill declares itself and registers with zero kernel edits — this stays. Only the use of `aliases` / `auto_steps` as *routing triggers* is legacy (S8); the fields themselves still describe the skill.

```python
from vector_os_nano.core.skill import skill, SkillContext
from vector_os_nano.core.types import SkillResult

@skill(
    aliases=["grab", "grasp", "抓", "拿", "抓起"],
    direct=False,
    auto_steps=["scan", "detect", "pick"],
)
class PickSkill:
    name = "pick"
    description = "Pick up an object from the workspace"
    parameters = {
        "object_label": {"type": "string", "description": "Object to pick"},
        "mode": {"type": "string", "enum": ["hold", "drop"], "default": "drop"},
    }
    preconditions = ["gripper_empty"]
    postconditions = ["gripper_holding_any"]
    effects = {"gripper_state": "holding"}

    def execute(self, params: dict, context: SkillContext) -> SkillResult:
        # ... implementation ...
        return SkillResult(success=True)
```

### Decorator Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| aliases | list[str] | Words/phrases that trigger this skill (multi-language) |
| direct | bool | If True, execute immediately without any LLM call |
| auto_steps | list[str] | Default skill chain for common patterns |

## Routing Logic [LEGACY routing]

> The keyword cascade below (`registry.match` → direct / auto_steps / LLM) is the legacy `IntentRouter`-era path, being strangled at S8 (pending CEO approval). The native producer replaces it — the model reads tool descriptions and routes itself.

```
User Input
  |
  v
registry.match(input)     # Check @skill aliases
  |
  +-- Match + direct=True  → Execute immediately (zero LLM)
  |   Example: "home", "close", "open", "scan"
  |
  +-- Match + auto_steps   → Expand to skill chain (zero LLM)
  |   Example: "抓杯子" → scan → detect → pick
  |
  +-- Match + complex      → LLM plans the full sequence
  |   Example: "把鸭子放到左前方" (has destination)
  |
  +-- No match             → LLM classify + plan
      Example: "你好" (chat), "随便做点什么" (creative task)
```

## Built-in Skills

The 10 arm skills below are available when an arm agent is connected (via `vector-cli --sim` or a live SO-101 arm). They are wrapped as tools under the `robot` tool category by `SkillWrapperTool`.

| Skill | Aliases | Direct | Auto-steps |
|-------|---------|--------|------------|
| home | go home, reset, 回家, 归位 | Yes | - |
| wave | wave, hello, 挥手, 打招呼, 你好 | Yes | - |
| scan | look, observe, 看看, 扫描 | Yes | - |
| detect | find, search, 检测, 识别, 找一下 | No | scan, detect |
| describe | describe, what is, 描述, 这是什么 | Yes | - |
| pick | grab, grasp, 抓, 拿, 抓起 | No | scan, detect, pick |
| place | put, 放, 放下, 放到, 放置 | No | - |
| gripper_open | open, release, 张开, 松开 | Yes | - |
| gripper_close | close, grip, 夹紧, 合上 | Yes | - |
| handover | handover, give, 递, 递给 | No | - |

### Auto-steps and SkillWrapperTool [LEGACY routing]

`pick` declares `__skill_auto_steps__ = ["scan", "detect", "pick"]`. When the agent calls the `pick` tool, `SkillWrapperTool.execute()` reads this attribute and expands the call into the full step chain before any LLM planning — zero additional LLM calls for the common case. (Retiring at S8; the model now plans the chain.)

### Complex / Long-chain Tasks [LEGACY routing]

> The **VGG GoalDecomposer** producer below is legacy, being strangled at S8 (pending CEO approval); the native model-driven producer handles multi-step goals now. Its files still exist as the fallback path.

For multi-step or ambiguous goals (e.g. "把鸭子放到左前方", "整理桌面"), simple auto_steps expansion is insufficient. These route through the **VGG GoalDecomposer** in `vcli/cognitive/` (`goal_decomposer`, `goal_executor`, `goal_verifier`, `strategy_selector`, `vgg_harness`). The decomposer breaks the goal into a plan, verifies preconditions, and calls `agent.execute_skill()` for each step — this path may involve multiple LLM calls and is designed for robustness, not zero-LLM speed. Note: `goal_verifier` / the honest-verify spine is NOT part of this legacy layer — it is unchanged and shared by all producers.

## Adding a Custom Skill

```python
from vector_os_nano.core.skill import skill, SkillContext
from vector_os_nano.core.types import SkillResult

@skill(
    aliases=["wave", "hello", "挥手", "打招呼", "你好"],
    direct=True,
)
class WaveSkill:
    name = "wave"
    description = "Wave the arm back and forth as a greeting"
    parameters = {"times": {"type": "integer", "default": 3}}
    preconditions = []
    postconditions = []
    effects = {}

    def execute(self, params, context):
        for _ in range(params.get("times", 3)):
            joints = context.arm.get_joint_positions()
            joints[0] = 0.5
            context.arm.move_joints(joints, duration=0.5)
            joints[0] = -0.5
            context.arm.move_joints(joints, duration=0.5)
        return SkillResult(success=True)

# Register:
agent.register_skill(WaveSkill())

# Now these all work:
# "wave"     → direct execute (zero LLM)
# "挥手"     → alias match → same
# "wave 5 times" → LLM plans with params
```

## Multi-Stage Agent Pipeline [LEGACY routing]

> The 6-stage keyword pipeline below is the legacy producer, being strangled at S8 (pending CEO approval). The native producer collapses MATCH/CLASSIFY/PLAN into the model's own tool-use loop.

When alias matching can't handle the input, the full pipeline runs:

```
Stage 1: MATCH     — Check @skill aliases (zero LLM)
Stage 2: CLASSIFY  — LLM determines intent: chat/task/query
Stage 3: PLAN      — LLM decomposes into skill sequence
Stage 4: EXECUTE   — Run skills step by step (deterministic)
Stage 5: ADAPT     — On failure, inject context and retry or explain
Stage 6: SUMMARIZE — LLM generates user-friendly result summary
```

Simple commands (home, open, close, scan) use only Stage 1.
Common patterns (pick X) use Stage 1 with auto_steps.
Complex tasks use the full pipeline.

## Design Principles

1. Skills describe themselves — aliases, parameters, pre/postconditions (LIVE)
2. Adding a skill is one class + one decorator — zero kernel/routing code changes (LIVE plug-in contract)
3. Chinese and English are first-class — aliases support both languages (LIVE)
4. [LEGACY routing, S8] Simple things should be fast — `direct` skills had zero-LLM overhead
5. [LEGACY routing, S8] "LLM is for reasoning, not routing — alias matching handles 80%" — superseded: the model now does the routing too
