# SkillFlow — Skill Plug-in Protocol

**Status:** the `@skill` plug-in protocol is LIVE: adding a skill is one class + one decorator —
no kernel or routing-code edits (the North Star "bring a skill" contract). Skills describe
themselves; routing is the model's job (the native producer reads tool descriptions). The legacy
alias/`auto_steps`/VGG keyword-routing sections were ruled dead (D9/D62/D72–D74) and are deleted — git history keeps them.

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

A skill declares what hardware it needs and queries it at run time through the
`SkillContext` registries — `context.arm` / `context.base` / `context.perception`
(dict registries `arms` / `bases` / `perception_sources`, plus `context.has_arm()`).
Exposure is gated by the embodiment's capability profile
(`embodiments/capability_profile.py::resolve_capability_profile`): a skill needing an arm is
only offered as a tool when the connected body has one. Missing hardware at execute time →
return `SkillResult(success=False, diagnosis_code=...)` — fail loud, never fake.

## SkillWrapperTool — how a skill becomes an LLM tool

Every registered `@skill` is auto-wrapped by `vcli/tools/skill_wrapper.py::SkillWrapperTool`
under the `robot` tool category:
- motor detection: `effects` containing "move"/"navigate"/"arm" ⇒ permission = ask,
  not concurrency-safe;
- post-execution state: motor skills append current position/room to the result;
- recovery hints: on failure, `diagnosis_code` maps to a next-step suggestion for the model.

## Adding a custom skill

```python
@skill(aliases=["wave", "挥手"], direct=True)
class WaveSkill:
    name = "wave"
    description = "Wave the arm back and forth as a greeting"
    parameters = {"times": {"type": "integer", "default": 3}}
    preconditions, postconditions, effects = [], [], {}

    def execute(self, params, context):
        for _ in range(params.get("times", 3)):
            joints = context.arm.get_joint_positions()
            joints[0] = 0.5;  context.arm.move_joints(joints, duration=0.5)
            joints[0] = -0.5; context.arm.move_joints(joints, duration=0.5)
        return SkillResult(success=True)

agent.register_skill(WaveSkill())   # or drop the file in vector_os_nano/skills/
```

A skill may wrap an external VLA/VLM or a classical grasp/nav stack — the runtime routes to it by NL and grades it like any other step.

## Binding a skill's goal class to a verify oracle (D69 — read this before shipping)

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

Full verdict contract + acceptance runbook: [docs/verify.md](verify.md).

## Design principles

1. Skills describe themselves — description, parameters, pre/postconditions.
2. Adding a skill is one class + one decorator — zero kernel/routing edits.
3. Chinese and English are first-class — aliases and NL routing support both.
4. Success is proven by a GT oracle the skill cannot author — never self-reported.
