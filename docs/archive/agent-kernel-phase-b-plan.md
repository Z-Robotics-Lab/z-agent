# Verified Agent Kernel — Phase B Plan (Differentiation Tier)

- Status: **Shipped — B.1 + B.2 implemented on `feat/verified-agent-kernel`.** Keystone
  resolved as (a) tool-backed via `PermissionContext`. See "Shipped" note below.
- Date: 2026-06-04
- Branch: `feat/verified-agent-kernel` (Phase A merged on this branch + pushed)
- Related: [agent-kernel.md](agent-kernel.md), [ADR-006](architecture-decisions/ADR-006-agent-kernel-world-plugin.md)

## Shipped (what actually landed)

B.1 (`feat(kernel): wire dev-world execution + verify-as-eval`) and B.2
(`feat(kernel): persistent stats + experience compilation`) are implemented and tested.
Deviations from this plan, for the record:

- **Keystone (a) tool-backed** as recommended: new `cognitive/tool_dispatcher.py` runs
  every dev side effect through `PermissionContext.check` + a per-world allowlist
  (`worlds/dev.py:DEV_TOOL_ALLOWLIST`). Bash deny-list + file_write overwrite guard reused.
- **Plan omission caught:** `tool_call` also had to be added to the decomposer's
  `KNOWN_STRATEGIES` gate (via `DEV_VOCAB.strategies`), or LLM-authored `strategy="tool_call"`
  is silently cleared before reaching the selector.
- **Persistence is opt-in** via `engine.init_vgg(persist_dir=...)` (None = in-memory) so
  tests/evals never write to `~/.vector`. The CLI passes `~/.vector`. Both `_DEFAULT_PATH`s
  moved to `~/.vector/`.
- **strategy_params carried through templates** (step-17 surprise handled): parameterized
  to `${param}` for multi-trace templates, verbatim for concrete; v1 files load tolerantly.
- **Tests live in `tests/vcli/`** (`test_level63..66`), not `tests/harness/` — the harness
  `conftest.py` does `pytest.importorskip("mujoco")`, and these are robot-free kernel tests
  that must run on macOS with zero robot deps.
- `cognitive/trace_store.py` carries `replay` + `evidence_passed` (the evidence gate helper
  is shared by `cli._on_vgg_complete` and `eval_runner`).

**Post-ship hardening (adversarial review).** A multi-agent adversarial review of B.1+B.2
confirmed 17 findings (5 dismissed as already gated by the permission prompt); all are
fixed (commit `fix(kernel): harden Phase B execution path`). Highlights:
- Intrinsic tool `deny` (bash deny-list, dangerous-path) is now an unconditional hard stop
  evaluated *before* `no_permission` — `--no-permission` can no longer disable a safety rail.
- `file_write` / `file_edit` hard-deny protected paths (parity with the read path).
- The code-as-policy sandbox no longer receives `tests_pass` (a subprocess runner).
- Evidence gate: a VLM visual-override pass is no longer counted as deterministic evidence
  (`StepRecord.visual_override`; trace schema v2), so `evidence_passed` and `replay` agree.
- Template fast-path: concrete `tool_call`/`code` templates require a *full* sub-goal-name
  match (no single-token hijack); skills keep lenient synonym matching.
- The learning tier (stats + templates) is wired for the **dev world only** — the robot
  decompose/execute path stays byte-identical and is not contaminated by dev `tool_call`
  stats. Persistence (`init_vgg(persist_dir=...)`) is opt-in everywhere.
- Tests: `tests/vcli/test_level67_dev_e2e.py` (full loop) and `test_level68_review_fixes.py`
  (one per fix).

