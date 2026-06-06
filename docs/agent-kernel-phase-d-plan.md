# Verified Agent Kernel — Phase D Plan (closed-loop controller: grounding, control-flow, unification)

- Status: **Stage 3 (grounding) — next.** Stages 0-2 shipped to working tree (uncommitted; 628 tests green).
- Date: 2026-06-05; updated 2026-06-06
- Branch: `feat/verified-agent-kernel`
- Related: [ARCHITECTURE.md](ARCHITECTURE.md), [agent-kernel-STATUS.md](agent-kernel-STATUS.md),
  [agent-kernel-phase-c-plan.md](agent-kernel-phase-c-plan.md)

## Why this phase exists (the redirection)

Phase A–C made the kernel real and made the SO-101 arm controllable from `vector-cli` by
**single** natural-language commands (wave / home / scan / detect / describe / pick / place).
The owner then reframed the direction: the system was an open-loop "compiler" (plan once,
execute blind, discard observations); we are turning it into a **grounded closed-loop
controller**. Foundation-first; arm as the touchstone; GoalTree + verify kept but made
closed-loop and incremental.

Two concrete failures exposed the gap and drive this phase:

1. **Long-chain planning is broken for the arm.** `把所有东西抓一遍` decomposed into go2/base
   steps (`explore_area` via `scan_360`), a hallucinated skill (`look`), never producing the
   real chain (`scan → detect-all → for each object: pick → place`). It failed 0/2.
2. **Headless was the default; it shouldn't be.** "Start the arm sim" in plain `vector-cli`
   silently ran windowless. NL-first means a window by default; headless only on request.

This phase is now structured as **Stages 0–5**. Stages 0–2 are shipped to the working tree
(uncommitted). Stage 3 is next. The original D.1 / D.2 analysis is preserved below as the
root-cause record; see each stage's section for current status.

---

## Stage 0 (= D.1) — NL-first visible sim (macOS) — SHIPPED

**Status: shipped to working tree.**

**Root cause (preserved).** The MuJoCo passive viewer hard-raises unless the process runs under
`mjpython` (sets `_MJPYTHON`). `vector-cli` is a plain-python console script, so the in-process
`MuJoCoArm(gui=True)` viewer silently degraded to headless. The only working visible path was the
manual `scripts/vector-sim` wrapper.

**Decision taken: re-exec the whole CLI under mjpython on macOS** (driven by NL/flag, `--headless`
opt-out). Re-exec fixes the root in ~15 lines and every existing skill animates as-is.

**What shipped:**
- `cli.py` `main()` — re-exec guard at the very top (before credential/agent init): on macOS,
  if a window is wanted and not already under mjpython, `os.execv` into `.venv-nano/bin/mjpython`
  with the same argv. `VECTOR_REEXEC=1` env guard prevents loops. Falls back to headless + warning
  if mjpython is missing.
- Flags: opt-in `--gui` replaced with opt-out `--headless`; `_init_agent` calls
  `MuJoCoArm(gui=not args.headless)`.
- `sim_tool.py` `_start_arm`: default `gui=True`; `start_simulation` detects "no viewer possible"
  and re-execs into mjpython with `--sim` for the pure-NL case.
- `prompt.py`: model told arm sim opens a window by default; "headless"/"无窗口"/"no window" ->
  `gui=false` and suppress re-exec.
- `intent_router.py`: routes headless/无窗口/不要窗口/no-window -> `gui=false`.
- `scripts/vector-sim` kept as thin alias; now equivalent to `vector-cli --sim`.

**Acceptance verified:** plain `vector-cli` -> "start the arm sim" -> window opens; "wave" animates.
"start the arm sim headless" / `--headless` -> no window. mjpython-missing -> clear warning + headless.

---

## Stage 1 (close the loop) — SHIPPED

**Status: shipped to working tree.**

- `Blackboard` — per-run observation store with safe `${step.output.path}` param-binding refs
  resolved by pure dict/list traversal (no eval).
- `GoalVerifier.evaluate()` — returns `(bool, raw)` instead of bare bool; callers get the
  structured evidence.
