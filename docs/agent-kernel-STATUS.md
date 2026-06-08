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

- **R2-1 — Go2 sim opens HEADLESS (no window) while the arm opens one.** "启动 go2 带臂" ran headless;
  owner: "无法打开 go2 的 sim … 应该是一个可泛化的操作." The mjpython re-exec + passive-viewer GUI must
  generalize across embodiments. Investigate the go2 launch path (`--sim-go2` / NL "启动go2") vs the arm
  re-exec guard + `MuJoCoGo2` viewer (gui flag, `_viewer`/`viewer`). Make the viewer a ONE world-agnostic
  mechanism, not arm-only.
- **R2-2 — Grasp TIMES OUT under the real-time GUI.** `step_4_grab_each[0].grab_item` timeout 22.7s (limit
  15s). Under a live viewer, `MuJoCoArm.move_to` syncs to wall-clock, so the full pick motion sequence runs
  in REAL TIME (~20s+) and blows the 15s step/foreach-body timeout. Headless pick is ~3s (no real-time
  sleeps) so headless tests miss this. Fix: timeouts must fit real-time sim — raise the pick/motor step
  timeout (skill-declared durations, or scale the decompose `timeout_sec` for motor skills), and/or speed up
  pick. World-agnostic (go2 walk/patrol have the same real-time issue).
- **R2-3 — "抓个东西" (singular, unbound) expands to a foreach grabbing EVERY object.** A singular "grab
  something" should grab ONE (e.g. the nearest), not iterate all. Teach the decompose to distinguish singular
  vs "all/每个" (LLM-side intent), and/or the unbound grab -> single nearest. (Earlier idea: unbound -> nearest
  in pick, language-neutral.)
- **R2-4 — Ctrl-C does not exit cleanly under mjpython + sync GUI exec.** Owner had to ^C^C then type `quit`.
  The synchronous GUI exec path (Step 1) + permission prompt swallow KeyboardInterrupt. Make ^C abort the
  running task and return to the prompt; a second ^C / `quit` exits cleanly.
- **R2-5 — Permission prompt blocks mid-task under the live region.** "自己想个任务做" -> "Allow scan?
  [y/n/a]" hung (input not consumed under mjpython/the live region). Sim skills (scan/detect/...) are safe:
  auto-allow safe sim skills (or `--no-permission` default in sim), and/or fix the prompt rendering so it
  reads input outside the live region.
- **R2-6 — stderr / ROS2-proxy ERROR bleed into the rich panels.** `ERROR:...go2_ros2_proxy` / `sim_tool`
  lines interleave with the live boxes. Step-4 quieting covered skills/perception/hardware but ERROR-level
  ROS2-proxy noise still bleeds; fix stderr handling around the go2 launch + quiet the proxy in sim.
- **R2-7 — capability (not a bug): generalization + longer chains.** Reduce embodiment asymmetry; harden
  multi-step planning + observation-driven replan; the foreach grasp fallback emitted "grab_one -> Cannot
  locate target object" after the timeout — inspect the replan path.

## Autonomous /loop prompt (the standing instruction for owner-away iterations)

Run via `/loop <this prompt>` (no interval => self-paced). Each firing = ONE focused fix/improve increment.

> Autonomous iteration on **vector-os-nano** (branch `feat/verified-agent-kernel`; ONLY this project, never
> UniLab). Model deepseek-v4-flash (config set). NORTH STAR: a generalizable **PHYSICAL agent for robots** —
> NL controls everything via a grounded CLOSED loop (decompose -> plan -> execute -> verify -> replan); sim is
> a MEANS, not the end. Leverage the LLM throughout the cognitive layer (language/planning/selection); keep
> grounding/verify/safety DETERMINISTIC (verify is the moat). Every fix must GENERALIZE across embodiments
> (arm AND go2 AND future) and tasks — never an arm-only / banana-only patch.
>
> EACH ITERATION:
> 1. Read `docs/agent-kernel-STATUS.md` ("Known live bugs — ROUND 2" backlog) -> `docs/ARCHITECTURE.md` ->
>    memories `vector-os-nano-live-hardening`, `vector-os-nano-language-layer`, `workflow-model-tiering`.
> 2. Pick the ONE highest-value item (or discover a new one by running the REAL cli + deepseek and
>    reproducing). Reproduce + diagnose root cause FIRST.
> 3. Fix via a focused dynamic **Workflow** (implement -> adversarial review (2-3 lenses) -> critic), 2-3
>    increments max (avoids the StructuredOutput flake). Pin agent models per `workflow-model-tiering`.
> 4. VALIDATE: full suite green (`.venv-nano/bin/python -m pytest tests/vcli tests/unit/vcli -q`) + headless
>    real-cli/deepseek where possible. Some issues (GUI window, real-time timing, Ctrl-C under mjpython) ONLY
>    reproduce in the owner's window — reason carefully, add what headless coverage you can, and CLEARLY hand
>    the visual/timing check to the owner; never claim a GUI-visual works unverified.
> 5. Self-review the real git diff. Green-then-commit ISOLATED, with STATUS (+ ARCHITECTURE if structure
>    changed) updated in the SAME commit (Doc Governance). Update the relevant memory. **Do NOT push.**
>    `git checkout mjcf/go2/scene_room_piper.xml` if a go2 test dirtied it.
> 6. Halt-on-red (salvage partial green). Record progress + the next item in STATUS so the next firing
>    resumes cleanly. Then schedule the next iteration.
>
> Backlog now: R2-1 go2 sim headless (generalize the mjpython/viewer GUI across embodiments) · R2-2 grasp
> real-time timeout (timeouts must fit real-time sim) · R2-3 singular "抓个东西" -> grab ONE not foreach-all ·
> R2-4 Ctrl-C clean exit under mjpython · R2-5 permission prompt blocks mid-task in sim · R2-6 ROS2-proxy
> ERROR bleed into panels · R2-7 longer-chain robustness + replan. See STATUS for details. Prefer the fix that
> removes an embodiment asymmetry or generalizes a mechanism over a one-off patch.
