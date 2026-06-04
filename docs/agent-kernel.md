# Verified Agent Kernel — Architecture Direction

- Status: Proposed
- Date: 2026-06-04
- Scope: the Vector OS orchestration layer (VectorEngine + VGG + CLI) — the OS *around*
  the models, in service of robots.

## Vision

Vector OS is not another model — it is an agent-orchestration system built *around*
models, in service of robots. It plans tasks, routes each instruction to the right model
and skill, verifies every step of execution, and recovers automatically on failure — the
things models do unreliably on their own are exactly Vector OS's job. Unified large
models, specialized small models, classical skills, and atomic actions are orchestrated
into one deployable whole that is cross-hardware, cross-model, and cross-system.

Further, Vector OS is a *programmable platform*: developers build physical AI the way they
write code ("code physical AI"). Any model, any skill, any robot — plug and play.

Models are raw capability. We are not trying to build the smartest brain right now; we
make *every* brain run trustworthily on the industrial floor, callable and buildable by
anyone. **Vector OS is the operating system for the robot world.**

## Thesis (how the architecture serves the vision)

The VGG (Verified Goal Graph) kernel is the engine of that OS. It decomposes a task into
an inspectable goal graph, **routes each sub-goal to the right capability** (a skill, an
atomic action, or a model — large or specialized), attaches a machine-checkable success
predicate to every step, executes via ranked strategies, and re-plans on verified failure
— with no fine-tuning. The kernel is deliberately model-, skill-, and hardware-agnostic
*so that* it can orchestrate a heterogeneous fleet of brains and bodies in the field.

A **world** is a deployment target the kernel drives: a robot embodiment (Go2, SO-101 /
Piper, …) and — on a developer's laptop — a robot-free **dev** world used to build and
harden the kernel itself. The dev / macOS path is a *means*, not the product: it gives
cross-system deployability, a fast hardware-free dev loop, and a way to exercise the
orchestration logic. **Robots remain the end.**

This serves two near-term goals at once:

1. **Cross-platform / cross-system.** The kernel — engine, VGG sandbox, routing, tools,
   backends, session, permissions — is pure Python with no robot/ROS2 dependency, so it
   runs anywhere (macOS first) and the *same* orchestration deploys onto real hardware by
   swapping the world.
2. **A trustworthy orchestration layer the field needs.** Deterministic per-step
   verification, an inspectable self-revising plan graph, measured-strategy selection,
   and experience compilation — what makes unreliable models dependable in production.

Note: today the kernel routes sub-goals to skills/primitives behind a single LLM backend
(`vcli/backends/`). The full vision — routing to a *heterogeneous model zoo* (specialized
detectors/planners, VLA policies, small task models) as first-class routable capabilities
alongside skills — is a forward direction the architecture is built toward, not yet
implemented.

## Differentiation (honest)

Mainstream agent runtimes (Claude Code, Cursor, Devin, OpenHands, LangGraph) bottom out
in a ReAct-style tool loop where verification is the model self-assessing over whatever
tool feedback exists. None ships deterministic per-step verification as a first-class
runtime primitive.

| Dimension | Mainstream agent CLIs | Verified Agent Kernel (VGG) |
|---|---|---|
| Verification | Model self-assessment + opportunistic tests | Machine-checkable `verify` predicate per sub-goal (deterministic, not LLM-judge), evaluated in an AST sandbox |
| Plan representation | Opaque chat chain / flat todo / author-defined static graph | LLM-generated, inspectable, editable, replayable goal graph (DAG + per-node pre/post-conditions); the agent re-plans against measured node outcomes |
| Retry / strategy | Single-trajectory reflection; "multi-agent" = parallel *different* tasks | Ranked alternative strategies for the *same* goal, selected by measured success rate |
| Cross-task learning | Human-authored skills/rules; no self-learning | Successful verified traces compiled into reusable templates; no fine-tuning |
| Cost / latency | Caching + compaction | Same, plus a deterministic single-skill fast path (1-step tree, no LLM call) |

**Novelty framing — do not overclaim.** Each pillar has clear prior art: Voyager
(verified, reusable skill library without fine-tuning), ToolGate / ProgPrompt
(pre/post-condition contracts), process reward models (step-level verification), LLM+P
(symbolic plan verification), multi-armed bandits (measured selection). The defensible
contribution is the **conjunction and engineering**: deterministic per-sub-goal predicate
contracts + measured-success strategy selection + verified-by-construction template
compilation, unified in one fine-tuning-free, domain-general runtime, targeting the
generator-verifier gap that LLM-judge and self-refine pipelines cannot close.

**Soft spots to design around (state them openly):**

- The LLM still authors the goal tree and the predicates, so verification bias re-enters
  at predicate-authoring time. Deterministic predicates remove subjectivity only within
  what the predicate can express. Mitigation: predicate libraries, human-reviewable
  predicates, and an escalation ladder (deterministic predicate -> visual/VLM check ->
  LLM judge as last resort; the `VisualVerifier` is an early instance).
