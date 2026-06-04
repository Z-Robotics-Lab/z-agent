# Verified Agent Kernel — Architecture Direction

- Status: Proposed
- Date: 2026-06-04
- Scope: the agentic system (VectorEngine + VGG + CLI), not the robot stack

## Thesis

VGG (Verified Goal Graph) is not a robot feature. It is a **domain-general,
verified-agent kernel**: a runtime that decomposes a task into an inspectable goal
graph, attaches a machine-checkable success predicate to every sub-goal, executes via
ranked strategies, and re-plans on verified failure — with no fine-tuning. The robot is
one **world** the kernel can drive, alongside future worlds (code/dev, browser, ops).

This single reframe addresses both current goals at once:

1. **Cross-platform (macOS first).** The kernel — engine, VGG sandbox, general tools
   (file/bash/grep/web), backends, session, permissions — is already pure Python with no
   robot or ROS2 dependency. Once the robot coupling is pushed behind a world plugin, the
   CLI runs on macOS as a general verified agent with zero robot dependencies.
2. **Architectural differentiation.** The capabilities the kernel embodies —
   deterministic per-step verification, an inspectable self-revising plan graph,
   measured-strategy selection, and experience compilation without fine-tuning — are
   precisely the white space the mainstream agent CLIs leave open.

The robot does not get demoted; it becomes the flagship world ("the same kernel that
verifies your code also drives a real quadruped").

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
   robot world          dev/code world        browser world (future)
   tools + verify       tools + verify         ...
   namespace +          namespace +
   decompose vocab      decompose vocab
   + persona            + persona
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
- **Built but not wired (latent headline features):**
  - `code_executor.py` — complete AST-sandboxed Python executor; missing only a
    `code` branch in the executor dispatch and a `code_as_policy` entry in the decomposer
    menu.
  - `experience_compiler.py` + `template_library.py` — compile successful traces into
    reusable templates; no runtime feeds traces in.
  - `strategy_stats.py` — cross-session persistence implemented but disabled (engine
    constructs `StrategyStats()` with no path -> in-memory only).
- **Robot-gated:** `vgg_decompose` returns `None` when no robot base is connected; the
  decomposer vocabulary is robot-specific.

Implication: a large fraction of the differentiation is wiring and de-coupling, not
greenfield.

## Roadmap

**Phase A — Kernel/world decoupling + macOS general-agent CLI.**
Fix the packaging gap so the CLI installs and starts on a clean Mac; make the persona
world-selectable (general default with no robot); formalize the `World` seam and ship a
default dev/code world; un-gate VGG from a connected robot and make the decomposer
vocabulary injectable. Outcome: `vector-cli` runs on macOS as a general verified agent
over file/bash/web tools, zero robot dependencies. This is the cross-platform win and the
demo vehicle.

**Phase B — Wire the differentiation tier.**
Add the `code-as-policy` execution branch (forced through the AST validator);
verify-as-eval (predicates as a self-grading, replayable eval signal; evidence-gated
"done"); experience compilation -> template reuse; persistent strategy stats. Outcome: an
agent that self-verifies, gates its own completion on evidence, and learns from its own
runs without fine-tuning — the differentiation story made real.

**Phase C — Worlds ecosystem + robot as flagship.**
Fold the robot stack into a `robot` world plugin; ship the `dev` world by default;
explore compositional worlds (one verified plan that both edits code and drives the
robot).

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

- Re-implementing industrial navigation (FAR/TARE) on macOS. The robot world keeps ROS2
  as an opt-in high-fidelity backend on Linux.
- Driving real robot hardware from macOS. Real hardware stays on Linux.
- Fine-tuning any model. The kernel is provider-agnostic and frozen-model by design.

## References (prior art, for honest positioning)

ReAct; Reflexion; Tree-of-Thoughts; LATS; Plan-and-Solve; process reward models
("Let's Verify Step by Step"); generator-verifier gap (Stechly and Kambhampati); LLM+P;
Code-as-Policies; ProgPrompt; Voyager; ToolGate; FormalJudge; VeriGuard; library learning
(LILO); bandits for LLM selection.
