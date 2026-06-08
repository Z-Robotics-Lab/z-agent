# Verified Agent Kernel — STATUS (resume anchor)

One-page "where are we / what's next" for the agent-kernel line of work. Read this first
when resuming; the detailed plans are linked at the bottom.

- Branch: `feat/verified-agent-kernel`. Base: `master`. No PR yet.
- Last updated: 2026-06-06.
- Scope guard: this is **vector-os-nano only** — not the UniLab go2arm-grasp work.

## North star (restated 2026-06-05)

**Vector OS Nano = natural language controls everything**, via a built-in agent that
**decomposes NL → plans → executes long-chain tasks** (and verifies + re-plans). VGG
(Verified Goal Graph) is that engine. The system was an open-loop "compiler" (plan once,
execute blind, discard observations, keyword-match at every junction); we are turning it
into a **grounded closed-loop controller** — foundation-first, arm as the touchstone,
GoalTree + verify kept but made closed-loop/incremental.

Single-skill NL control works. Long-chain planning (e.g. "把所有东西抓一遍") does not yet.
See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the durable design.

## Shipped (on the branch)

Committed:
- **Phase A** — kernel/world decoupling; `vector-cli` boots robot-free on macOS.
- **Phase B.1/B.2** `80916f4`/`f5b9eb4` — dev world acts (tool_call via ToolDispatcher,
  code-as-policy sandbox, verify-as-eval, `vector-eval`), persistent StrategyStats +
  experience compilation. Hardening `8e961f8` (17 adversarial findings). e2e `bee46f7`.
- **Phase C.1/C.2** `62fcfc1`/`2a7c942` — capability seam (`Capability` + registry +
  `LLMChatCapability`; invoke-succeeds-but-verify-false => success=False) and cross-capability
  routing (measured-better promotion, no schema change).

Also committed + pushed (`aebd61e` arm + Stage 0, `cdbfada` Stages 1-2); 628 tests green (`tests/vcli tests/unit/vcli`):
- **Robot-arm control** — SO-101 MuJoCo arm controllable from `vector-cli` by single NL
  commands (wave/home/scan/detect/describe/pick/place). Arm-aware `RobotContextProvider`;
  `start_simulation` in always-enabled `sim` tool category + `sim` IntentRouter rule; VGG
  gate admits arm-only; perception word-boundary detect + `caption()`/`visual_query()`;
  `SkillWrapperTool` honors `__skill_auto_steps__` + motor detection; SimStart/Stop rebuild
  live `DynamicSystemPrompt` + registry `unregister()`/dedup; fixed critical
  `DynamicSystemPrompt.__init__` corruption (was overwriting tool-instructions block every
  turn). New: `scripts/vector-sim` launcher, `tests/vcli/test_level71_robot_control.py`.
- **Stage 0 (NL-first visible sim)** — `cli.py` re-exec guard: on macOS, when a window is
  wanted, re-execs the whole REPL under `mjpython` before credential/agent init; `--headless`
  is the new opt-out (replaces opt-in `--gui`). "Start the arm sim" opens a window by default.
- **Stage 1 (close the loop)** — `Blackboard` per-run observation store with safe
  `${step.output.path}` param-binding refs (pure dict/list traversal, no eval);
  `GoalVerifier.evaluate()` returns `(bool, raw)` instead of bare bool;
  `StepRecord.result_data` carries structured observation payload;
  `VGGHarness` rebuilds `world_context` on each (re)decompose.
