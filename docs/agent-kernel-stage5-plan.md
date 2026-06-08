# Verified Agent Kernel — Stage 5 Plan (unify the two planning paths)

- Status: **SCOUT — design + one safe additive step shipped.** The
  observable intent decision (`VectorEngine.classify_intent` ->
  `IntentDecision`) is in the working tree; `vgg_decompose` now single-sources its
  fork through it. No behaviour change; full canonical suite green (803 passed, 4
  skipped). The rest of this doc is the plan; nothing else is implemented yet.
- Date: 2026-06-08
- Branch: `feat/verified-agent-kernel`
- Related: [ARCHITECTURE.md](ARCHITECTURE.md) §4 (planning flow),
  [agent-kernel-STATUS.md](agent-kernel-STATUS.md),
  [agent-kernel-phase-d-plan.md](agent-kernel-phase-d-plan.md) (Stage 5 lives in Phase D),
  [ADR-008](architecture-decisions/ADR-008-playground-parallel-track.md)

## Why this stage exists

Today the engine has **two planning paths that can diverge**, forked by a keyword
intent gate:

- **VGG path** — `vgg_decompose` -> `GoalTree` -> `vgg_execute` (VGGHarness:
  decompose -> topo-execute -> deterministic verify -> Blackboard bind -> replan).
  This is the closed loop and the project's differentiator.
- **tool_use path** — `run_turn`, a ReAct-style loop: call backend, dispatch tools,
  append results, loop until `end_turn`. No deterministic verify, no GoalTree, no
  observation-driven replan; the LLM self-assesses.

The North Star (CLAUDE.md rule 1) is that **natural language controls everything via
decompose -> plan -> execute -> verify -> replan, a CLOSED loop, not keyword
matching**. As long as a keyword gate decides which interactions get verified, an
entire class of interactions (anything the gate routes to `run_turn`) escapes the
moat (rule 5: "verify is the moat"). Stage 5 = collapse the two paths into **one
closed-loop controller** so deterministic verify + observation-driven replan apply to
ALL interactions, and the keyword intent gate is dropped.

This is a **big** architectural change. This document is the design + the staging; the
scout increment ships only step S5.0 (below).

---

## 1. Precise divergence map (as the code stands at HEAD)

The fork happens in `vcli/cli.py` (~line 1676): `engine.vgg_decompose(user_input)` is
called first; a non-`None` `GoalTree` takes the VGG path (`vgg_execute_async`), else
the turn falls through to `engine.run_turn(...)`. The gate itself lives inside
`vgg_decompose` (now surfaced via `classify_intent`). Two MCP/CLI entry points share
the one engine, so the fork must be fixed in the engine, not per-frontend.

| Concern | VGG path | tool_use path (`run_turn`) |
|---|---|---|
| **Entry** | `vgg_decompose` -> `vgg_execute[_async]` | `run_turn` |
| **Routing** | `classify_intent` / `should_use_vgg` (keyword gate) | the default when the gate says no |
| **Plan representation** | frozen `GoalTree` DAG of `SubGoal` (verify + strategy + foreach) | none — implicit in the LLM's tool-call stream |
| **Decompose** | `GoalDecomposer` (LLM, vocab single-sourced from registry) + 1-step fast path | none — LLM emits tool calls directly |
| **Strategy / dispatch** | `StrategySelector` -> skill / primitive / code / tool / capability, via `GoalExecutor` | `ToolRegistry` + `_dispatch_tools` (permissions, concurrency partition, hooks) |
| **Verify** | **deterministic** `GoalVerifier` (AST sandbox) per step; evidence gate | none — model decides it's done (`stop_reason == end_turn`) |
| **Observation capture** | `Blackboard` (per-run); `result_data`; `${step.path}` binding; `StepRecord` | tool results appended to `Session` messages; nothing structured/bindable |
| **Replan** | VGGHarness 3 layers + S4-4 obs-driven mid-tree replan; `validation_notes` fed back | implicit — LLM re-decides next tool from message history |
| **Loop bound** | `HarnessConfig` (step retries / redecompose / pipeline / obs-replan) | `max_turns` |
| **Output surface** | `ExecutionTrace` + `run_snapshot` EXPORT VIEW (observation surface) | `TurnResult` (text + `ToolCall`s) |
| **Execution** | async (`vgg_execute_async`, background thread) | synchronous (blocking `run_turn`) |
| **Permissions** | dev tools via `ToolDispatcher` allowlist + `tool_permission_resolver`; robot via skill path | 7-layer `PermissionContext.check` + `ask_permission` per tool |
| **Stop/abort** | `abort` flag + `_vgg_cancel` event; P0 stop bypass in `run_turn` | `abort_event` per turn; P0 stop bypass |