- "No system unites all four pillars" is a best-effort 2026 literature finding, not a
  proof. Keep external claims hedged.
- LLM-authored strategy code is not sandboxed today (only the VGG `code_executor` path
  is). Any code-as-policy execution must be forced through the AST validator.

## Architecture: kernel vs world plugin

The seam already exists implicitly in the codebase; this direction names it and pushes
the robot vocabulary behind it.

```
+-------------------------------------------------------------+
|                       Agent Kernel                          |
|  VectorEngine (tool loop, dispatch, permissions, session)   |
|  Backends (Anthropic / OpenAI-compat / local)               |
|  VGG: GoalDecomposer (mechanics) / GoalVerifier (sandbox)   |
|       GoalExecutor / VGGHarness / StrategySelector          |
|       StrategyStats / CodeExecutor / ExperienceCompiler     |
|  General tools: file_read/write/edit, bash, glob, grep, web |
+----------------------------+--------------------------------+
                             | registers
        +--------------------+---------------------+
        |                    |                     |
   robot embodiments     dev world            (more embodiments /
   (Go2, SO-101/Piper)   (laptop, robot-free   deployment targets)
   tools + verify ns +   build/test means)     ...
   model+skill routing   tools + verify ns +
   + persona             routing + persona
```

A **world plugin** registers exactly four things, all consumed through interfaces the
kernel already has:

1. **Tools** — into the existing `CategorizedToolRegistry` under its own category (intent
   routing already filters by category).
2. **A verify/primitive namespace** — the dict `GoalVerifier` evaluates predicates
   against (today built by `engine._build_verifier_namespace`; becomes a per-world
   contribution).
3. **A decompose vocabulary** — the strategy menu (already registry-driven) plus the
   verify-function names, signatures, descriptions, and few-shot examples the
   `GoalDecomposer` prompt teaches (today robot-hardcoded).
4. **A persona / prompt block** — replacing the hardcoded robot `ROLE_PROMPT` /
   `TOOL_INSTRUCTIONS`.

A world thus contributes the **routable capabilities** for its domain — today skills +
atomic actions; as the heterogeneous model zoo lands, specialized models (detectors,
planners, VLA policies) register here too and the StrategySelector routes a sub-goal to
the right one. This is the "any model, any skill, any robot — plug and play" seam.

What stays in the kernel vs moves to the robot world:

| Stays in kernel (already generic) | Moves to robot world plugin |
|---|---|
| `VectorEngine`, backends, session, permissions, intent-router mechanism | `_init_agent` Go2/arm/ROS2 launch (`vcli/cli.py`) |
| VGG: verifier sandbox, executor, harness, selector, stats, code-executor, topo-sort, retry | Robot verify bindings in `engine._build_verifier_namespace` |
| `GoalDecomposer` mechanics (JSON parse, AST validation) | `GoalDecomposer` robot *vocabulary* (verify funcs, examples) |
| General tools: file/bash/glob/grep/web | Robot / diag / sim tools + skill wrappers |
| `CategorizedToolRegistry` category mechanism | `core/agent.py`, `skills/`, `hardware/`, `perception/`, `ros2/`, `mcp/` |

The kernel never imports a world; a world registers into the kernel via a small `World`
protocol. A default `dev`/`code` world ships in the kernel; `robot` becomes an optional
plugin.

## Current state: real vs built-but-unwired

Grounded in a read of `vcli/cognitive/` and `engine.py`:

- **Real and robust:** the kernel loop — decompose -> verify sandbox (AST-checked,
  restricted builtins, 5s timeout) -> execute (topo-sort, timeout, fallback, abort) ->
  3-layer retry/re-plan harness. Cleanly decoupled from robotics behind a single binding
  method (`_build_verifier_namespace`).
- **Wired in Phase B (were latent):**
  - `code_executor.py` — now reachable via the `code` branch in
    `GoalExecutor._execute_strategy`; instantiated in `engine.init_vgg`.
  - `tool_dispatcher.py` (new) — the `tool` branch: a verified sub-goal dispatches one
    kernel tool through `PermissionContext` + a per-world allowlist.
  - `experience_compiler.py` + `template_library.py` — `engine._maybe_compile_experience`
    feeds successful traces in; the compiled `TemplateLibrary` drives the no-LLM
    decompose fast path. `strategy_params` now survives compile -> reuse.
  - `strategy_stats.py` — persisted under `~/.vector/` when `init_vgg(persist_dir=...)` is
    set (the CLI passes it); atomic save.
  - `trace_store.py` (new) — save/load/replay + the evidence gate.
- **Robot-gated (unchanged):** `vgg_decompose` returns `None` when no robot base is
  connected; the decomposer vocabulary is robot-specific. The dev world is not robot-gated.

Implication: a large fraction of the differentiation is wiring and de-coupling, not
greenfield.

## Roadmap