- **Stage 2 (single-source the decompose vocab)** — `vocab_from_registry.build_decompose_vocab`
  derives the full vocab (planner intro, strategy descriptions, verify signatures, examples)
  from the live `SkillRegistry`, killing the GO2 split-brain; base primitives
  (walk_forward/turn/scan_360) gated on `has_base`; `StrategySelector` is world-scoped;
  `GoalTree.validation_notes` fed back into replan context ("skill X does not exist; use
  one of {…}") so hallucinated skills stop repeating.
- **Playground v1 (this commit)** — the playground track (ADR-008) + the shared seam-contract
  prelude. Prelude: `vcli/worlds/registry.py` (`resolve_world`->registry + named lookup); the engine
  MERGES `world.build_verify_namespace` additively (a world OWNS its predicates); `vcli/cognitive/
  observation.py` (JSON-safe verified-loop observation surface + CLI renderers). Track:
  `vector_os_nano/playground/` package — `PlaygroundWorld` + frozen `Scenario` + catalog (`tabletop`,
  `tabletop_tray` over `so101_mujoco.xml`) + 5 deterministic sim-oracle predicates
  (`holding_object`/`arm_at_home`/`placed_count`/`detect_objects`/`describe_scene`); `--scenario`
  flag + `/scenario` mid-session switch + banner; NL decompose proven arm-only (mock backend;
  go2/hallucinated strategies rejected via `validation_notes`); the verified loop (goal tree +
  per-step PASS/FAIL + replan) rendered in the live CLI. Sim-oracle is the deterministic verify
  source (ADR-008 C1); VLM `detect`/`describe` stays the agent's perception skill. 719 tests green
  + 1 marked live-LLM smoke; real headless `MuJoCoArm` oracle test passes in isolation.
- **Stage 4 (control-flow IR) + Go2 2nd embodiment (this commit)** — `ForEachSpec` + an additive
  `SubGoal.foreach` field (frozen-safe); `GoalDecomposer` parses/validates a `foreach` node (fail-loud
  on unknown source_step / body strategy); `GoalExecutor` EXPANDS it at runtime from a producing step's
  `result_data` via the Blackboard pure `${path}` traversal (per-item var binding, no eval); `VGGHarness`
  obs-driven mid-tree replan hook. Proven: "grab everything" -> scan -> detect_all -> foreach(obj):
  pick(obj)/place(obj), leaf count == detected count, every verify flips on real oracle state. **Go2**:
  quadruped scenario (`go2_room`, has_base) with sim-oracle base predicates (`at_position`/`facing`/
  `visited`) + go2-only NL decompose; arm scenarios unaffected. 777 green + 3 marked live smokes. Known
  follow-ups (next workflow): live decomposer prompt not yet taught the `foreach` JSON (mock-only on the
  live path); foreach reads a producing-step output, not the verify-namespace detect predicate (synthetic
  producer in tests); harness double-records foreach child stats; a `foreach` missing `depends_on` can
  silently iterate zero (auto-inject `source_step`).

Run the kernel tests: `cd ~/vector-os-nano && .venv-nano/bin/python -m pytest tests/vcli -q`.
Known pre-existing red: `tests/unit/test_mujoco_*.py` (cross-test MUJOCO_GL pollution; pass in
isolation). Pre-existing quirk: go2 sim load rewrites `mjcf/go2/scene_room_piper.xml` abs paths —
`git checkout` it before committing.

## Next — finish the live foreach path + harden, then Stage 5 (ADR-008 two tracks)

Full plan: **[agent-kernel-phase-d-plan.md](agent-kernel-phase-d-plan.md)**. Remaining stages:

- **Stage 3 (grounding)** — PARTIAL: arm predicates `holding_object()`/`arm_at_home()`/`placed_count()`
  and `detect_objects`/`describe_scene` are real via the **deterministic sim oracle** (shipped in
  Playground v1). Still open: the VLM `MuJoCoPerception`/`DetectSkill` perception path, referring-
  expression resolution ("the red cup" -> object_id), and `ObjectMemory` re-sync.
- **Stage 4 (control-flow IR + observation-driven replan)** — SHIPPED: additive `foreach` in the
  goal model; executor expands it at runtime from a producing step's output; obs-driven mid-tree
  replan hook. LIVE path now wired: the decomposer prompt teaches the `foreach` JSON (`_FOREACH_EXAMPLE`)
  so a real LLM can emit a loop; a real detect-producing step (`make_detect_producer` ->
  `{"objects":[...],"count":N}` captured to the Blackboard; `DETECT_STRATEGY="detect_objects_skill"`)
  replaces the synthetic primitive; harness no longer double-records foreach child stats; a `foreach`
  missing `depends_on` auto-injects its `source_step`. (`until`/`if` deferred.)
- **Stage 5 (unify the two planning paths)** — SHIPPED. **S5.0** observable `classify_intent` ->
  `IntentDecision`. **S5.1** ONE shared tool-dispatch seam (`vcli/tool_execution.py`). **S5.2** answer-only
  GoalTree shape (moat intact). **S5.3** `VectorEngine.run_turn_unified` — ONE closed-loop controller that
  produces a GoalTree for EVERY shape (answer-only chat / 1-step skill / N-step DAG), runs the harness loop
  through the shared dispatch seam, returns a `UnifiedTurnResult` (parity-tested). **S5.4** cut-over: both
  frontends (`cli.py` REPL + `mcp/`) call `run_turn_unified`, so every turn — chat included — is a verified
  trace; `should_use_vgg` is now a cheap routing HINT (incl. the conversational-question guard), not a fork
  in front of verify; `VECTOR_LEGACY_TURN=1` restores the old ReAct fork for one release. Live-confirmed:
  "hello"/"为什么这么慢" answer directly via an answer-only step (`VGG [PASS] answer`), real commands still
  plan+verify. Reasoning-model TUI (`vcli/turn_status.py`) cleaned up.

**Phase C.3** (real specialized model in the robot world) **is blocked behind Stage 3** — a
grounded arm decomposer is the prerequisite. C.3/C.4 decisions remain open
([agent-kernel-phase-c-plan.md](agent-kernel-phase-c-plan.md)).

**Direction (2026-06-06, ADR-008).** The shared seam-contract prelude AND playground v1 are shipped
(see "Playground v1" above; 719 green). Stage 3 grounding is satisfied for the arm via the
**deterministic sim oracle**; the VLM perception path + referring-expression + `ObjectMemory` re-sync
remain open. Work proceeds on two parallel tracks across the seam contract — see
[ARCHITECTURE.md](ARCHITECTURE.md) §5/§7 and
[ADR-008](architecture-decisions/ADR-008-playground-parallel-track.md).

**Shipped (on the branch):** playground v1, Stage 4 control-flow IR (`foreach` expand + obs-replan hook),
Go2 2nd embodiment, the live foreach path (prompt teaches the loop + real detect-producing step) + bug
fixes, an adversarial code-review pass, Go2 room geometry reconciled with the real `scene_room.xml`, and
the **Stage 5 scout** (`classify_intent` -> an inspectable `IntentDecision`, a behaviour-preserving pure
read of the routing gate). 803 green. **Stage 5 plan:** [agent-kernel-stage5-plan.md](agent-kernel-stage5-plan.md).
**Next (autonomous workflow):** execute Stage 5 seam-safe staging (route both paths through the unified
controller; drop the keyword intent gate) per that plan.

## Pointers

- Rules + read order: [../CLAUDE.md](../CLAUDE.md)
- Direction / design: [ARCHITECTURE.md](ARCHITECTURE.md)
- Next-session plan: [agent-kernel-phase-d-plan.md](agent-kernel-phase-d-plan.md)
- Phase C plan (C.1/C.2 shipped, C.3/C.4 open): [agent-kernel-phase-c-plan.md](agent-kernel-phase-c-plan.md)
- ADRs: [architecture-decisions/ADR-006-agent-kernel-world-plugin.md](architecture-decisions/ADR-006-agent-kernel-world-plugin.md),
  [architecture-decisions/ADR-007-closed-loop-controller.md](architecture-decisions/ADR-007-closed-loop-controller.md),
  [architecture-decisions/ADR-008-playground-parallel-track.md](architecture-decisions/ADR-008-playground-parallel-track.md)
- Superseded/historical docs (phase-b plan, vgg-design-spec, pick_top_down, sysnav, agent-kernel.md) live in git history — `git log --all -- <path>`. No working-tree archive.

## Next-session kickoff prompt (paste this to start)

> 继续 vector-os-nano(分支 `feat/verified-agent-kernel`;只动这个项目,不碰 UniLab go2arm-grasp)。
> 这个 session 的目标:**完全跟上进度、彻底理解项目**,然后等我给方向再动手。
>
> 按顺序读,边读边建立全貌:
> 1. `docs/agent-kernel-STATUS.md` — 当前在哪、已 ship 什么、下一步(resume 锚点)。
> 2. `docs/ARCHITECTURE.md` — 北极星与架构思想(NL 控制一切;闭环控制器;kernel/world seam)。
> 3. `docs/agent-kernel-phase-d-plan.md` — 下一阶段施工图(Stage 3 grounding 开始;0-2 已 ship)。
> 4. 需要时翻 `docs/agent-kernel-phase-c-plan.md`、`docs/cli-tool-system.md`、`docs/skill-protocol.md`。
>
> 读完用**你自己的话**跟我确认(展示理解,别复述目录):
> - 一句话:vector-os-nano 是什么、北极星是什么。
> - 现在能做什么 / 不能做什么(单技能 NL 控制 ✓;长链规划 ✗,根因是什么)。
> - Stage 0-2 分别解决了什么、还剩 Stage 3-5 解决什么。
> - 工作树里哪些改动未提交、测试状态(`git status` + `pytest tests/vcli`)。
> - 你建议 Stage 3 从哪个子任务开始,为什么。
>
> 先别写代码、别开 workflow。等我确认你的理解与方向后再开始。