**What each path uniquely OWNS (the merge must preserve all of it):**

- tool_use owns: the live ReAct conversation loop, streaming `on_text`, concurrency
  partitioning of read-only tools, the 7-layer permission gate with interactive
  `ask`, tool hooks (pre/post), session message threading, auto-compaction, and the
  P0 stop bypass.
- VGG owns: the frozen plan, deterministic per-step verify + evidence gate, the
  Blackboard + `${path}` binding, the StrategySelector executor-type seam, the
  harness replan layers + obs-driven replan, StrategyStats / experience compilation,
  and the observation EXPORT VIEW.

**What actually blocks merging them into one controller:**

1. **Verify has no analogue on the tool_use side.** A free-form tool turn has no
   per-step predicate and no GoalTree to attach one to. Either every interaction
   gets decomposed into a verifiable GoalTree (expensive; an LLM call for "hello"),
   or the controller must support **degenerate / trivially-verified** steps so chat
   stays cheap. Rule 5 (verify is the moat) must not be weakened to achieve this.
2. **Tool dispatch lives in two places** (`GoalExecutor`/`ToolDispatcher` vs
   `run_turn`/`_dispatch_tools`) with different permission, concurrency, hook, and
   streaming behaviour. Unifying requires ONE dispatch seam both planners call.
3. **Sync vs async.** VGG runs in a background thread (CLI stays responsive); ReAct
   blocks. A unified controller needs one execution model (likely: always async with
   a streaming observation channel) without regressing CLI latency or the MCP server.
4. **Plan vs no-plan.** ReAct decides the next action one step at a time from history;
   VGG commits to a DAG up front (then replans). The unified controller must support
   **incremental / single-step planning** as a special case of the GoalTree loop, so
   conversation doesn't pay full decomposition cost.
5. **Routing is keyword-based and lossy.** `should_use_vgg` is a heuristic; dropping
   it means SOMETHING must decide per-turn whether to plan-and-verify or to answer
   directly — ideally the decomposer itself (it can return a 0-action / answer-only
   plan), so the decision becomes part of the closed loop, not a gate in front of it.
6. **Two entry points** (`vector-cli`, `vector-os-mcp`) both fork on the path. The
   unification must land in the engine so both frontends switch atomically.

---

## 2. Target unified flow

One controller — call it the **closed-loop turn** — replaces the cli-level fork:

```
NL input
  |
  v
classify (NOT a keyword gate): the decomposer returns a GoalTree that may be
  - 0-action "answer" plan      (pure conversation; verify trivially true)
  - 1-step verified plan        (single skill / tool; deterministic verify)
  - N-step DAG (+ foreach/...)   (complex; full closed loop)
  |
  v
run the SAME harness loop for every shape:
  topo-execute -> dispatch via ONE tool/skill seam -> capture to Blackboard
    -> deterministic verify (trivial-true for answer steps) -> replan on
       fail / observed divergence
  |
  v
stream text + per-step observation EXPORT VIEW; return one result type
```

Key properties:

- The keyword `should_use_vgg` gate is **gone**. The decompose step decides shape,
  and a 0/1-step plan is the cheap path (the fast path stays no-LLM for alias/skill
  matches; chat may be a single answer-only step).
- **Every** turn produces a verifiable plan; verify still runs (trivially true for
  answer-only steps, so the moat is never bypassed, only degenerate).
- One tool/skill dispatch seam — permissions, concurrency, hooks, streaming live in
  one place that both the executor and any direct-answer step call.
- One result/observation surface for CLI + MCP.

---

## 3. Seam-safe staging (additive; both paths keep working until the switch)

Each step is independently shippable, keeps the canonical suite green, and does NOT
flip routing until the final cut-over. Order chosen so risk is paid down before the
behaviour change.

- **S5.0 — observable decision (SHIPPED, this scout).** `classify_intent` ->
  frozen `IntentDecision{route, reason, complex}`; `vgg_decompose` single-sources its
  fork through it; debug-logged. Pure, no behaviour change. Gives the merge a stable,
  tested seam and makes routing inspectable. *(done; 10 new tests)*

- **S5.1 — one dispatch seam.** Extract the tool execution body of `run_turn`
  (`_dispatch_tools` + permission + hooks + concurrency) behind a small interface
  that `GoalExecutor`'s tool path (`ToolDispatcher`) ALSO uses, so there is one place
  that runs a tool with permissions/hooks. Additive: both callers keep their current
  entry points; only the shared core is deduplicated. Test: parity tests that the
  seam produces identical `ToolResult` + permission behaviour for both callers.

