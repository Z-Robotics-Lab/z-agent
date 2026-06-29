# >> REFACTOR HANDOFF — 2026-06-25 — find-and-grasp pipeline refactor in progress.
# Sim is FREE now (no mujoco). RESUME FROM: docs/plan-find-grasp-refactor.md + DECISIONS D88-D99 + git log.
# >> EYES NOW IN THE LOOP (ADR-002, D99): per-round REAL-VERIFY = tools/acceptance/measure_fetch_visual.py
#   (GT oracle + visual witness + temporal). `disagreements>0` (a GROUNDED turn the eyes object to) => red-team
#   BEFORE trusting grounded_rate. Gate semantics corrected: a GT-FAIL is NOT a vision disagreement (orthogonal
#   rubric is silent on success) — only GT-PASS+vision-FAIL is. See DECISIONS D99.
# >> LIVE EYES-VERIFIED BASELINE (2026-06-26, OpenRouter routing, N=5 "把绿色的瓶子拿过来"): grounded_rate=0.8
#   (4/5), vision_pass=5, DISAGREEMENTS=0 (no false-greens — eyes agree with the GT oracle on every success);
#   I read a grounded frame = real Go2+arm grasp at the table. CAVEAT (honest): temporal=None on all 4 grounded
#   trials — the 1-step perception_grasp routing captures <2 strip frames, so the temporal motion witness fires
#   only on the slower failed trial; GT weld (holding_object) + spatial vision still cover success.
# >> PROMPT-VERB ROUTING ("拿过来"=perception_grasp 0.8 / "拿给我"=handover 0.4, GT-measured). CORRECTION (D101,
#   adversarial review 2026-06-28): the handover-only GROUNDED was checked by the FROZEN GT WELD ORACLE + a human
#   frame-read — NOT "cleared by the eyes". The ADR-002 visual rubric is ORTHOGONAL (rendered/upright/intact/
#   in-frame) and STRUCTURALLY BLIND to grasp authenticity, so it can neither confirm nor refute a grasp; the eyes
#   have NEVER caught a real false-green and cannot catch a grasp-fakery one with the current rubric (real coverage
#   gap). The "拿给我" eyes run (0.4, disagreements=0) was TERMINAL-ONLY, never committed as a RESULT artifact.
#   All in-reach 1-step grasps; the FULL look->navigate->grasp never routed (object spawns in arm reach).
# >> THIS round (D100, commit d84aa5c): VECTOR_FETCH_FAR scenario knob — relocates the green target onto a new
#   pick_table_far ~3m down the +X hall (13.88,3.0), beyond perception_grasp's 1.6m self-approach, so a 1-step
#   grasp can't reach it. Additive/env-gated, default off = baseline preserved; verify spine reads live GT (honest).
#   FINDING (far-fetch, verify_fetch_cli N=3): forces the model OFF the 1-step grasp (routes mobile_pick x2 /
#   perception_grasp x1) and the dog PHYSICALLY navigates (eyes strip frame = dog mid-doorway), BUT grounds 0/3 —
#   the composed out-of-reach fetch is BROKEN. The model never composes the explicit navigate_to_object->
#   perception_grasp; mobile_pick navigates but fails to seat the grasp, bare perception_grasp can't reach (fails
#   loud, no replan-to-navigate). NEXT ROUND (Debug Protocol): why mobile_pick doesn't weld at the far table +
#   whether to steer routing toward navigate_to_object->perception_grasp. NOTE: far trials ~3-4min each (slow nav).
# >> THIS round (backlog #3; commit e762f12): merge_object x=0/y=0 SENTINEL TRAP FIXED. Backlog #1 (live-model
#   bare-cli full-fetch e2e, TOP priority) was NETWORK-BLOCKED — DeepSeek http=000 + GPT-4o 421 (VPN fake-IP);
#   per loop discipline pivoted to the offline backlog #3 (same bug class as the D97 (0,0) catastrophe).
#   FIX (scene_graph.py merge_object, spine untouched): the `x=x if x!=0.0 else existing.x` merge silently kept a
#   STALE pos when a real obs localized an object at the world origin / on the x=0|y=0 axis. Switched the sentinel
#   to None: None = no new localization (keep existing on merge, default 0.0 on new); a real float INCL 0.0 always
#   applied. Caller audit: all internal (649/708/744 coord-less; 701/738 coord-bearing) + test callers behavior-
#   preserved; only the genuine-0.0 case changes (was buggy). VERIFY = TDD (the honest verification for a pure
#   in-memory data-store fix, no sim-observable behavior): RED 3 origin cases failed → GREEN all 6 pass; 100
#   scene-graph + 175 core/perception/skills tests green, no regressions. tests/unit/core/test_merge_object_origin_sentinel.py.
# PRIOR: D97 (90dd65c) perception wired into the real go2 launcher (look/explore depth-localize, no (0,0) pollution),
#   real-verify via the ACTUAL launcher (<3cm vs GT). #1 positions VERIFIED (D91). #2 navigate_to_object (D92).
#   #3 pipeline COMPOSES e2e (D93). Grasp reliability RAISED to 0.833 (D94/D95) then PLATEAUED. home 5-vs-6 DoF FIXED (D96).
# NEXT round (non-gated): backlog #1 — drive the FULL fetch "把绿色瓶子拿过来" through the BARE `vector-cli` REPL by NL
#   end-to-end via the LIGHT in-process --sim-go2 path (tools/verify_fetch_cli.py EXISTS, WIP eddf8ad) — but ONLY
#   when network is up (needs DeepSeek routing + GPT-4o VLM naming; both down this round). If still network-down,
#   re-measure grasp reliability via the OFFLINE tools/measure_fetch_reliability.py (no model needed). Spine untouched.
#   #4 (find_objects_by_category substring) speculative — only if it bites at scale. #4-ext-explore / #5-store-unify = CEO GATES.
# OPEN CAVEATS: live-model bare-cli full-fetch e2e (backlog #1) still UNRUN — network-blocked (DeepSeek + GPT-4o down).
#   Grasp plateau ~0.83 (1 perception-framing + 1 terminal-grasp per ~12). merge_object sentinel trap now FIXED (D98).

# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this FIRST; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design = [ARCHITECTURE.md](ARCHITECTURE.md); how to start = [getting-started.md](getting-started.md);
decision history = [DECISIONS.md](DECISIONS.md); hidden-bug lessons = [tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-25 · R12 DONE (Yusen-directed): green grasp "hang" was a mj_forward DATA-RACE SEGFAULT — FIXED + regression-tested (447a100); obstacle-aware nav-approach integrated, all 3 colours GROUND deterministically (9d5adbe); live N=6=67% (4/4 perception_grasp routings grounded — drag is pre-existing model-routing variance, D86). navigate_to converges go2+g1 on one planner.
goal:    a PLUG-AND-PLAY agent-orchestration runtime for physical AI — bring your own robot
         (urdf+mesh+config), policy, skill, capability; plan · route · verify · recover. Bare
         `vector-cli` + NL is the only acceptance face; the honest-verify spine is frozen.
phase:   PLUG-AND-PLAY PLATFORM REFACTOR (branch `arch/plug-and-play` off `feat/orchestrator-redesign`).
         Make the OS config-driven (a robot = a CONFIG file, not a driver class — Rule 11) + model-routed
         (strangle the legacy keyword producer), staged strangler-fig with bare-cli e2e each stage (Rule 12).

doing:   loop R10 DONE — live-model grasp routing reliability MEASURED (Yusen authorized "A 去测"). Harness
         tools/measure_grasp_reliability.py: N fresh isolated `cli -p --sim --native-loop` subprocesses, REAL DeepSeek
         (.env), single-turn so the flaky multi-turn REPL launch is excluded. RESULT N=15: **13/15 = 87% GROUNDED**
         (model autonomously routes pick→holding_object('banana')→GROUNDED, graded by the untouched spine, real weld);
         2/15 RAN (model over-perceived → detect/scan instead of committing to pick); 0 stalls/timeouts/errors —
         CORRECTS the "5 stalls" prior (those were the multi-turn LAUNCH, not the routing). VISUAL (tools/visual_grasp.py,
         EGL offscreen, per Yusen's "see the effect"): before=banana on table → after=arm raised + banana removed
         (lifted 0.06→0.26m, holding True). Closes the R9/D79 #1 residual (North Star "route by the MODEL" was
         paper-tested). Failure mode is ACTIONABLE (a prompt/tool-desc nudge to grasp-not-over-detect could lift 87%).
         SCOPE: standalone-arm routing (cleanest isolation); go2+Piper perception_grasp is the harder follow-up.
         Committed aae6d77 (D80). NEXT options for Yusen: (a) raise the 87% (prompt nudge), (b) measure the go2+Piper
         perception grasp the same way, (c) the queued CEO gates (S8 etc.).
         ---
         loop R9 DONE — milestone adversarial REVIEW (Ultracode Workflow: 6 skeptics refute each R1-R8 headline +
         ambition critic + Opus judge; + my empirical re-verify: offline 1516 passed, S3b grasp RE-GROUNDS 36s, tree
         clean post-sim). VERDICT: the BUILT work is TRUSTWORTHY — spine byte-frozen across R1-R8 (independently
         re-verified), no false-greens, honesty discipline intact. FIXED 2 real overclaims the review caught: (1) the
         D74 "safe superset" was claimed unconditionally but holds only WITHIN AN ACTIONABLE WORLD + had an off-by-strip
         MISS ("去 " dropped) → aligned should_attempt_native threshold to len(raw)<2 (native_loop.py) + regression test
         (30 green) + scoped the D74 wording; (2) the stale "BYTE-UNCHANGED since 7b220d9" slogan → corrected. THE REAL
         FRONTIER (review's load-bearing finding; "non-gated exhausted" was PREMATURE): the North Star "route by the
         MODEL not keywords" is PAPER-TESTED — every seal is a deterministic FakeToolScriptBackend replay; live-LLM
         tests skipif'd off; the model-producer's e2e routing reliability is UNMEASURED (5 prior live runs stalled on
         variance → the deterministic half was sealed instead). See "Pending decisions" for the live-model-reliability
         harness (judge's #1; NON-gated but conflicts with the "no live-deepseek REPL" discipline → YUSEN's call).
         Committed this RECORD (code+test+docs). D79.
         ---
         loop R8 DONE — scene-XML churn hardening (the LAST non-gated item). FINDING: the R5 "entangled" worry was a
         MISREAD — test_scene_builder.py reads the go2_room.xml TEMPLATE (`_ROOM`) and REGENERATES scene_room_piper.xml,
         it does NOT read the committed scene as a golden reference; the sim fixtures' `git checkout` restore is in a
         caught except. So untracking is safe. DID: `git rm --cached` the 2 LIVE generated scenes
         (mjcf/go2/scene_room_piper.xml regenerated by build_room_scene; mjcf/g1/scene_g1_12dof_room.xml by
         _build_g1_room_scene_xml) + added both to .gitignore; `git rm` the DEAD orphan mjcf/g1/scene_g1_room.xml (no
         references; superseded). VERIFIED: tests/unit/test_scene_builder.py 6/6 green (regenerates the now-untracked
         scenes from the template) AND the tree stays CLEAN after regeneration — the churn that bit every R1-R7 sim
         round is gone. Committed this RECORD.
         >>> NON-GATED LADDER EXHAUSTED. All remaining substantial work is CEO-GATED and queued (Pending CEO gates):
         S8 (retire legacy producer) · S3c-impl (planner-plugin, deferred N≥3) · S4 (embodiment registry) ·
         S5 (ControlPolicy+convex_mpc dep) · S6 (capability permission/security). The loop has driven R1-R8 of
         non-gated frontier work; the killer-demo frontier (drop-a-robot+policy+skill→20min→GROUNDED) needs S4+S5
         (gated). DELIVERED a batched executive summary to Yusen this round; loop on a long await-CEO cadence.
         ---
         loop R7 DONE — S9 (docs rewrite + CI doc-drift gate; non-gated). docs/cli-tool-system.md was STALE (the audit
         flag): it described IntentRouter + `VectorEngine.run_turn()` + VGG decompose as the canonical flow, with
         native_loop mentioned once. REWRITE: added an authoritative "当前 producer 架构" section at the top — a
         producer-per-path table (REPL action→native, REPL chat→run_turn_unified, -p→native via _print_native_enabled,
         --native-loop→pure native, legacy/VECTOR_LEGACY_TURN→vgg_decompose) + the truth (native is the DEFAULT
         producer, routes by the model not keywords; IntentRouter/should_use_vgg is LEGACY being strangled→S8;
         should_attempt_native (D74) is the registry-driven replacement) + a 5-contracts pointer. Marked the stale
         sections (系统架构/Tool Call 流程/IntentRouter/VGG 层) as LEGACY. Added a CI DOC-DRIFT GATE
         (tests/unit/vcli/test_doc_drift_gate.py, green): parses the `<!-- doc-drift-gate: default_producer=run_turn_native -->`
         marker + asserts the LIVE default agrees (_repl_native_enabled & _print_native_enabled default ON) — the doc
         can never silently diverge from the code again. Doc count = 8 (≤8 hygiene OK). No source/behavior change.
         Committed this RECORD. NON-GATED LADDER NOW NEARLY EXHAUSTED — remaining non-gated = the deferred scene-XML
         untrack hardening (fiddly); everything else substantial (S8, S3c-impl, S4, S5, S6) is CEO-GATED.
         ---
         loop R6 DONE — S3c-design (navigate convergence, design-only). FINDING (verified by reading the code): the
         navigate capability is ALREADY converged at the TOOL layer — `_NativeBaseNavigateTool` calls
         `base.navigate_to(x,y,timeout=…)` POLYMORPHICALLY, no go2/g1 branch (Rule 11 met there). The "fork" is two
         PLANNER BACKENDS behind one interface: go2→`Go2ROS2Proxy.navigate_to` (external ROS2 CMU-FAR) and
         g1→`MuJoCoG1.navigate_to` (in-driver vgraph), both honoring (x,y,timeout)→truthy. The Rule-11 convergence =
         a PLUGGABLE planner Capability declared in robot.yaml (planner: far|vgraph) — GATED (new Planner interface +
         a `nav` robot.yaml field + FAR external-dep) → queued (Pending CEO gates) + recommend DEFER until N≥3 planners
         (YAGNI at N=2; ADR-001). DELIVERED: docs/ADR-001-navigate-convergence.md + a contract test
         (tests/unit/embodiments/test_navigate_contract.py, 2 green) pinning the polymorphic invariant. No
         behavior/interface change this round. Committed this RECORD.
         ---
         loop R5 DONE — tidy/de-slop (milestone cleanup; docs-hygiene). Fixed 2 ACTIVELY-MISLEADING producer
         docstrings invalidated by S5b: `engine.run_turn_native` "(M1, flag-gated OFF)…behind --native-loop" →
         it is now the DEFAULT producer (REPL `_repl_native_enabled` + `-p` `_print_native_enabled`); the flags are
         explicit forces. `engine.run_turn_unified` "DARK-LAUNCHED — nothing calls this yet" → it is LIVE on the REPL
         non-VGG tool_use/chat route (cli.py:2601). Imports OK + 49 focused tests green (docstring-only, no behavior
         change). FINDING: the generated-scene-XML untrack hardening is NOT trivial (test_scene_builder.py:58-59
         reads the committed XML as the byte-identical reference + ~10 @sim fixtures git-checkout it to restore churn)
         — DEFERRED to its own round; STATUS hardening note corrected. No code/behavior change. Committed this RECORD.
         ---
         loop R4 DONE — S5c (S8 precondition #3, the LAST). New `should_attempt_native(user_input, *, agent, engine)`
         (native_loop.py): the REGISTRY-DRIVEN native-attempt hint that replaces the keyword `should_use_vgg`. The
         native producer routes by the MODEL reading tool descriptions, so the only pre-gate question collapses to
         "does this world expose any actionable tool?" — derived SINGLE-SOURCE from `_build_motor_tools` (Rule 3, NO
         keyword table), fail-open. PROVEN a SAFE SUPERSET of `should_use_vgg`: for every input the keyword router
         routes to VGG, this also attempts → S8 can rewire the 4 gate sites off `should_use_vgg` with NO missed
         routing; its extra attempts (chat/questions) are fail-open fallbacks (a wasted LLM call, never a missed/wrong
         command). VERIFIED: 29 tests (parity/superset corpus + purity + fail-open + a REAL-derivation test against the
         live _build_motor_tools — a 10-skill agent → attempt True, trivial → False, empty toolset → False). SHADOW:
         NOT wired into live routing yet (zero behavior change — the rewiring is part of S8). Committed a563c62.
         >>> MILESTONE: S5a✅ + S5b✅ + S5c✅ = ALL S8 preconditions MET. S8 (retire the legacy keyword producer +
         tables) is now UNBLOCKED but is a CEO GATE (routing-contract + -p acceptance entrypoint + flag-default
         changes + big deletion). Per loop discipline: do NOT cross — an executive summary is queued (see Pending CEO
         gates) and the loop PIVOTS to non-gated work (S3c-design, hardening) until Yusen approves S8.
         ---
         loop R3 DONE — S5b (S8 precondition #2): native is the DEFAULT producer on the `-p` acceptance path.
         New `_print_native_enabled()` (cli.py, DEFAULT ON, escape hatch VECTOR_PRINT_NATIVE in {0,false,off,no})
         mirrors the owner-approved REPL cutover (`_repl_native_enabled`) on the non-interactive entrypoint:
         run_one_turn ATTEMPTS native first then FALLS THROUGH to legacy on no-action (strictly additive). Fires on
         `_native_first_enabled(args) or (_print_native_enabled() and not _native_loop_enabled(args))` — the default
         cutover does NOT pre-empt an explicit --native-loop (precedence guard), and the user-facing --native-first/
         VECTOR_NATIVE_FIRST flag default stays OFF (NOT changed → not the interface gate the judge flagged). Also
         FIXED the 3 pre-existing `test_repl_native_cutover` reds: ROOT CAUSE = the test's `_FakeEngine.run_turn_native`
         stub was missing the `on_progress` param the REAL engine gained, so `_repl_attempt_native`'s call raised
         TypeError (caught as "no action") — a STALE TEST, the production cutover was correct. VERIFIED: full
         `tests/unit/vcli tests/vcli tests/integration/vcli -m "not sim"` = 1460 passed (only the 3 pre-existing
         deepseek-config env reds); e2e = a RAW bare `-p` run on the go2 sim with NO native flag (default cutover) ->
         native OWNED the turn (strategy=walk, n_steps=1) -> honest verdict via the frozen spine (RAN this run: the
         open-loop walk didn't reach at_position(11,3) — sim-physics nondeterminism, NOT a producer defect). Committed
         8c1200e + this RECORD. (No committed default-cutover SIM test: run_cli_turn forces VECTOR_NATIVE_LOOP=1 for a
         tool_script w/o --native-first, so it can't exercise the default path — a harness limitation; test (c) is the
         committed sim proof of block-1's mechanism, units pin the default-trigger. D73.)
         ---
         loop R2 DONE — S5a (S8's precondition). A Decision Workflow (3 read-only recon agents + Opus judge)
         REFUTED the optimistic "native is already the default producer": truth = run_turn_native is default ONLY
         for REPL ACTION turns; chat/sim/switch still fall to legacy run_turn_unified, -p is native-OFF, and
         classify_intent/should_use_vgg is a LIVE gate at 4 sites — so S8 (delete legacy producer) CUTS a live
         dependency + touches a routing-contract interface = DEFERRED (gated). Chosen instead: S5a — single-source
         the 3 scattered ad-hoc capability gates (native_loop navigate gate, worlds/robot._agent_has_camera,
         engine._has_base) onto ONE `resolve_capability_profile(agent)` over the already-declared CapabilityProfile
         (embodiments/capability_profile.py NEW). Gated flags (has_base, camera) are runtime-authoritative =
         BYTE-IDENTICAL; enrichment flags (has_arm/has_gripper/lidar) reconcile runtime-OR-declared (handles the
         go2+Piper runtime-attach: bare go2 manifest says has_arm:false but a Piper binds at runtime → runtime wins).
         Rule 11 (no capability-by-code drift) + S8's precondition. VERIFIED: 13 new parity unit tests + full vcli
         suite 1435 passed ZERO assertion edits (byte-identical); e2e = the R1 grasp STILL GROUNDS on the real
         go2+Piper sim through the rewired _build_motor_tools (32s). Pre-existing reds (NOT mine, fail on clean HEAD):
         3 deepseek-config env + 3 tests/vcli/test_repl_native_cutover.py::test_repl_attempt_native_* (the REPL
         native-cutover path — investigate in S5b). Committed: c31c6d3 (code) + this RECORD.
         ---
         loop R1 DONE — S3b is SEALED (100%). New deterministic e2e `tests/vcli/test_native_loop_grasp_attach_pty.py`
         (35 s, `-m sim`) drives the native producer on the in-process go2+Piper ATTACH scene through a scripted
         `FakeToolScriptBackend` (NO live deepseek): `perception_grasp("抓绿色的瓶子")` -> `verify(holding_object(
         'pickable_bottle_green'))`. Asserts the FULL real pipeline grounded — colour/HSV resolve -> rendered-depth
         pointcloud (never GT) -> MPC-gait approach -> Piper top-down IK -> weld 0->1 -> lift — graded by the
         UNTOUCHED spine + the D69 gate: strategy==`perception_grasp`, verify_result True, `ActorCaused.CAUSED`,
         classify GROUNDED, `VerdictReport.verified`/`evidence==GROUNDED`/exit 0, `evidence_passed` True, with
         `holding_object()==False` pre-asserted (genuine 0->1). This decouples S3b's seal from deepseek's flaky
         multi-turn REPL (5 prior live runs stalled on model variance, never the grasp code). bare-cli + NL launch
         routing reliability is now a SEPARATE non-gated hardening item (not a blocker on S3b).
         WAS — S1·S2·S3a·S3b refactor + D69 (fakeable-grasp CLOSED) + scan-DoF, all COMMITTED. D69: a robot world
         DROPS file_write/file_edit/bash from the native ACTION toolset (Prong 1) + a rule-5 STRICTER-ONLY spine gate
         `_object_goal_turn_ok` (`cognitive/object_goal.py` + `trace_store`) — a grasp goal must be GROUNDED via a
         NECESSARY `holding_object`/`placed_count`, else RAN. scan-DoF: scan holds the arm's current pose when the
         configured pose len != the arm DoF (Piper 6-vs-5). 786 unit green (only 3 pre-existing env reds).
         ---
         S1+S2+S3a+S3b DONE + verified (behavior-preserving). S3b: ONE scene builder —
         `hardware/sim/scene_builder.py build_room_scene(...) -> (MjModel, path)` via `MjSpec.attach`;
         BOTH `_build_room_scene_xml` (go2, prefix="") and `_build_g1_room_scene_xml` (g1, prefix="g1_") call
         it (the two-scene-builder fork is KILLED). Root blocker was a MuJoCo-3.9 `attach`+`to_xml` serializer
         bug (anonymous nested `<default>` → reload "empty class name"); fixed (B) = in-memory `compile()`
         authoritative + `normalize_attach_defaults` repairs the FILE (go2.xml NOT touched — fix A rejected).
         2nd blocker (build agent STOPPED at the byte-id guardrail): attach reorders go2 qpos (freejoint
         0→21, arm 19→40); finished D66's missed qpos-order literals (arm-stow + MPC pin) to DofLayout. Latent
         bug fixed: arm-stow guard nq≥27→nu≥19 (pickables inflate bare nq to 40 → Case 8). BYTE-IDENTICAL all
         3 cases (go2+arm/bare/g1: counts+name-sets+class-default params by NAME). ORCHESTRATOR VERIFICATION
         caught+fixed a 2nd reorder regression the build agent MISSED: `MuJoCoPiper` IK base-sync read literal
         `qpos[0:19]` → pickables under attach (root=21); fixed to DofLayout-derived (Case 9); IK-base-sync e2e
         CONFIRMED (IK tracks the moved dog, not the default). 50 driver + 17 piper unit green. FULL bare-cli
         grasp e2e still OWED before S3b is 100% done (R12).
         S2: drivers READ `robot.yaml` + generic `DofLayout`. S1: config schema + g1 BaseProtocol uniformity.

owns:    `embodiments/**`, `hardware/sim/{scene_builder.py, mujoco_go2.py, mujoco_g1.py, mujoco_piper.py}`,
         `vcli/native_loop.py`, `vcli/cognitive/{object_goal.py NEW, trace_store.py}`, `docs/*`.
         Spine `vcli/cognitive/` was byte-unchanged 7b220d9→D68; D69 is the FIRST deliberate edit since — a
         PURELY STRICTER object-goal turn-gate (rule 5 "only ever stricter"; evidence_classifier / actor_causation
         / coord_goal still UNTOUCHED).

blocked: none. Later stages carry CEO gates (surface, do NOT cross): S4 embodiment-registration
         interface (replace the `sim_tool` enum); S5 `ControlPolicy` interface + convex_mpc as an explicit
         dep; S6 capability permission/security path for side-effecting VLAs. Full analysis: /tmp/pnp_synthesis.md.

next:    LOOP ROUND LADDER — CORRECTED by the R2 Decision Workflow (S8 was premature). Cold-ORIENT each round:
         · R1 ✅ (D71) S3b SEALED. · R2 ✅ (D72) S5a cap-gating single-sourced. · R3 ✅ (D73) S5b native=-p default.
           · R4 ✅ (D74) S5c registry-driven should_attempt_native (shadow superset). ALL S8 preconditions now MET.
           · R5 ✅ (D75) tidy/de-slop: fixed 2 stale producer docstrings; gitignore-untrack found entangled (deferred).
           · R6 ✅ (D76) S3c-design: navigate already converged at the tool layer; planner-plugin GATED+deferred (ADR-001).
           · R7 ✅ (D77) S9: cli-tool-system.md rewritten to the native path + CI doc-drift gate (test_doc_drift_gate.py).
           · R8 ✅ (D78) scene-XML churn fixed (untracked+gitignored 2 generated scenes, deleted 1 orphan; byte-id test green, tree clean).
         · NEXT: non-gated ladder EXHAUSTED. The loop awaits CEO approval on the batched gates (Pending CEO gates):
           S8 (retire legacy producer; preconditions all met) · S3c-impl (planner-plugin, deferred N≥3) · S4/S5/S6.
           On a long await-CEO cadence: each wake re-ORIENT; if still all-gated + no new direction, light regression-watch
           + re-sleep long. When Yusen approves a gate (or leaves new direction), resume that work.
         · S8 (GATED — preconditions S5a✅+S5b✅+S5c✅ ALL MET; awaiting CEO approval, see Pending CEO gates):
           retire classify_intent/should_use_vgg + IntentRouter/StrategySelector tables + GoalDecomposer/GoalExecutor
           legacy producer. Routing-contract + -p acceptance entrypoint + escape-hatch flag defaults → exec summary first.
         · Deferred hardening (its own round): the generated-scene-XML untrack — NOT trivial (R5/D75 finding):
           test_scene_builder.py:58-59 reads the committed scene XML as the byte-identical REFERENCE + ~10 @sim
           fixtures `git checkout` it to restore churn; untracking breaks both. Needs re-pointing the reference + fixtures.
         · Non-gated hardening: the deepseek multi-turn REPL-routing reliability (dev-world launch routing);
           gitignore the runtime-GENERATED scene XMLs (scene_room_piper.xml / scene_g1_*; they churn).
         · CEO-GATE stages — do NOT cross; DESIGN + spike + exec-summary to a `## Decisions pending` queue, then
           PIVOT to non-gated work: S4 embodiment registry (sim_tool enum→registry INTERFACE), S5 ControlPolicy
           plugin + convex_mpc DEP, S6 capability planner-exposure + side-effecting-VLA PERMISSION/SECURITY.
         DISCIPLINES (every round — also in ~/.claude/loops/vector-plugnplay.goal): branch `arch/plug-and-play`
         ONLY (never break master / feat/orchestrator-redesign); spine `vcli/cognitive/` ONLY EVER STRICTER
         (rule 5; prefer world-side; D69 is the precedent); a behavior-preserving refactor must be byte-identical
         + e2e-verified (R12) via bare `vector-cli` OR `FakeToolScriptBackend`; serialize sims (ONE at a time) +
         `rosm nuke` + `pkill -9 -f '[m]ujoco'` after each, MUJOCO_GL=egl; NEVER trust subagent self-reports —
         verify diff + re-run + e2e yourself (esp. any moat edit); blast-radius-grep after a layout change
         (Case 8/9); UPDATE STATUS + a DECISIONS dot-point + ARCHITECTURE-if-structural EVERY round (docs-hygiene).
         Repro: grounding-dino + EdgeTAM offline-cached; `timm>=1.0`; /tmp/pnp_synthesis.md = full refactor analysis.

## The 5 plug-and-play contracts (the refactor's structural spine — R11; detail → ARCHITECTURE.md)
- **Embodiment**: urdf+mesh+`robot.yaml` → drivers READ it via `DofLayout` (S1 schema + S2 wired; S4 = one generic driver class).
- **Policy**: gait/control plugged separately by an obs/action spec (S5).
- **Skill**: `@skill` declaring `requires` arm|base|camera; may wrap an external VLA/VLM or a classical stack.
- **Capability**: register an external model/stack (detector/planner/VLA) as a routable unit (S6 planner-exposure).
- **Verify**: a world-side predicate reading INDEPENDENT GT; the frozen spine grades it.

## G1 cross-embodiment (durable summary; round narrative in DECISIONS D57-D64 + git)
- R1-R8: g1 (12-dof RL gait) STANDS+WALKS in the go2 room (D57-58); a MOAT-GRADED routable embodiment with
  go2 parity (D59, `at_position`→RAN honest D14); grounding-dino routes onto its head camera (D60), R4's
  false-green fixed→RAN (D61), audit-clean (R6); FIRST honest GROUNDED via GT-segmentation match (D63);
  obstacle-aware `navigate_to` via `g1_vgraph` (D64). cross-MODEL (D48-D51) is LIVE on master.

## Standing facts (durable)
- Branch `arch/plug-and-play` off `feat/orchestrator-redesign` off master; `feat/playground-vln` is ABANDONED.
- Honest-verify moat: a step grades GROUNDED only when a deterministic predicate reads an oracle the ACTOR
  cannot author. The sandbox may only get STRICTER (rule 5). `vcli/cognitive/` was byte-unchanged 7b220d9→D68;
  D69 (object_goal.py + the trace_store gate) is the ONE deliberate edit since, and it is STRICTER-ONLY; the spine
  tree-hash has been byte-frozen across the entire R1-R8 loop arc (independently re-verified R9/D79). [Was a stale
  absolute "BYTE-UNCHANGED since 7b220d9" slogan — corrected R9 since D69 made it literally false.]
- `native_loop.run_turn_native` is the default model-driven producer (no keyword table); the legacy keyword
  producer is being strangled (delete at S8). Acceptance = bare `vector-cli` + NL only.
- cross-MODEL (D48-D50) + the moat are LIVE on master (origin/master cd7029a).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- **STRATEGIC DECISION (non-gate, R9/D79) — measure the live-model producer reliability?** The R9 review's
  load-bearing finding: the North Star ("route by the MODEL, not keywords") is PAPER-TESTED — every seal is a
  deterministic FakeToolScriptBackend replay; the model-producer's e2e routing reliability has NEVER been measured
  (5 prior live runs stalled on variance → the deterministic half was sealed). Judge's #1: build a LIVE-LLM grasp
  reliability harness (swap the fake backend for the real model in test_native_loop_grasp_attach_pty, N≈20, publish
  the routing %). It is NON-gated (the approved acceptance path + real model + sample size) BUT directly conflicts
  with the standing loop discipline "不用 live-deepseek 多轮 REPL" → NOT run autonomously; YUSEN decides: (a) authorize
  the live-reliability harness (accept the model-variance + network risk), or (b) keep the deterministic-seal posture
  and treat live reliability as out-of-scope. This is the real frontier the loop has been routing around.
- **S8 — retire the legacy keyword producer (READY for approval; all preconditions S5a/S5b/S5c done).**
  One-liner: delete the keyword routing layer so routing is model + declared-metadata only (North Star).
  Remove: `IntentRouter` (`_RULES`/`should_use_vgg`/`is_complex`/`_MOTOR_*` keyword sets) + `StrategySelector`
  keyword ladder + `engine._DIR_MAP`/`_VERIFY_MAP`/`_ROOM_ALIASES` + the legacy `GoalDecomposer`/`GoalExecutor`
  producer; rewire the 4 `should_use_vgg` gate sites (cli.py:414/2445, engine.py:1090/1707) onto the proven
  `should_attempt_native` (D74). Keep `legit-config` rows (stop-words, `_TOOL_CATEGORIES`, `_COLOR_TO_SCENE` until a
  scene-name binder lands). WHY GATED: changes the routing CONTRACT + the `-p`/REPL acceptance entrypoints + retires
  a producer; a big, owner-visible behavior-contract change. RISK: a goal the model can't route loses the legacy
  fallback (mitigation: keep `VECTOR_LEGACY_TURN`/`VECTOR_PRINT_NATIVE` escape hatches one milestone). VERIFY: full
  S0 regression + a novel 3rd-language phrasing all route with ZERO keyword tables; `red-team` before sealing.
  → Needs Yusen's go/no-go before the deletion. Until then the loop does S3c-design + hardening.
- **S3c — navigate planner-plugin (DESIGN done, ADR-001; implementation GATED + recommend DEFER).**
  Navigate is already converged at the TOOL layer (one polymorphic `_NativeBaseNavigateTool`; pinned by
  tests/unit/embodiments/test_navigate_contract.py). The Rule-11 convergence of the two PLANNER backends
  (go2 external ROS2-FAR vs g1 in-driver vgraph) = a pluggable planner Capability declared in robot.yaml
  (`planner: far|vgraph`). GATED: new Planner interface + a `nav` robot.yaml field + the FAR external-dep
  formalization. Recommendation (ADR-001): DEFER until N≥3 planners/embodiments motivate the abstraction
  (YAGNI at N=2; no regression risk meanwhile). → Yusen go/no-go, batched.
- Plug-and-play stage gates: S4 embodiment-registration interface · S5 `ControlPolicy` interface + convex_mpc dep
  · S6 side-effecting-capability permission/security. Plus: nav→FAR cmd_vel causation (SPINE D14) · strategy_params
  preservation (SPINE D52) · explore TARE · VLN SysNav. New deps / interfaces / hardware / security route here.
