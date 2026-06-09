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

- **Live-hardening V (this commit) — P0/P1 grounding: RobotWorld now has real verify predicates.**
  The plain robot arm world (`RobotWorld`, used by the normal `--sim` grasp path) returned `{}` for
  `build_verify_namespace`, so the engine kept its stubs (`detect_objects -> []`, `certainty -> 0.0`)
  and EVERY verify failed. Fixed by single-sourcing the deterministic sim-oracle predicate factories
  into a new kernel module `vcli/worlds/arm_sim_oracle.py` (moved out of `playground/verify/`, which
  the kernel must not import per ADR-008; the two playground files are now thin re-export shims) and
  having `RobotWorld.build_verify_namespace(agent)` return the 5 arm/scene predicates
  (`detect_objects`/`describe_scene`/`holding_object`/`arm_at_home`/`placed_count`, `object_names=()`
  = all scene objects) WHENEVER a sim arm (`hasattr get_object_positions`) is connected; real hardware
  / no arm still returns `{}` (byte-identical). Because the decompose verify allowlist is derived from
  the verify namespace, the planner now also gains these as allowed verify predicates. 7 new tests
  (`tests/vcli/test_robot_world_grounding.py`, incl. an engine end-to-end proving the stub is REPLACED);
  playground suite still 95 green; 953 green total; ruff clean. NEXT (Step 3) makes the decompose
  actually USE them + bind the target object label so "抓香蕉" picks the banana.

