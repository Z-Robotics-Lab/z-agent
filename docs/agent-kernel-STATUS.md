# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this FIRST; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design = [ARCHITECTURE.md](ARCHITECTURE.md); how to start = [getting-started.md](getting-started.md);
decision history = [DECISIONS.md](DECISIONS.md); hidden-bug lessons = [tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-24 · loop R2 — S5a: capability gating single-sourced onto resolve_capability_profile (byte-identical); S8 deferred (premature)
goal:    a PLUG-AND-PLAY agent-orchestration runtime for physical AI — bring your own robot
         (urdf+mesh+config), policy, skill, capability; plan · route · verify · recover. Bare
         `vector-cli` + NL is the only acceptance face; the honest-verify spine is frozen.
phase:   PLUG-AND-PLAY PLATFORM REFACTOR (branch `arch/plug-and-play` off `feat/orchestrator-redesign`).
         Make the OS config-driven (a robot = a CONFIG file, not a driver class — Rule 11) + model-routed
         (strangle the legacy keyword producer), staged strangler-fig with bare-cli e2e each stage (Rule 12).

doing:   loop R2 DONE — S5a (S8's precondition). A Decision Workflow (3 read-only recon agents + Opus judge)
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
         · R1 ✅ (D71) S3b SEALED.  · R2 ✅ (D72) S5a capability-gating single-sourced.
         · S5b (NON-gated, next): make run_turn_native the default on the -p path (run_one_turn, cli.py:1751-1848)
           via an ADDITIVE native-attempt-then-fall-through (mirrors the REPL cutover), KEEPING the legacy flags at
           their current defaults (changing a user-facing flag DEFAULT is an interface gate → NOT here). NB: fix /
           understand the 3 pre-existing test_repl_native_cutover reds here (the cutover-attempt path).
         · S5c (NON-gated): a registry-driven should_attempt_native(...) routing HINT (Rule 3 single-source) run
           ALONGSIDE classify_intent().use_vgg (shadow/parity, not replacing) — proves a model-driven replacement
           exists with zero behavior change, so the 4 keyword-gate sites can later be rewired off should_use_vgg.
         · S3c-design (NON-gated DESIGN only): navigate convergence (g1 in-driver vgraph vs go2 external ROS2-FAR →
           one config-parameterized capability). Pure design/ADR; the moment it proposes touching a nav INTERFACE →
           decision queue, do NOT implement.
         · S8 (GATED + cuts live deps — REQUIRES S5a✅+S5b+S5c green): retire classify_intent/should_use_vgg +
           IntentRouter/StrategySelector tables + GoalDecomposer/GoalExecutor legacy producer. Routing-contract +
           -p acceptance entrypoint + escape-hatch flag defaults → executive summary to the decision queue first.
         · Hardening (NON-gated filler): generated-scene-XML gitignore is PARTIAL (the R2 judge's "already done" was
           WRONG — verified via git check-ignore): .gitignore covers go2 scene_flat/scene_room (L17-18) + the OLD
           hardware/sim/ location (L49-51), but mjcf/go2/scene_room_piper.xml AND mjcf/g1/scene_g1_*.xml are STILL
           TRACKED and churn on every connect. Fix = add those paths + `git rm --cached` them (FIRST confirm no
           scene-builder byte-identical test reads the committed XML as a reference). Plus stale docstrings
           (engine.py:1637/1677-1680, cli.py native-loop help) — doc-only, byte-safe.
         · S9  docs: rewrite the workflow narrative to the native path + a CI drift gate.
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
  cannot author. The sandbox may only get STRICTER (rule 5). `vcli/cognitive/` BYTE-UNCHANGED since 7b220d9.
- `native_loop.run_turn_native` is the default model-driven producer (no keyword table); the legacy keyword
  producer is being strangled (delete at S8). Acceptance = bare `vector-cli` + NL only.
- cross-MODEL (D48-D50) + the moat are LIVE on master (origin/master cd7029a).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- Plug-and-play stage gates: S4 embodiment-registration interface · S5 `ControlPolicy` interface + convex_mpc dep
  · S6 side-effecting-capability permission/security. Plus: nav→FAR cmd_vel causation (SPINE D14) · strategy_params
  preservation (SPINE D52) · explore TARE · VLN SysNav. New deps / interfaces / hardware / security route here.