- **S5.2 — answer-only GoalTree shape.** Teach `GoalDecomposer` to emit a 0-action /
  answer-only plan (one `SubGoal` with `verify="True"` and a text strategy) for pure
  conversation, and make the executor/harness run it (verify trivially true, evidence
  gate aware that an answer step carries no robot evidence). Additive: nothing routes
  to it yet. Test: a conversational input decomposes to a 1-step answer plan that
  verifies true and yields the answer text.

- **S5.3 — unified controller method (dark-launched).** Add
  `engine.run_turn_unified(...)` that ALWAYS decomposes (answer-only for chat) and
  runs the harness loop, streaming text + observation views, returning one result
  type. NOT wired into the CLI/MCP yet — exercised only by tests + an opt-in flag.
  Test: it reproduces both a chat turn and a VGG plan turn end-to-end on the mock
  backend.

- **S5.4 — cut over the frontends, drop the gate.** Switch `cli.py` and the MCP
  server to `run_turn_unified`; delete the `vgg_decompose`-then-`run_turn` fork and
  the `should_use_vgg` keyword gate (keep `is_complex` only if the decomposer still
  needs a cheap hint). Keep `run_turn` available one release as a fallback behind a
  flag, then remove. Update ARCHITECTURE §4 (remove the `[Stage 5 TODO]` markers) and
  STATUS in the SAME commit (Doc Governance).

---

## 4. Risks (kept honest)

- **Cost / latency.** Decomposing every turn (even "hi") risks an LLM call per chat
  turn. Mitigation: the no-LLM fast path stays for alias/skill matches; a cheap
  pre-classifier (could be the SAME keyword heuristic, but now feeding the decomposer
  rather than gating verify) keeps trivial chat from paying decomposition. The gate
  becomes an *optimization hint*, not a *correctness fork*.
- **Weakening the moat.** "Trivially-true verify for answer steps" must not become a
  backdoor that lets real actions skip verify. The evidence gate must distinguish an
  answer-only step (legitimately no robot evidence) from an action step that produced
  none. Rule 5: the sandbox may only get stricter.
- **Sync->async regression.** Moving chat onto the async harness path could change CLI
  ordering / streaming or break the MCP request/response contract. Mitigation: S5.3 is
  dark-launched and parity-tested before S5.4.
- **Permission/hook drift.** Two dispatch implementations have subtly different
  permission + hook behaviour; the S5.1 merge must be parity-tested or a tool could
  gain/lose a gate.
- **Two frontends.** CLI and MCP must switch together; a half-switch leaves divergent
  behaviour. Land the cut-over in the engine, flip both in one commit.
- **Big-bang temptation.** The whole point of the staging is to AVOID a rewrite.
  Anything that can't be made additive + parity-tested is not ready to land.

---

## 5. Test strategy

- **Parity tests (the core safety net).** For S5.1 and S5.3, assert the new shared
  path produces identical observable results to the old path for a fixed corpus of
  turns (a chat turn, a 1-skill turn, a multi-step plan turn, a denied-permission
  turn, a foreach turn) on the **mock backend** — no live LLM (project rule).
- **Routing matrix tests (S5.0, shipped).** `classify_intent` returns the right
  `IntentDecision` for each branch (disabled / no-router / robot-not-ready /
  gate-reject / complex / actionable) and is pure/repeatable.
- **Degenerate-verify tests (S5.2).** An answer-only plan verifies true, carries no
  robot evidence, and the evidence gate does NOT mark a real action step as verified
  just because it has no predicate.
- **Evidence-gate guard.** A regression test that an ACTION step with no deterministic
  predicate is NOT counted as verified (the moat stays intact through the merge).
- **No-live-LLM rule.** All of the above run on the mock backend in the default suite;
  any real-LLM smoke is marked and skipped by default.
- **Green bar.** Canonical set `tests/vcli tests/unit/vcli`, baseline 786; each step
  keeps it green and adds its own regressions.

---

## 6. Scout increment delivered (S5.0)

- `vcli/engine.py`: added frozen `IntentDecision{route, reason, complex}` (with a
  `use_vgg` convenience property) and `VectorEngine.classify_intent(user_message)` — a
  PURE read of the same gate conditions `vgg_decompose` used. `vgg_decompose` now calls
  `classify_intent` (single-sourced decision), debug-logs `route/reason/complex`, and
  is otherwise behaviour-identical (the tool_use route is exactly the old inline
  `return None` set; `is_complex` is pure so computing it in the classifier is safe).
- `tests/unit/vcli/test_engine_classify_intent.py`: 10 tests — the routing matrix,
  `IntentDecision` frozen + `use_vgg`, purity/repeatability, and that `vgg_decompose`
  short-circuits exactly on a tool_use decision.
- Canonical suite: **803 passed, 4 skipped** (was 793 + 10 new). No commit.