- **Live-hardening VI (this commit) — Step 3: LLM-side grasp generalization.** The decompose
  emitted EMPTY `strategy_params` for a grasp step (the registry-derived examples filled only
  REQUIRED params; pick's `object_label` is optional → never demonstrated), so "抓香蕉" ran pick
  with no label → query degraded to the literal "object" → fail. Fix EQUIPS the LLM (the owner's
  principle: language understanding belongs in the LLM, not hardcoded keyword tables):
  (1) per-skill `verify_hint` declared on each arm skill (pick→`holding_object()`, home→
  `arm_at_home()`, detect→`len(detect_objects())>0`, place→`placed_count()>=1`, describe→
  `describe_scene()!=''`, else `True`) — single-sourced (the skill owns its success predicate),
  surfaced via `to_schemas()` into the decompose vocab as a per-strategy "suggested verify" line +
  used as the example's verify expr. (2) Planner-intro guidance (both `_DEFAULT_PLANNER_INTRO` and
  engine `_NEUTRAL_PLANNER_INTRO`, single-sourced via `_TARGET_BINDING_GUIDANCE`): copy a named
  target into the strategy's object/object_label/query/target param, and prefer the suggested verify.
  (3) `_build_examples` now shows an object-ish param BOUND (priority order: object_label > object >
  query > target > label > item; object_id excluded as a handle; string-typed only — fixes an
  over-match that bound a string into a float coord param). (4) pick reads the target from any of
  object_label/object/query/target/object_id (param-name flexibility, language-neutral). (5) detect/
  pick descriptions no longer forbid Chinese — natural-language targets in any language are accepted;
  NO bilingual keyword tables added anywhere. World-agnostic + single-source preserved. 960 green,
  ruff clean. VALIDATED live (real deepseek-v4-flash, headless grounded arm): 抓香蕉 / grab the bottle /
  拿起红色的杯子 / 把所有东西抓一遍 all decompose to detect -> pick with the target BOUND into object_label
  (香蕉/bottle/红色的杯子) + verify holding_object(); grab-everything emits foreach(object_label=${item.label}).
  REFINEMENT (same pass): the LLM first injected the target into the detect verify (detect_objects('香蕉')),
  which the language-neutral oracle (English names) can't match -> detect verify failed. Fixed by strengthening
  _TARGET_BINDING_GUIDANCE: use the suggested verify EXACTLY as written, target goes ONLY in strategy_params,
  never as an argument inside verify. Re-validated: detect verify is now the query-less len(detect_objects())>0
  (passes), every step verify satisfiable. (Headless PHYSICAL grasp now also works — see Live-hardening VII;
  only the owner's GUI window visual check remains.)

- **Live-hardening VII (this commit) — Step 4: sim grasp config + REPL polish. END-TO-END GRASP WORKS.**
  (1) PHYSICAL GRASP: pick added `z_offset=0.10` (10cm, real-rig tuning) to the object z before grasping,
  so in sim (exact coords) the gripper closed 10cm ABOVE the object — the skill reported success but
  `holding_object()` stayed False (verify-as-moat caught the fake success). Fixed with a single-sourced
  `SIM_PICK_CONFIG = {"hardware_offsets": False, "z_offset": 0.0}` (skills/pick.py) used at all 3 sim
  agent constructors (cli.py, sim_tool.py, mcp/server.py); `_DEFAULT_Z_OFFSET=0.10` kept for real hardware.
  VALIDATED headless: ALL 6 objects (banana/mug/bottle/screwdriver/duck/lego) grasp + lift to z~0.26,
  `holding_object()=True`. New real grasp regression `tests/vcli/test_sim_grasp_e2e.py`. (2) LOG SPAM: the
  REPL non-verbose quieting now covers `vector_os_nano.{skills,perception,hardware}` (not just cognitive)
  via a single `_QUIET_LOGGERS` tuple. (3) CALIBRATION: removed the hardcoded `~/Desktop/vector_ws/...` path;
  resolution is now arg > `VECTOR_CALIB_FILE` env > identity, and absent calib logs at DEBUG (was a WARNING
  flood). 969 green + new calibration tests. THE FULL CHAIN now works headless end-to-end: NL (中/英) ->
  decompose binds target -> detect verify passes -> pick physically grasps -> holding_object() True.

- **Phase E W1.1 (this commit) — learning-tier evidence gate. MOAT.** First commit of **Phase E**
  (dimos-informed hardening; plan `docs/agent-kernel-phase-e-plan.md`, Wave 1 = moat hardening). Closes the
  one moat leak the dimos comparison surfaced: the LEARNING tier trained on raw `step.success`, so a VLM
  `visual_override` or a sentinel `verify="True"` "success" could train the strategy bandit AND compile into
  a "verified" reusable template. Now the per-step bandit reward and template compilation are gated on the
  SAME deterministic evidence the engine uses for its per-trace `verified` flag. New
  `trace_store.step_evidence_ok` (per-step analogue of `evidence_passed`; mirrors its inner clause +
  `is_robot` leniency). Reward = `step.success AND step_evidence_ok(...)` — robot world collapses to
  `step.success` (robot learning BYTE-IDENTICAL, not starved); dev/playground additionally require real
  evidence. SINGLE chokepoint `GoalExecutor._record_strategy_stats` through which all 3 former record sites
  route (execute fallback, foreach [reads the per-iteration `child`, the verify carrier], harness non-foreach);
  the harness no longer owns the gate. `engine._maybe_compile_experience` also requires `_evidence_ok(trace)`.
  Adversarial review caught + this commit closes two gaps the green suite hid: (a) foreach/fallback bandit
  sites bypassed the gate; (b) `mcp/server.py` called `init_vgg` without `world=` → `is_robot=False` on a live
  robot entry point → now passes `world=resolve_world(agent)` (also fixes a pre-existing `_evidence_ok`
  is_robot inconsistency on the MCP path). 1050 green (+ foreach-bypass / robot-collapse / MCP-world
  regression tests). NEXT: W1.2 fail-loud world-registration preflight validator.

- **Phase E W1.2 (this commit) — fail-loud world-registration preflight validator.** `init_vgg` now calls
  `engine._preflight_validate_world(vocab, selector, verify_ns, world_name, has_base)` after the
  vocab/selector/verify-namespace are built (before the harness is wired). It asserts every taught strategy
  resolves to a real route (registered skill / capability / base-primitive-if-`has_base` / always-valid
  built-in) and every taught verify-function has a provider in the verify namespace — raising a MULTI-LINE
  actionable error (offending names + valid set) so registration drift fails at BOOT, not as an opaque
  mid-plan step failure (strengthens rule 8 / fail-loud). SCOPE GUARD (no false positives): an undeterminable
  registry (`_registered_skill_names()` None) WARNS not raises; convention-routed (non-`_skill`) strategies are
  skipped (they never route to `invalid` at runtime); a verify-fn whose signature is marked opt-in /
  "may be disabled" (e.g. dev's `tests_pass`) is documented-lazy (DEBUG, not drift). All 3 real worlds
  (dev/robot/playground) boot silently; additive (+156/-0, engine.py only). 12 tests
  `tests/vcli/test_w12_preflight_validator.py`; 1067 green. KNOWN LIMITATION (follow-up): the CLI wraps
  `init_vgg` in `try/except Exception: pass` (`cli.py`, the concurrent GUI session's file), so at the live CLI
  a drift surfaces as "VGG disabled" rather than the loud error; it DOES fail loud at the engine boundary +
  MCP/eval + tests. The opt-in signature-string guard could later be made declarative. NEXT: W1.3
  scene_graph -> TextLLM adapter.

- **Phase E W1.3 (this commit) — scene_graph spatial call behind a TextLLM adapter (core/ provider leak
  removed).** `core/scene_graph.py:rank_rooms_for_goal` inlined a raw httpx POST with a HARDCODED
  `openai/gpt-4o` + openrouter URL and read the PRIVATE `vlm._api_key` — an adapter break + provider leak in
  `core/`. Replaced with a narrow injectable `TextLLM` Protocol (one method `complete_text(prompt) -> str`,
  defined IN `core/` so `core/` never imports `vcli`); `rank_rooms_for_goal(goal, text_llm)` now calls
  `text_llm.complete_text`, with the prompt + json.loads/regex-fallback parsing + graceful `[]` preserved
  byte-identical. Default adapter `BackendTextLLM` (new `vcli/backends/text_llm_adapter.py`) wraps
  `create_backend` (configured provider, DeepSeek default), never reads a private attr or hardcodes a model.
  Path is now offline-mockable: harness tests inject a fake TextLLM (no httpx patching). Method-param injection
  chosen because SceneGraph's ctor + its `cli.py`/`sim_tool.py` construction sites are the concurrent session's
  (kept byte-identical). NOTE: `rank_rooms_for_goal` has no live caller yet (latent go2-nav path), so
  `BackendTextLLM` has no live wiring — the deliverable is the decoupling + mockability. 57 harness + 1074
  canonical green. NEXT: W1.4 playground build_step_primitives wire-into-live (or delete) — last Wave 1 item.

- **Phase E W1.4 (this commit) — playground step-primitives wired live; WAVE 1 COMPLETE.** (Owner: WIRE.)
  `playground.build_step_primitives(agent)` — the per-step PRODUCER dict the tabletop/foreach tests exercise —
  was tested-but-dead (the live executor never called it). Now `init_vgg` injects it into the GoalExecutor
  `primitives=` slot (defensive: a world without the method / any failure -> None -> byte-identical importlib
  path). A genuine ROUTING gap surfaced beyond a one-line wire: the producer strategy names end in `_skill`, so
  the live StrategySelector routes them to `skill`/`invalid` (and the `invalid` route DROPS strategy_params) —
  never to `primitive`, so the slot was never consulted live. Fixed with a pre-selector intercept
  `GoalExecutor._world_primitive_strategy`: when a sub-goal's explicit `*_skill` strategy is a key in the
  injected producer dict, dispatch it DIRECTLY as a `primitive` StrategyResult preserving the real
  strategy_params (so the `${obj.name}` foreach binding survives). Tightly gated (dict primitives only,
  producer-only `*_skill` keys; PlaygroundWorld's `detect_objects_skill`/`locate_rooms_skill` don't collide
  with real skill strategy names like `detect_skill`); inert when `_primitives` is None (dev/robot
  byte-identical); the producer can't self-certify (verify stays sim-oracle deterministic). 3 live-wiring tests
  prove the WORLD producer runs (not the importlib fallback) + a real detect->foreach(pick,place) drives
  leaf==produced==6 with each verify flipping on real oracle state. 1081 green. FOLLOW-UPS: the intercept's
  architectural home is `strategy_selector.py` (mirroring `_capability_names`) — done executor-side because
  strategy_selector.py was outside this loop's allowed files; could additionally exclude registered-skill names
  for defense-in-depth. **WAVE 1 (moat hardening) COMPLETE: W1.1 evidence-reward `85d59a2` + W1.2 preflight
  `7afe2c0` + W1.3 TextLLM adapter `c3103ad` + W1.4 live primitives (this).** NEXT: owner picks Wave 2
  (operability: W2.1 daemon+run-registry+status/stop/log, W2.2 RUN_ID watchdog orphan sweep, W2.3 ObjectMemory
  re-query-freshest, W2.4 typed failure_class into replan) — see `docs/agent-kernel-phase-e-plan.md`.

- **Phase E W2.4 (this commit) — typed `failure_class` into the replan context. Wave 2 started.** Replan could
  only see a stringified error. Now each FAILED `StepRecord` carries a DETERMINISTIC typed `failure_class` (a
  closed set: `timeout` / `verify_fail` / `ik_fail` / `tool_error` / `exec_error`; `""` for success), derived
  ONLY from already-available evidence (timeout-vs-verify-miss-vs-exec, the step's machine-readable
  `diagnosis`, executor_type) with NO new model call. Classified at every executor failure site (timeout gate
  first; selector-raise -> exec_error; exec-fail -> `classify_exec_failure(executor_type, diagnosis)`
  most-specific-wins; verify-miss -> verify_fail). Threaded onto `FailureRecord` (additive last field) and into
  the re-decompose context the decomposer sees: each failure line gets a `[failure_class]` tag + a per-class
  adaptation hint block, so the LLM re-plan adapts to the typed signal (selector unchanged — deterministic
  typed signal, LLM reasons over it, matching the architecture). `StepRecord.failure_class` is the additive
  LAST field (defaulted `""`, rule 6; trace replay round-trips; not serialized, same as `result_data`). 17
  tests `tests/vcli/cognitive/test_failure_class.py`; 1104 green. FOLLOW-UPS (non-blocking): annotate the field
  as `Literal[FailureClass]`; optional per-skill timeout table. NEXT: W2.3 ObjectMemory re-query-freshest.

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
- **P0 — PERCEPTION/GROUNDING. [PARTLY FIXED — Live-hardening V, this commit].** Correction to the
  original hypothesis: the CLI arm path ALREADY wires the deterministic `MuJoCoPerception` oracle
  (not the VLM), so `detect("banana")` works. The live "No detections found for 'object'" was caused
  by the decompose emitting an EMPTY `strategy_params` for the pick step → the query degraded to the
  literal default "object" (which the oracle correctly doesn't match). The grounding half (verify
  predicates) is now FIXED (RobotWorld contributes the sim-oracle predicates). The binding half —
  the decompose must extract the target entity and bind it to the pick param — is FIXED IN CODE
  (Live-hardening VI), PENDING the live real-deepseek confirmation that the LLM binds it.
- **P1 — VERIFY-SATISFIABILITY. [FIXED — Live-hardening V, this commit].** `RobotWorld` now
  contributes real `detect_objects`/`describe_scene`/`holding_object`/`arm_at_home`/`placed_count`
  (sim oracle), so verify can pass for a sim arm. `certainty()` is still a stub — Step 3 steers the
  per-skill verify choice away from it (home -> `arm_at_home()`, pick -> `holding_object()`).
- **P1 — VERIFY-FN CHOICE.** The decompose vocab picks `certainty()` for `home` (meaningless);
  should pick `arm_at_home()`/`holding_object()` etc. Wire the playground arm predicates as the
  robot-world verify namespace and teach the vocab to pick the right per-skill predicate.
- **P1 — LOG SPAM (skills). [FIXED — Live-hardening VII].** REPL non-verbose quieting now covers
  `vector_os_nano.{skills,perception,hardware}` via a single `_QUIET_LOGGERS` tuple.
- **P2 — HARDCODED PATH. [FIXED — Live-hardening VII].** `skills/calibration.py` no longer hardcodes
  the `~/Desktop/vector_ws/...` path; resolution is arg > `VECTOR_CALIB_FILE` env > identity, and an
  absent calib file logs at DEBUG (was a WARNING flood). Identity is correct for the sim oracle.

UNIFYING FIX: bring the playground's deterministic sim-oracle grounding (ADR-008 C1) into the plain
robot arm world — closes P0-perception + P1-verify + P1-verify-fn together. P0-segfault is separate
(thread-safety) and goes first. Fixed-this-session (committed, verified): unmatched-retry, log spam
(vcli.cognitive only), meta-routing, decompose JSON robustness, replan validation, mjpython viewer.

ROUND 1 STATUS: ALL FIXED + committed (118f886 segfault, 75cbdba grounding, 4a2edf7 decompose binding,
f53bd04 verify target-free, c953d72 z_offset grasp). Headless end-to-end works; real deepseek bilingual
decompose validated.

## Known live bugs — ROUND 2 (found 2026-06-08, real GUI run: mjpython window + deepseek)

The arm sim now opens a window and "抓香蕉" decomposes correctly. But a live GUI session surfaced issues
that ONLY reproduce under the real mjpython window / real-time sim (headless tests cannot catch them — the
owner must run the window; reason carefully + hand the visual/timing checks to the owner). NORTH STAR
REMINDER: the end goal is a generalizable PHYSICAL robot agent — every fix must GENERALIZE across embodiments
(arm AND go2 AND future), never an arm-only/banana-only patch. Backlog (rough priority):

- **R2-1 — Go2 sim opens HEADLESS while the arm opens one.** [IN-PROCESS macOS PATH IMPLEMENTED (Stage 1+2),
  headless-green — OWNER WINDOW CHECK PENDING (2026-06-09)]. OWNER DECISION (2026-06-09): target = in-process
  `--sim-go2` on macOS (like the arm), NOT the Linux `launch_explore.sh` nav stack. Run modes were first
  distinguished at a high level (owner ask): mode A arm `--sim`; B go2 in-process `--sim-go2` (+ optional ROS2
  stack); C go2 + full explore/TARE stack via `launch_explore.sh` (Linux only); D headless — ALL must keep
  working across mac/win/linux. SHIPPED THIS SESSION (headless-verified, NOT visually confirmed): a
  **platform-aware run-mode seam** `hardware/sim/viewer_mode.py` (`resolve_viewer_drive_mode` ->
  `main_thread_pump` for macOS/mjpython | `background_daemon` for Linux/Windows window | `headless`; trigger =
  `mujoco.viewer._MJPYTHON` present, not bare `sys.platform`), and `MuJoCoGo2` made viewer-thread-safe: the
  per-iteration physics bodies were extracted (`_physics_step_sinusoidal`/`_physics_step_mpc`, state lifted to
  `self`), a public main-thread `step()` pump + `_drive_for()` added (`walk()` pumps `step()` on the
  caller/main thread in pump mode instead of `time.sleep`, so the gait animates + the viewer syncs on the main
  thread), the background `_physics_thread` is GATED OFF only in `main_thread_pump` mode, and
  `_resume_physics`/`_pd_interpolate` no longer restart a daemon in pump mode. **Linux/Windows/headless are
  BYTE-IDENTICAL** (daemon path unchanged) — go2+nav (modes B/C) preserved per owner ask. Half A (mjpython) is
  ALREADY done for the in-process path (`cli._maybe_reexec_under_mjpython`, `_wants_window` covers `--sim-go2`);
  the engine `_has_live_viewer` gate already runs go2 skill exec synchronously on the main thread, so `walk()`
  pumps on main. Tests: `tests/unit/vcli/test_viewer_mode.py` (resolver, canonical) +
  `tests/unit/test_go2_viewer_pump.py` (daemon gating, pump syncs on caller thread, walk pumps, resume no-daemon).
  Canonical `tests/vcli tests/unit/vcli` 1050 green. **OWNER WINDOW CHECK STILL NEEDED** (cannot be verified
  headless): run `vector-cli --sim-go2` on macOS → window opens, NO segfault, the dog stands then animates a
  walk command in real time (frozen-when-idle is expected arm-parity v1; a background-input pump for live idle
  rendering is a later follow-up). ROOT CAUSE (for ref): `MuJoCoGo2.connect` always started a daemon
  `_physics_thread` (mujoco_go2.py ~511) that called `viewer.sync()` off-main = the cross-thread GLFW hazard
  the arm segfault fix (118f886) addressed; the in-process `--sim-go2` path (cli.py ~521) hit it on macOS.
  R2-6 is NOT subsumed (see below). DEFERRED: the Linux `launch_explore.sh` bridge-under-mjpython re-exec
  (mode C is Linux-only, owner runs nav there) + a background-input-thread pump for live idle-window rendering.
- **R2-2 — Grasp TIMES OUT under the real-time GUI. [FIXED — /loop iter 1].** Was: a completed pick (22.7s
  real-time under the viewer) was falsely marked timeout (foreach-body limit 15s) → bad replan. Fixed with
  skill-declared `typical_duration_sec` (single-source) + a GoalExecutor floor: effective timeout =
  `max(sub_goal.timeout_sec, skill.typical_duration_sec)`, so a completed motor action is never falsely failed
  even if the LLM under-estimates. World-agnostic (generic getattr, no executor-side skill map); arm
  pick/place/home/scan/wave/handover + go2 walk/turn/patrol/explore all declare durations; `_FOREACH_EXAMPLE`
  body 15→45. 26 new tests (both floored-pass + control-timeout); 995 green. OWNER WINDOW CHECK: confirm the
  real-time grasp now completes without a false timeout.
- **R2-3 — "抓个东西" (singular) grabbed EVERY object via foreach. [FIXED — /loop iter 2].** Two parts:
  (A) LLM intent — decomposer guidance teaches singular ("a/one/something/一个/个/随便") -> a SINGLE action step
  (no foreach), plural ("all/every/每个/所有/一遍") -> foreach over the detected list (prompt text = LLM layer,
  world-agnostic). (B) language-neutral skill fallback — an UNBOUND pick (object_label/object/query/target/
  object_id all empty) grabs the NEAREST object (min xy-dist), gated on a sim arm (`hasattr get_object_positions`);
  real hardware unchanged; NO keyword tables. Validated live (real deepseek-v4-flash): 抓个东西 -> 1 pick step,
  empty params -> nearest; 抓香蕉 -> detect+pick(object_label=香蕉); 把所有东西抓一遍 -> foreach (regressions OK).
  9 + 3 new tests; 1007 green.
- **R2-4 — Ctrl-C does not exit cleanly under mjpython. [FIXED IN CODE 2026-06-09 — OWNER WINDOW CHECK PENDING].**
  Owner had to ^C^C then type `quit`. ROOT CAUSE (hypothesis): mjpython drives a Cocoa main loop and leaves
  SIGINT bound to its own handler, so a single ^C is swallowed and never raises KeyboardInterrupt in the REPL
  (the turn-level handler at cli.py never fires). FIX: (1) `_ensure_sigint_under_mjpython()` re-installs
  `signal.default_int_handler` under mjpython (reuses `viewer_mode.running_under_mjpython`), so one ^C raises
  KeyboardInterrupt -> aborts the running task -> returns to the prompt; (2) the stated UX is now explicit — a
  single ^C during a task arms a pending-exit and a second consecutive ^C (or `quit`/Ctrl-D) exits cleanly
  (`interrupt_pending` flag, reset on any input). Headless test `tests/unit/vcli/test_cli_sigint.py` (handler
  restored under mjpython, untouched off it). OWNER WINDOW CHECK STILL NEEDED (cannot verify the real mjpython
  signal path headless): in `vector-cli --sim-go2`, start a task, ^C once -> it aborts to the prompt; ^C again
  -> exits. If a single ^C still does nothing, report the exact behavior (the SIGINT may be deferred inside a
  blocking GLFW call — a cooperative interrupt check in the pump would be the next step). NOTE: cli.py carries
  32 pre-existing ruff errors (lint debt unrelated to this change — my edits add zero); a separate chore.
- **R2-5 — Permission prompt blocks mid-task in sim. [FIXED — /loop iter 3].** "自己想个任务做" ->
  "Allow scan? [y/n/a]" hung. Fixed: `SkillWrapperTool.check_permissions` auto-allows MOTOR skills when the
  connected robot is SIMULATED (a sim action has no real-world consequence). Sim detected world-agnostically
  by the hardware module package (`vector_os_nano.hardware.sim`, precise package match) across the agent's
  arm/base/gripper. SAFETY: ALL-semantics — ANY real (non-sim) component keeps the confirmation gate (a mixed
  sim-arm+real-base agent still asks), so a real actuator is never auto-allowed; read-only skills unchanged;
  scoped to skills (bash/file/outward tools + the deny rail untouched). The VGG/executor path does NOT gate
  skill permissions separately (only dev-world tool sub-goals), so one fix covers both paths. 17 tests
  (incl. mixed-hardware safety); 1024 green. (Adversarial review caught + fixed an ANY-vs-ALL safety bug
  before commit.) NOTE: the mjpython prompt-input rendering hang for OTHER (non-skill) prompts is separate
  and owner-window-only.
- **R2-6 — ROS2-proxy ERROR bleed into the rich panels. [FIXED 2026-06-09, headless test].** `ERROR:...
  go2_ros2_proxy` / `sim_tool` lines interleaved with the live boxes. The `launch_explore.sh` subprocess stderr
  is already redirected to `/tmp/vector_vnav.log` (NOT the bleed); the real bleed was IN-PROCESS logger calls
  logging an EXPECTED condition at ERROR: on a macOS/Windows sim host `rclpy` is absent, so
  `Go2ROS2Proxy.connect()` (go2_ros2_proxy.py:177) and the piper proxy setup (sim_tool.py:490) hit
  `ModuleNotFoundError('rclpy')` and logged `logger.error(...)` — and `_QUIET_LOGGERS` only pins those packages
  to ERROR, so ERROR-level lines still emit. ROOT FIX: an unavailable ROS2 is NOT an error — both sites now
  catch `ImportError` separately and `logger.debug(...)` (quiet in the non-verbose REPL, visible under
  --verbose); real (non-import) failures still log ERROR. Test `tests/unit/vcli/test_ros2_proxy_logging.py`
  (rclpy-absent connect logs DEBUG, no ERROR). Also removed 2 pre-existing dead imports in sim_tool.py. NOT
  owner-gated (the ERROR-vs-DEBUG level is headless-tested; the in-window visual is the owner's). NOTE (deeper,
  separate): `logging.basicConfig` captures the original stderr, so a genuinely-ERROR log during a turn can
  still bypass the turn's `sys.stderr->devnull` mute — out of scope here (no expected-noise source remains).
- **R2-7 — capability: generalization + longer chains. [PARTIAL — /loop iter 4: grab-everything long chain
  now works end-to-end].** Found + fixed a producer/consumer contract bug that broke the grab-everything long
  chain: a "grab everything" plan decomposes to detect -> foreach(pick ${item.name}), but the robot-world
  `DetectSkill` produced objects keyed by `label` only (the foreach example + the playground producer use
  `name`), so `${item.name}` didn't resolve -> pick "Cannot locate target object" on the first item ->
  whole chain failed. Fix: DetectSkill now exposes BOTH `name` and `label` (robust to whichever field the
  planner emits). Validated live (real deepseek-v4-flash, headless): "把所有东西抓一遍" executes end-to-end —
  detect + 6 foreach picks ALL PASS, trace success=True. Deterministic regression test
  (`tests/vcli/test_detect_foreach_contract.py`); 1026 green. STILL OPEN under R2-7: observation-driven
  replan robustness, embodiment asymmetry, richer skills/evals.
  **[/loop iter 5: manipulation chains validated + place verify grounded].** Executed more multi-step
  chains end-to-end live (real deepseek, headless): 把香蕉放到左边 (detect->pick(hold)->place), 拿起香蕉递给我
  (pick->handover), 把所有东西都放到左边 (detect->foreach(pick+place ×6)) — ALL succeed, every step PASS. No
  functional bug — the R2-2/R2-3/R2-7 fixes made manipulation robust across task shapes. BUT found a verify-
  moat weakness: `place` declared `verify_hint = "placed_count() >= 1"`, which is trivially true in a
  region-less robot world (all resting objects count) — it verified nothing. Fixed to `not holding_object()`
  (grounded: a place RELEASES the held object; empirically holding flips True->False across pick(hold)->place),
  which discriminates a real place from a failed one. New pick->place regression test
  (`tests/vcli/test_pick_place_chain.py`); 1027 green.
  **[/loop iter 6: pick fails fast on an absent target].** Probed failure recovery by executing "抓起苹果"
  (no apple in scene): the robot correctly FAILS (success=False — moat held, no fake success), but it burned
  ~28s exhausting pick retries (re-home + re-detect the same miss each attempt). Fix: pick now breaks out
  immediately on a target-not-found diagnosis (`object_not_found` / `no_detections`) — retrying can't conjure
  an absent object; transient failures (ik/move/track) still retry. Absent-target pick now fails in ~0.06s
  (1 attempt vs max_retries). New regression test (`tests/vcli/test_pick_fail_fast.py`); 1029 green. KNOWN
  RESIDUAL (deeper, deferred): a detect step's query-less verify (`len(detect_objects()) > 0`) FALSE-PASSES
  when the specific target is absent (it counts other scene objects) — the verify can't match the user's
  CN/descriptive query against the oracle's EN ground-truth names without aliases (which the language
  principle forbids); a real fix verifies against the detect STEP's own alias-aware output (Rule 4:
  close-the-loop) rather than a separate oracle call.
  **[/loop iter 7: lint hygiene + cadence note].** Cleared the recurring dead-code in `skills/` (9 unused
  `Skill`/etc. imports + a dead `y_scale` local) so future ruff signal is clean; 1029 green, no behavior
  change. STATUS: the ARM touchstone is now thoroughly hardened end-to-end (perception, grounding, decompose
  binding, real-time timeouts, singular/plural intent, long chains, place/handover, honest+fast failure,
  grounded verify). Diminishing returns on solo-verifiable arm work — the remaining high-value items are
  OWNER-GATED and need a live `--sim` window: R2-1 go2 viewer (generalize mjpython launch + go2 physics-thread
  viewer safety), R2-4 Ctrl-C under mjpython, R2-6 ROS2 ERROR bleed. The deeper R2-7 detect-verify
  close-the-loop is a design call worth doing with owner input. Cadence lengthened; loop keeps a slow heartbeat.
  **[/loop iter 9: detect-honest-success — verify moat hole closed].** DONE: DetectSkill now returns
  success=False when a SPECIFIC query finds nothing (target absent), while a GENERIC "all objects"-type query
  stays success-with-empty (grab-everything foreach still no-ops cleanly). Reuses the existing generic-term
  set (lifted to `_GENERIC_QUERIES`; no new keyword table). Closes the hole where a detect step PASSED having
  found nothing for a specific target. Matrix verified + tests (renamed `test_detect_specific_target_not_found
  _returns_failure` + new generic-empty test); 1029 green; ruff clean.
  **NEW HIGH-PRIORITY FINDING (top R2-7 next target, needs careful design / owner input):** live "抓起苹果"
  (apple absent) is STOCHASTIC — when the LLM binds `object_label='苹果'`, pick fails fast + honest (correct);
  when the LLM emits an UNBOUND pick, R2-3's unbound->nearest grabs the NEAREST object and pick's
  `holding_object()` verify passes -> **FALSE SUCCESS** (grabbed a non-apple, reported done). Root tension:
  unbound->nearest is load-bearing for genuine generic grabs ("抓个东西") but masks a binding failure for a
  named-but-unbound target; and `holding_object()` checks "holding SOMETHING", not "holding the REQUESTED
  target". Design options (pick one with owner input): (a) make holding_object TARGET-AWARE
  (`holding_object('banana')` checks that specific object at the EE) + have pick verify against the bound
  target; (b) disambiguate generic-intent vs binding-failure at decompose (explicit "any" marker for generic
  grabs; a named target MUST bind or the step fails, never silently nearest); (c) strengthen entity-binding
  reliability so a named target is always bound. (a)+(b) together is the principled fix. Do NOT just remove
  unbound->nearest — it breaks "抓个东西".
  **[2026-06-09: owner picked (a) then (b). (a) SHIPPED]** `holding_object(target=None)` is now TARGET-AWARE
  (`arm_sim_oracle.make_holding_object`): given a scene name/id it only counts THAT object (case-insensitive
  structural match, language-neutral — caller passes a resolved scene name, never a raw NL query); `target=None`
  preserves "holding anything" so every existing caller (place's `not holding_object()`, the playground/robot
  predicates, ~15 tests) is byte-identical. `pick` now records `result_data["picked_object"]` (the resolved
  label/id it grabbed) so a verify can close the loop. Test `tests/vcli/test_holding_object_target_aware.py`
  (held banana verifies holding_object('banana') True / holding_object('apple') False; no-target unchanged).
  Backward-compatible building block — NO behavior change yet. NEXT (b): decompose disambiguates generic ("any"/
  "抓个东西" -> nearest OK) vs a NAMED target (must bind or fail, never silent nearest) + wire pick's verify to
  the resolved target so a named-but-unbound grab of the wrong object fails. (My track: skills/arm_sim_oracle;
  the verify-wiring must avoid the harness/verifier — Phase E territory.)
- **R2-8 — orphaned tool message 400 bricks the REPL. [FIXED 2026-06-09, headless-reproduced + green].** Found
  live (deepseek/openai-compat go2 session): after a long session EVERY input 400s `Messages with role 'tool'
  must be a response to a preceding message with 'tool_calls'` and the REPL is dead until restart. ROOT CAUSE:
  `session.py compact()` sliced `non_meta[-keep_recent:]` at a fixed index ignoring the
  `assistant(tool_use)->tool_result` pairing, so the kept window could BEGIN with an orphaned `tool_result`
  (its producing assistant summarized away); `to_messages()`->`convert_messages()` (openai_compat) then emitted
  a `role:"tool"` with no preceding `tool_calls`; persisted because `_entries` is replaced with `[summary]+recent`.
  TWO-LAYER FIX: (1) `compact()` snaps the keep boundary back so the recent window never starts on a tool_result;
  (2) `to_messages()` (the shared chokepoint BOTH backends consume) drops any orphaned tool_result (tracks open
  tool_use ids) — defends against any other orphan source (e.g. interrupted turns, R2-4). Behavior-preserving for
  well-formed histories. Tests `tests/unit/vcli/test_session_tool_compaction.py` (reproduced the 400 RED, then
  green): compact-no-orphan, to_messages-drops-orphan, repeated-compaction-valid. NOT owner-gated (fully
  headless). Canonical 1054 green.
- **go2 base verify GROUNDED in RobotWorld (generalize the arm grounding to the base). [SHIPPED 2026-06-09].**
  `RobotWorld.build_verify_namespace` only grounded the ARM (`agent._arm`); a go2 BASE got `{}` -> go2 NL->verify
  fell back to the engine stubs (ungrounded) — the SAME asymmetry the arm fix (Live-hardening V) closed. Fix
  mirrors it: the go2 base predicate factories are single-sourced into a kernel module
  `vcli/worlds/go2_sim_oracle.py` (`make_at_position`/`make_facing`/`make_visited`/`make_rooms_producer`;
  ADR-008 — kernel must not import playground), `playground/verify/base_predicates.py` is now a thin re-export
  shim, and `build_verify_namespace` COMPOSES arm predicates (if a sim `_arm`) AND base `at_position`/`facing`
  (if a `_base` with get_position/get_heading) — `visited` left to the playground (needs scenario rooms the
  plain world lacks). World-agnostic: arm-only / go2-only / go2+arm each grounded; real hardware still `{}`.
  Tests `tests/vcli/test_go2_base_grounding.py` (+ fixed a MagicMock-leaks-a-base under-spec in
  `test_robot_world_grounding`). Canonical 1087 green. NEXT (live, owner): go2 NL commands (walk/turn to a pose)
  now have grounded verify — validate the closed loop end-to-end on real deepseek like the arm.

## Autonomous /loop prompt (the standing mission for owner-away iterations)

Run via `/loop <this prompt>` (no interval => self-paced). Mission-oriented + high-autonomy: each firing
advances the mission as far as it safely can, not a single tiny edit.

> **Mission: advance vector-os-nano toward a generalizable PHYSICAL agent for robots.** Iterate autonomously
> (owner away; auto-approve on; branch `feat/verified-agent-kernel`; ONLY this project, never UniLab). This is
> a mission, not a checklist: make natural language truly control a robot through a grounded CLOSED loop
> (understand -> decompose -> plan -> execute -> verify -> replan -> recover), generalizing across embodiments
> (arm, go2, future) AND tasks. Simulation is a MEANS; the end is a physical robot agent. Push the LLM through
> the whole cognitive layer (language, decomposition, planning, strategy/verify selection, recovery); keep
> grounding/verify/safety DETERMINISTIC — verify is the moat, never LLM-graded. Prefer fixes that remove an
> embodiment asymmetry or generalize a mechanism over one-off patches.
>
> Each iteration, ORIENT then act with judgment — you have wide latitude:
> - ORIENT: read `docs/agent-kernel-STATUS.md` (live-bug backlog + where-are-we/next), `docs/ARCHITECTURE.md`,
>   and memories `vector-os-nano-live-hardening` / `-language-layer` / `workflow-model-tiering`. Optionally run
>   the real cli + deepseek to feel current state and discover issues.
> - CHOOSE a meaningful objective — a bug class, a capability, an architectural improvement — that moves the
>   mission forward. You MAY pursue a FARTHER goal across several workflows/edits in one iteration; don't
>   artificially stop at one tiny change. Decompose it yourself and advance as far as you safely can.
> - BUILD: reproduce/diagnose first, then implement via focused dynamic **Workflows** (implement -> 2-3
>   adversarial reviewers -> critic), chaining as many as the objective needs. Pin agent models per
>   `workflow-model-tiering`. Write/extend tests for logic that matters; add evals where output quality matters.
> - VERIFY HONESTLY: keep the canonical suite green (`.venv-nano/bin/python -m pytest tests/vcli
>   tests/unit/vcli -q`); validate behavior headless with the real cli + deepseek wherever possible. Some
>   things only reproduce in the owner's mjpython window (GUI render, real-time timing, Ctrl-C under mjpython)
>   — reason carefully, add what headless coverage you can, and CLEARLY hand the visual/timing confirmation to
>   the owner. Never claim a GUI-visual works unverified.
> - COMMIT + RECORD: self-review the real diff; green-then-commit in isolated, logically-scoped commits,
>   updating STATUS (+ ARCHITECTURE if structure/contracts changed) and the relevant memory in the SAME commit
>   (Doc Governance). Record what you did + what's next so the next iteration resumes cleanly. **Do NOT push.**
>   `git checkout mjcf/go2/scene_room_piper.xml` if a go2 test dirtied it.
>
> DON'T interrupt the owner to ask — make reasonable decisions and proceed. Only stop/surface on a GENUINE
> blocker: the canonical suite goes red and you can't get it green (halt-on-red; salvage + commit partial
> green), something needs the owner's GUI/hardware confirmation, or an action would be destructive /
> irreversible / outward-facing (push, deploy, delete owner data). Otherwise keep advancing the mission,
> iteration after iteration, then schedule the next one.
>
> Current backlog (advance any; not exhaustive — discover more): R2-1 go2 sim headless (generalize the
> mjpython/viewer GUI across embodiments) · R2-2 grasp real-time timeout (timeouts must fit real-time sim) ·
> R2-3 singular "抓个东西" -> grab ONE not foreach-all · R2-4 Ctrl-C clean exit under mjpython · R2-5 permission
> prompt blocks mid-task in sim · R2-6 ROS2-proxy ERROR bleed into panels · R2-7 longer-chain robustness +
> replan + richer skills/evals. See STATUS for details.