- `StepRecord.result_data` — structured observation payload carried alongside success/verify/error.
- `VGGHarness` — rebuilds `world_context` on each (re)decompose so the replanner sees fresh state.

---

## Stage 2 (single-source the decompose vocab + fail-loud) — SHIPPED

**Status: shipped to working tree.**

- `vocab_from_registry.build_decompose_vocab` — derives planner intro, strategy descriptions,
  verify signatures, and examples from the live `SkillRegistry`. Kills the GO2 split-brain
  (validator allowlist and LLM prompt now share one source).
- Base primitives (walk_forward/turn/scan_360) gated on `has_base` — arm worlds no longer see them.
- `StrategySelector` — world-scoped; go2 keyword routes disabled for baseless worlds.
- `GoalTree.validation_notes` — dropped/unknown strategies fed back into replan context ("skill X
  does not exist; use one of {…}") so hallucinated skills stop repeating.

---

## Stage 3 (grounding) — NEXT

**Status: not started.** This is the primary remaining work.

**What grounding means.** Stages 0-2 give the arm a correct vocab and a closed observation loop.
Stage 3 makes those observations real: perception output flows into `world_context` so the
decomposer and verifier reason from actual scene state, not empty stubs.

**Work items:**
- Wire `detect_objects` / `describe_scene` to the real `MuJoCoPerception` / `DetectSkill` (currently
  returning `[]` / `""`). Bind into the arm verify namespace so correct plans also pass verify.
- Arm predicates: `holding_object()`, `arm_at_home()`, `placed_count()`. Wire into `engine.py` verify
  namespace alongside the perception functions.
- Referring-expression resolution: "pick up the red cup" -> `object_id` from the live object list;
  goal params resolved against the detected object set before execution.
- `ObjectMemory` re-sync from perception output after each detect step.

**Acceptance:** `pick up the mug` decomposes to only arm skills, executes, and `holding_object()`
verify returns True with real gripper state. `detect_objects()` in a verify predicate returns the
actual object list, not `[]`.

---

## D.2 — Arm-world VGG long-chain planning (root-cause record, preserved)

**Root cause (verified).** `RobotWorld.decompose_vocab()` returns `None`
(approximate anchor: `worlds/robot.py`, the `decompose_vocab` method), forcing the decomposer into
a **split-brain** state (approximate anchors: `goal_decomposer.py`, decompose/validate sections):
- the **validator allowlist** (`KNOWN_STRATEGIES`) is built from the live arm `SkillRegistry`
  (so it knows `pick`/`place`/`scan`/…), **but**
- the **prompt the LLM actually reads** falls back to the hardcoded **GO2 class defaults**
  (`_STRATEGY_DESCRIPTIONS`/`_EXAMPLE`/`_PLANNER_INTRO`) — navigate/look/explore/scan_360, the
  "去厨房" example. Not one arm skill appears in the prompt.

So the LLM plans with go2 skills (`scan_360`, `explore_skill`) and invents `look`. Compounding
defects: `KNOWN_STRATEGIES` unconditionally injects base primitives `walk_forward/turn/scan_360`;
`StrategySelector` keyword-routes go2 verbs + base primitives; base primitives call `_require_base()`
and raise "No hardware connected" on an arm; the goal model is a static DAG with no loop/foreach so
"for each detected object" is inexpressible; and the arm verify functions `detect_objects`/
`describe_scene` are unwired stubs returning `[]`/`""`.

(All file:line anchors in this record are approximate, not exact addresses — treat as search hints.)

**Target.** `把所有东西抓一遍` →
```
1 home          strategy=home_skill   verify=arm_at_home()
2 scan_workspace strategy=scan_skill   verify=True            depends_on=[1]
3 detect_all     strategy=detect_skill verify=len(detect_objects())>0  depends_on=[2]
--- dynamic loop, one iteration per detected object (N known only after step 3) ---
4.i pick_obj_i   strategy=pick_skill  {object_id:i}  verify=holding_object()
5.i place_obj_i  strategy=place_skill {target:bin}   verify=not holding_object()
```

**Original D.2 work items (P0/P1/P2) — disposition:**
- P0a (arm-scoped `decompose_vocab()` from registry) — **shipped** in Stage 2.
- P0b (gate base primitives on `has_base`) — **shipped** in Stage 2.
- P1b (wire arm verify namespace + arm predicates) — **target of Stage 3** (grounding).
- P1c (step data-flow / result_data) — **shipped** in Stage 1.
- P1a (foreach/iteration construct) — **target of Stage 4** (control-flow IR).
- P2a (fail-loud `StrategySelector`) — **shipped** in Stage 2.
- P2b (validator rejects hallucinations with feedback) — **shipped** in Stage 2.

**Acceptance (verify-as-eval, unchanged target).** A small NL eval set on the arm, single + long-chain:
`wave`, `go home`, `pick up the mug`, `把所有东西抓一遍`, `先回家再把桌子扫一遍`, `把红色的放到左边`.
Each must decompose to only arm skills (no go2/base, no hallucinated names), execute, and pass
per-step verify. Add as `tests/vcli/test_level72_arm_planning.py` (mock backend for determinism +
a marked live-LLM smoke).

---

## Stage 4 (control-flow IR + observation-driven replan)

**Status: not started.** Depends on Stage 3 (grounding must be real before dynamic loops are useful).

- Add `foreach`/`until`/`if` constructs to the goal model (`vcli/cognitive/types.py`, SubGoal shape).
- Executor expands a `foreach` at runtime from the producing step's `result_data` output (e.g.
  `detect_all` yields N object IDs -> N pick/place SubGoal pairs).