**Phase A — Kernel/world decoupling + macOS general-agent CLI. [DONE — shipped on
`feat/verified-agent-kernel`].**
Fixed the packaging gap so the CLI installs and starts on a clean Mac; made the persona
world-selectable (general default with no robot); formalized the `World` seam
(`vcli/worlds/`) and shipped a default dev/code world; un-gated VGG from a connected robot
and made the decomposer vocabulary injectable. Outcome: `vector-cli` runs on macOS as a
general verified agent over file/bash/web tools, zero robot dependencies. The dev world
does decompose + verify (execution is Phase B).

**Phase B — Wire the differentiation tier. [DONE — shipped on
`feat/verified-agent-kernel`; see [agent-kernel-phase-b-plan.md](agent-kernel-phase-b-plan.md)].**
Keystone resolved as tool-backed via `PermissionContext`. B.1 added tool-backed execution
(the dev world *acts* through the permission system + a per-world allowlist) and code-as-policy
(AST sandbox), plus verify-as-eval (predicates as a self-grading, replayable eval signal via
`cognitive/trace_store.py`; evidence-gated "done"; a `vector-eval` headless harness). B.2 added
persistent strategy stats and experience compilation -> template reuse (no-LLM decompose
fast path), with `strategy_params` carried through compile/serialize/instantiate. Persistence
is opt-in (`init_vgg(persist_dir=...)`) under `~/.vector/`. Outcome: an agent that self-verifies,
gates its own completion on evidence, and learns from its own runs without fine-tuning — the
differentiation story made real.

**Phase C — Robot worlds + the heterogeneous model zoo (the actual product). [PROPOSED —
design in [agent-kernel-phase-c-plan.md](agent-kernel-phase-c-plan.md); awaiting keystone
sign-off].**
Fold the robot stack into `robot` world plugin(s) per embodiment; make the kernel
orchestrate a *fleet of brains* — route a sub-goal to a specialized model (detector,
planner, VLA policy), a classical skill, or an atomic action, by measured fit; deliver
the "any model / any skill / any robot, plug and play" platform for building physical AI.
The dev world stays as the build/test means. The design proposes a `Capability` protocol +
per-world `CapabilityRegistry` and **one** new `"capability"` executor branch (keystone
mirrors B's tool-backed decision), reusing the existing `StrategyStats` bandit for
cross-capability routing and keeping the deterministic `verify` invariant untouched.

## Forward direction: from one LLM to a model zoo

The orchestration vision needs the kernel to route to *capabilities*, not just one LLM.
Today `vcli/backends/` is a single chat-LLM backend and `StrategySelector` routes a
sub-goal only to a skill/primitive. The evolution:

1. Generalize `backends/` into a **routable-capability registry**: a capability is
   anything with a typed `(input -> output)` contract and measured stats — a chat LLM, a
   specialized detector/segmenter, a planner, a VLA policy, a classical skill, an atomic
   action. Each world registers its capabilities (see the world-plugin seam above).
2. Extend `StrategySelector` to choose *across capability kinds* by measured fit (the
   bandit/stats machinery already exists), not just among skills — so "detect the red
   cup" routes to a small detector, "plan a grasp" to a planner, "walk" to a skill.
3. Keep verification unchanged: every routed step still carries a deterministic `verify`
   predicate, so a heterogeneous fleet of brains stays trustworthy.

This is net-new architecture (beyond Phase A/B) and is the bridge from "verified agent
kernel" to "Vector OS orchestrating any model/skill/robot." Sequence it after Phase B.

## Risks and mitigations

- *Verification bias at predicate-authoring time* — predicate libraries, human review,
  escalation ladder (deterministic -> visual -> LLM judge).
- *Unsandboxed generated code* — force all code-as-policy through the AST validator with
  an import allowlist before execution.
- *Scope creep from "make VGG general"* — Phase A only un-gates and injects vocabulary;
  the rich dev-world strategies (code-as-policy, eval) are Phase B.
- *Overclaimed novelty* — keep external positioning as synthesis novelty; cite Voyager,
  ToolGate, PRMs, LLM+P as the bar cleared.

## Non-goals (this direction)

- **Building a foundation model or competing on raw model intelligence.** Vector OS
  orchestrates whatever brains exist (large, small, specialized) and makes them
  trustworthy in the field; the smartest-brain race is not ours to run right now.
- **Positioning the dev/macOS path as the product.** It is a means — cross-system
  deployability and a hardware-free dev loop. The end is robots.
- Re-implementing industrial navigation (FAR/TARE) on macOS. The robot world keeps ROS2
  as an opt-in high-fidelity backend on Linux.
- Driving real robot hardware from macOS. Real hardware stays on Linux.
- Fine-tuning any model. The kernel is orchestration-first and frozen-model by design.

## References (prior art, for honest positioning)

ReAct; Reflexion; Tree-of-Thoughts; LATS; Plan-and-Solve; process reward models
("Let's Verify Step by Step"); generator-verifier gap (Stechly and Kambhampati); LLM+P;
Code-as-Policies; ProgPrompt; Voyager; ToolGate; FormalJudge; VeriGuard; library learning
(LILO); bandits for LLM selection.
