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

- **Live-hardening (this commit)** — fixes found by running the real CLI on deepseek-v4-flash:
  (1) arm VGG "unmatched" — `VGGHarness` cleared a step's explicit strategy on retry; on a baseless
  arm world the empty-strategy selector fell to the `fallback/unmatched` route, destroying the valid
  `scan_skill` and masking the real attempt-0 verify miss. Fixed with a `_retry_strategy()` selector
  probe that keeps a valid explicit strategy when clearing would resolve to fallback/invalid
  (world-agnostic; go2 path byte-identical; fail-loud preserved). (2) REPL WARNING log spam — the
  cognitive-package logger is raised to ERROR on the non-verbose REPL (`_setup_logging`; full logs
  under `--verbose`). Live-confirmed: "扫一眼看看" routes to scan_skill/describe_skill, no "unmatched",
  clean console. KNOWN residual (separate, Phase D grounding): the scan step may still fail on a
  verify miss (now surfaced HONESTLY, not masked); and a replan can still emit a hallucinated skill.

- **Live-hardening II (this commit)** — decompose robustness on deepseek-v4-flash:
  (A) META / non-actionable input ("我希望你去打开终端") answered instead of failing a VGG decompose —
  `intent_router` meta-request guard (gated on a residual-motor check so politely-phrased REAL motor
  commands like "请你巡逻" still plan). (B) decompose JSON robust for the reasoning model — budget raised
  to `DEFAULT_DECOMPOSE_MAX_TOKENS=8192`, balanced-brace extraction (fences/preamble/trailing prose), a
  bounded retry, then fail-loud to a single-step fallback (never a phantom plan). (C) hallucinated skills
  rejected LOUDLY on replan — `SubGoal.cleared_strategy` (additive marker) routes a cleared/unknown
  strategy to the `invalid` route with the valid set, never silently to `unmatched`. Live-confirmed:
  "我希望你去打开终端" -> answer-only `VGG [PASS] answer`. 938 green. Followups: remove dead
  `goal_decomposer._parse_and_validate`; meta guard is keyword-based (fails safe).