- Mid-tree replan triggered by live observation (not only failure string): if a step's `result_data`
  shows an unexpected state, `VGGHarness` reruns decompose with that context before continuing.

**Acceptance:** `把所有东西抓一遍` produces a dynamic tree whose leaf count equals the detected object
count, executes each pick/place, and passes per-step verify throughout.

---

## Stage 5 (unify the two planning paths)

**Status: not started.** Depends on Stages 3-4.

Merge the VGG path and the `tool_use` path into one closed-loop controller. The two paths currently
diverge at `run_turn`: VGG for "actions", tool_use for "conversation". Stage 5 makes VGG the unified
executor so observation-driven replanning applies to all interactions, not just explicitly "complex"
goals. Details TBD once Stages 3-4 are stable.

---

## Sequencing & relationship to Phase C

| Stage | Status | What it unlocks |
|---|---|---|
| 0 (NL-first visible sim) | SHIPPED | See the arm move; "wave" in a window |
| 1 (close the loop) | SHIPPED | Observations flow; verify returns evidence |
| 2 (single-source vocab + fail-loud) | SHIPPED | Correct arm-only plans; no hallucinated GO2 skills |
| 3 (grounding) | NEXT | Real perception in world_context; verify predicates are true |
| 4 (control-flow IR + obs-driven replan) | NOT STARTED | "抓一遍" expressible and executable |
| 5 (unify planning paths) | NOT STARTED | One closed-loop controller for all NL |

**C.3** (real specialized model in the robot world) **is blocked behind Stage 3**. C.3/C.4 decisions
stay open (see [agent-kernel-phase-c-plan.md](agent-kernel-phase-c-plan.md)).

## Key file map (approximate anchors — search hints, not exact addresses)

| Concern | File (approximate location) |
|---|---|
| Arm verify namespace (stubs) | `vcli/engine.py` — verify-namespace wiring section |
| Arm predicates (to add) | `vcli/engine.py` — alongside perception verify fns |
| Perception stubs to wire | `vcli/cognitive/types.py` — SubGoal / GoalTree shapes |
| Loop/foreach construct | `vcli/cognitive/types.py` — SubGoal shape; `vcli/cognitive/vgg_harness.py` — expand logic |
| Vocab source (now registry) | `vcli/cognitive/vocab_from_registry.py` |
| World-scoped strategy selector | `vcli/cognitive/strategy_selector.py` |
| Blackboard + param-binding | `vcli/cognitive/blackboard.py` |
| StepRecord.result_data | `vcli/cognitive/types.py` — StepRecord |
| VGGHarness world_context rebuild | `vcli/cognitive/vgg_harness.py` |
| NL-first window (shipped) | `vcli/cli.py` — re-exec guard near top of `main()`; `vcli/tools/sim_tool.py` |