Deferred follow-ups: incremental experience compilation (currently a bounded O(n) recompile
per success) and full cwd-containment for the autonomous write path (the dangerous-path
deny-list covers the sensitive targets; global containment would break the interactive
agent's legitimate absolute-path writes).

## Goal

Turn the VGG kernel from "decompose + verify" into "decompose + execute + self-grade
+ learn" by wiring four capabilities that are already coded but unplugged. Keep the
robot path and MCP working at every stage. macOS / Python 3.12 / uv / ruff / pytest;
LLM mocked in all tests; new persistence under `~/.vector/`.

Suggested PR split: **B.1 = code/tool execution + verify-as-eval** (the demo/story),
**B.2 = persistent stats + experience compilation** (the learning tier). B.2 depends on
B.1 producing real traces.

## KEYSTONE DECISION (resolve before coding B.1)

A `code_as_policy` sub-goal carries **no code today** (the selector passes only `params`,
`strategy_selector.py:205-206`), and `CodeExecutor`'s sandbox blocks all file/command I/O
(`code_executor.py:216-243`, only `import math`). So making dev sub-goals *act* forces a
choice:

- **(a) Tool-backed [RECOMMENDED].** A sub-goal dispatches a real kernel tool
  (`file_write`/`bash`) through the existing `PermissionContext.check` + a per-world tool
  allowlist. Reuses every safety guard (bash deny-list, file_write overwrite guard); one
  audited surface; smaller diff. `code_as_policy` via `CodeExecutor` stays alive for
  **robot motion only**, AST-gated as today.
- **(b) Sandboxed-code, widened.** Inject `write_file`/`run_command` into `CodeExecutor`
  and widen its sandbox. More expressive, but every injected primitive **bypasses**
  `PermissionContext` — the "unsandboxed generated code" risk in agent-kernel.md:63. Not
  recommended.

Recommended defaults for the lower-stakes questions (confirm or override next session):
- Payload carried in `SubGoal.strategy_params` (`{"tool","args"}` or `{"code"}`).
- All Phase B persistence under `~/.vector/` (traces, stats, templates); update the two
  `_DEFAULT_PATH`s (`strategy_stats.py:27`, `template_library.py:21`) which point at
  `~/.vector_os_nano/`.
- `vector-eval` defaults ask-level tools to auto-deny; `--allow` to auto-allow.
- Evidence-gated "verified" treats `verify ∈ {"", "True"}` as *not* evidence, **scoped to
  the dev world only** so robot async skills using `verify="True"` (`engine.py:573-585`)
  don't regress.

## Current-state findings (the four items are coded but unplugged)

- **Executor dispatch gap:** `GoalExecutor._execute_strategy` (`goal_executor.py:381-393`)
  handles only `{skill, primitive}`; `code` errors. `GoalExecutor.__init__`
  (`goal_executor.py:35-65`) has no `code_executor` / tool dispatcher — these are the
  injection points.
- **CodeExecutor is robot-shaped** (`code_executor.py`): AST-sandboxed, `math`-only
  imports, velocity-clamp on `set_velocity`; complete but never instantiated.
- **Dev sub-goals resolve to fallback** (`DEV_VOCAB` ships `strategies=frozenset()`,
  `worlds/dev.py:205-217`) → no execution.
- **Evidence gap:** `cli.py:1433-1455` reports success from `trace.success` alone; visual
  override can flip `verify_result` (`goal_executor.py:304-317`) and `verify="True"`
  passes trivially — no separate "deterministic evidence passed" gate.
- **Stats not persisted:** `engine.py:234` builds `StrategyStats()` (no path → in-memory).
  Full JSON persistence + corrupt-file handling already in `strategy_stats.py:162-210`.
- **Experience compiler unfed:** `GoalDecomposer` constructed without a `template_library`
  (`engine.py:251`) → the no-LLM template fast-path (`goal_decomposer.py:337-344`) is dead.
  `ExperienceCompiler.compile` (`experience_compiler.py:154`) + `TemplateLibrary` are
  complete and already preserve `verify`. Nothing collects traces.
- **Surprise:** templates serialize `strategy` but **not** `strategy_params`
  (`template_library.py:43-52`) — so tool/code payloads won't survive compile→reuse
  unless the (de)serializers are extended (B-4, step 17).

## Stages

### B.1.1 — Tool-backed + code execution branches (keystone)
1. New `cognitive/tool_dispatcher.py`: `ToolDispatcher` holds `ToolRegistry` +
   `PermissionContext` + `ToolContext` factory + allowlist + permission resolver;
   `dispatch(tool, args)` runs the full permission check then `tool.execute`.
2. `goal_executor.py`: extend `__init__` with `code_executor`/`tool_dispatcher` (default
   `None`); add `_execute_code` / `_execute_tool`; wire into `_execute_strategy`
   (`:381-393`) before the unknown fallthrough. `code` requires `params["code"]` →
   `CodeExecutor.execute` (AST-validated inside); `tool` requires `params["tool"]` +
   allowlist → permission check → dispatch.
3. `strategy_selector.py`: in `_resolve_explicit` (`:196-222`) add
   `tool_call → StrategyResult("tool", "tool_call", params)`.
4. `worlds/dev.py`: extend `DEV_VOCAB` with a `tool_call` strategy + params help + a
   `file_write` example sub-goal.
5. `engine.py init_vgg`: build a `CodeExecutor` (robot) + `ToolDispatcher` (registry +
   permissions + dev allowlist gated by `world.is_robot()`), pass both to `GoalExecutor`
   (`:316-323`). Preserve `agent=None` tolerance.
6. Tests `tests/harness/test_level63_code_tool_exec.py`.

### B.1.2 — Verify-as-eval + evidence-gated done
7. New `cognitive/trace_store.py`: `save_trace`/`load_trace` JSON round-trip for
   `ExecutionTrace` under `~/.vector/traces/`.
8. `replay(trace, verifier) -> bool` re-evaluates each `sub_goal.verify` (deterministic
   evidence vs "ran"/visual-override). Reuses `GoalVerifier`.
9. `cli.py _on_vgg_complete` (`:1433-1455`): only report success when
   `trace.success and evidence_passed` (dev-world strict rule); else "completed without
   verifiable evidence".
10. New `vcli/eval_runner.py` + `vector-eval` script (`pyproject.toml [project.scripts]`
    near line 115): run `{task, expect}` list headless over the dev world; per-case
    green/red; non-zero exit on any red; default auto-deny ask-tools, `--allow` opt-in.
11. Tests `tests/harness/test_level64_verify_as_eval.py`.

### B.2.1 — Persistent strategy stats
12. `engine.py:234`: `StrategyStats(persist_path=~/.vector/strategy_stats.json)`.
13. `strategy_stats.py save()`: atomic temp-file + `os.replace` (concurrent CLIs).
14. Tests `tests/harness/test_level65_stats_persistence.py`.

### B.2.2 — Experience compilation → template reuse
15. `engine.py`: accumulate successful `ExecutionTrace`s (bounded); on success
    `ExperienceCompiler().compile(...)` → `TemplateLibrary.add/save` to
    `~/.vector/goal_templates.json`. Cheap, never block/raise on the hot path.
16. `engine.py init_vgg`: build one `TemplateLibrary(persist_path=...)`, pass to
    `GoalDecomposer(..., template_library=lib)` (`:251`) → activates the no-LLM fast-path.
17. `template_library.py` + `experience_compiler.py`: carry `strategy_params` through
    (de)serialization + instantiation (schema version bump; loader skips unknown shapes).
18. Tests `tests/harness/test_level66_experience_reuse.py` (assert backend NOT called on
    a template hit).

## Success criteria

- B-1: a dev sub-goal (`tool_call` → `file_write`) actually mutates a tmp tree through the
  permission gate; deny blocks it; robot `code_as_policy` still runs; a `code` sub-goal
  calling `open(...)` is rejected by the AST validator.
- B-2: trace save/load/replay reproduces pass/fail; a `verify="True"`-only trace is NOT
  reported as verified; `vector-eval` returns correct green/red + exit code, no robot.
- B-3: record→save→reload round-trips; corrupt file degrades gracefully; atomic save.
- B-4: two dev traces compile to a template carrying verify + `strategy_params`; a matching
  task reuses it with the LLM backend asserted-not-called.
- Global: robot VGG harness (level45/46/54/56, mujoco e2e) + MCP tests stay green; new
  injections default `None` so the robot path is byte-identical when unused.

## Risks (see planner output for full register)

Generated-code/tool execution escaping the sandbox (mitigated by tool-backed + permissions
+ allowlist; `code` path AST-gated, no FS primitives); robot regression (all new params
default `None`); silent success on trivial predicates (evidence gate, dev-scoped);
persistence corruption/concurrency (atomic save, tolerant loaders); template payload loss
(extend serializers + schema version); scope creep (strictly the four items, B.1/B.2 split).

## Open questions for the owner (carried into next session)

1. Keystone: confirm **(a) tool-backed** for dev side effects (recommended).
2. Payload carrier: `SubGoal.strategy_params` dict (recommended) vs a new explicit
   `payload` field on `SubGoal`.
3. Persistence: standardize on `~/.vector/` (recommended) vs keep `~/.vector_os_nano/`.
4. PR split B.1 / B.2 (recommended yes).
5. `vector-eval` default: auto-deny + `--allow` (recommended) vs auto-allow.
6. Evidence semantics: `verify ∈ {"", "True"}` = not-verified, dev-world-scoped
   (recommended) vs global.