- **Live-hardening III (this commit)** — the MuJoCo viewer never opened ("mjpython not found —
  arm sim will run headless") even though mjpython IS installed at `.venv-nano/bin/mjpython`. Root
  cause: BOTH re-exec paths computed the venv path as `parents[N]`-from-`__file__`, off by one, so
  they looked in `$HOME` and never found mjpython. Fixed with a shared `locate_mjpython()` helper
  (vcli/tools/sim_tool.py) that derives mjpython from `sys.executable`'s dir (the venv bin/),
  depth-independent and NOT `resolve()`-d (resolving follows the venv symlink to the base
  interpreter's bin, where mjpython is absent). Both `cli._maybe_reexec_under_mjpython` and
  `SimStartTool._reexec_under_mjpython_with_sim` use it. 5 regression tests. Human visual check:
  `vector-cli --sim` (or NL "start the arm sim") in a real terminal should now open a MuJoCo window.

- **Live-hardening IV (this commit) — P0 segfault fixed.** "抓香蕉" segfaulted because
  `engine.vgg_execute_async` ran skills on a background `vgg-executor` thread that called
  `mj_step` + `viewer.sync()` on `mjData`/GLFW, racing the main-thread passive viewer
  (MuJoCo data + GLFW are not thread-safe; GLFW is main-thread-only on macOS). Fix: a
  world-agnostic `VectorEngine._has_live_viewer()` (duck-types the agent's `_arm`/`_base`
  for a live viewer) gates `vgg_execute_async` — when a viewer is live it runs
  `vgg_execute` SYNCHRONOUSLY on the caller's (viewer-owning) thread; the background-thread
  path is byte-identical for the headless/dev case. `KeyboardInterrupt` still propagates
  (the inner handler catches `Exception`, not `BaseException`). 3 regression tests
  (`tests/vcli/test_segfault_sync_exec.py`); 946 green. `vgg_execute_async` is the ONLY
  background sim access (the tool_use/ReAct path already runs sync on the main thread).
  HUMAN VISUAL CHECK still needed: "抓香蕉" in a real `--sim` terminal must no longer crash.

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

## Known live bugs — "grab a thing" fails (found 2026-06-08, real cli + deepseek + MuJoCo)

CONFIRMED WORKING: chat answers cleanly; the MuJoCo viewer now opens (mjpython re-exec fixed);
NL routes to real arm skills (go_home/detect/pick, no 'unmatched'). BUT "抓一个东西"/"抓香蕉"
fails end-to-end, and the CLI segfaulted. Priorities for the next pass:

- **P0 — SEGFAULT. [FIXED — Live-hardening IV, this commit].** Was: `vgg_execute_async`'s
  background thread stepped `mjData` + `viewer.sync()` while the main-thread viewer rendered
  (MuJoCo/GLFW not thread-safe). Fixed by running execution synchronously on the viewer-owning
  thread when a viewer is live (`_has_live_viewer()` gate). Needs the owner's live `--sim`
  visual confirmation that "抓香蕉" no longer crashes.
- **P0 — PERCEPTION/GROUNDING (why grab fails).** detect finds nothing ("No detections found",
  "Perception failed, falling back to world model", "Cannot locate target object") even though
  the MuJoCo scene HAS the objects. The robot arm world's detect uses the VLM path, which fails in
  sim. The PLAYGROUND already solved this with the DETERMINISTIC sim-oracle (`get_object_positions`).
  FIX = bring the playground's sim-oracle grounding into the plain robot arm world (this is the
  earlier design choice (a), now clearly correct — VLM is the wrong tool in sim).
- **P1 — VERIFY-SATISFIABILITY.** Every step fails verify even when the action physically succeeds:
  go_home fails `certainty()` (engine stub -> 0.0), detect fails `len(detect_objects())>0` (stub ->
  []). `engine._build_verifier_namespace` falls through to stubs in the plain arm world. Same root
  as P0-grounding.
- **P1 — VERIFY-FN CHOICE.** The decompose vocab picks `certainty()` for `home` (meaningless);
  should pick `arm_at_home()`/`holding_object()` etc. Wire the playground arm predicates as the
  robot-world verify namespace and teach the vocab to pick the right per-skill predicate.
- **P1 — LOG SPAM (skills).** The WF1 quieting only covered `vcli.cognitive`; `skills.pick`/
  `.calibration` still flood the REPL. Broaden to the `vector_os_nano` skill/perception loggers.
- **P2 — HARDCODED PATH.** `skills/calibration.py` warns about
  `/Users/yusenthebot/Desktop/vector_ws/config/workspace_calibration.yaml` (another machine's path).
  Give a sane default / skip calibration in sim (identity is fine for the sim-oracle).

UNIFYING FIX: bring the playground's deterministic sim-oracle grounding (ADR-008 C1) into the plain
robot arm world — closes P0-perception + P1-verify + P1-verify-fn together. P0-segfault is separate
(thread-safety) and goes first. Fixed-this-session (committed, verified): unmatched-retry, log spam
(vcli.cognitive only), meta-routing, decompose JSON robustness, replan validation, mjpython viewer.

## Next-session kickoff prompt (paste this to start)

> 继续 vector-os-nano(分支 `feat/verified-agent-kernel`;只动这个项目,不碰 UniLab)。当前模型
> deepseek-v4-flash(config 已设)。上个 session 修了一批 live bug 并提交(unmatched/日志/meta 路由/
> decompose JSON/replan 校验/mjpython viewer),但**真机最简单的"抓一个东西"还是做不到**,而且 CLI 段错误。
>
> 先读:`docs/agent-kernel-STATUS.md`(看"Known live bugs"那节)→ `docs/ARCHITECTURE.md` → 记忆
> `vector-os-nano-live-hardening`。然后按优先级解决,**每步用真 cli + deepseek + MuJoCo 窗口 live 验证、
> 多重审核、绿了再提交**:
> 1. **P0 段错误**:`vgg_execute_async` 后台线程访问 mjData + 主线程 viewer → MuJoCo 非线程安全 → segfault。先定位再修(把 mujoco 访问收敛到一个线程 / 加锁)。
> 2. **P0 抓取失败的根因**:机器人臂世界的 detect 走 VLM,在 sim 里检测不到场景里明明存在的物体。把 playground 已验证的**确定性 sim-oracle**(`get_object_positions`)接进机器人臂世界的 detect + verify 命名空间(ADR-008 C1 的做法推广到 robot world)。
> 3. **P1 verify 接地 + 选对谓词**(home→arm_at_home、pick→holding_object)、**P1 技能层日志降噪**、**P2 calibration 硬编码路径**。
> 4. 目标:`打开so101的sim` → `抓香蕉` 能**端到端成功**(每步 verify 真过),窗口里看得到机械臂抓起香蕉,控制台干净,不崩。
>
> 先复现+诊断 P0 段错误和抓取失败,跟我确认根因和方案,再动手。
