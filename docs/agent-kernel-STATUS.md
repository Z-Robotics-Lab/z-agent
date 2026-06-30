# >> FETCH-CAMPAIGN HANDOFF — cold-read: docs/plan-find-grasp-refactor.md + DECISIONS D99-D110 + git log -15.
# >> EYES = per-round REAL-VERIFY (ADR-002, D99/D101): tools/acceptance/measure_fetch_visual.py is a 2nd VLM
#    witness beside the GT oracle — emits PASS|FAIL|ABSTAIN, NEVER feeds evidence_passed, flags only
#    GT-PASS+vision-FAIL for red-team. Coverage gap (D101): BLIND to grasp authenticity -> the GT weld
#    (holding_object) is the success authority. disagreements>0 => red-team before trusting any grounded_rate.
# >> IN-REACH fetch: grounded_rate ~0.8 (D99, frozen weld+lift oracle, three consistent runs) — steady baseline.
# >> FAR fetch (out-of-reach) via perception_grasp is now RELIABLE (D111, 7756132): the D110 "sometimes
#    no_detections" variance was ROOT-CAUSED (logged probe) to a NAV terminal-heading bug, not perception —
#    FAR's navigate_to leaves the dog mis-faced at the standoff and the one-directional ~200deg re-perceive
#    scan misses the bottle. FIX (skill-level, kernel/moat untouched): the recovery faces the KNOWN seed xy
#    via _grasp_ready_repose before re-perceiving. Verified 3/3 skill-direct (real weld +0.23m each).
#    Mechanism still = SKILL-LEVEL recovery in perception_grasp (D109, CEO Gate A — NOT a kernel replan).
# >> FAR FETCH WORKS but is ROUTING-GATED (D111-D114, campaign #1). perception_grasp far is RELIABLE when
#    routed (D111 face-the-seed: 9/9 grounds); D112 mobile_pick fast-fails honestly; D113 routing-descriptions
#    shifted routing toward perception_grasp. RED-TEAM (D114, the key honesty catch): the early "5/5" was a
#    routing STREAK — honest far-green grounded_rate ≈ 9/12 (0.75) over 12 model-path samples (GT weld), because
#    the model STILL picks mobile_pick ~25% of the time (-> fast object_not_found, no ground). 0.75 is just
#    BELOW the >=0.8 target; the binding constraint is now ROUTING CONSISTENCY, not any single skill. Blue 1/1
#    grounded. RED 0/1 = a separate FOV issue (below). Pre-all-fixes the same command was 0/N.
# >> RED short-can FOV (next seed): the red object is a CAN, shorter than the bottles; its mask is ~1000px
#    at the 3.9m scan but 0 at the ~0.9m grasp standoff — it falls below the head camera's vertical FOV up
#    close. Fix = raise camera tilt / widen standoff for short objects.
# >> NEXT (non-gated): (1) RED short-can FOV fix; (2) EYES (ADR-002 VLM 2nd witness) grounded_rate over N for
#    green/blue when the VLM net is stable (GT weld is the authority now; OpenRouter dropped connections
#    intermittently this session); (3) near all-3-colours confirm. Then find-fetch is reliably closed;
#    PLACE half remains CEO-gated (D106 receptacle oracle).
# >> CEO gates still queued (do NOT cross — see Pending CEO gates below): S8 · S3c · S4 · S5 · S6 · D106 place oracle.

# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this FIRST; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design = [ARCHITECTURE.md](ARCHITECTURE.md); how to start = [getting-started.md](getting-started.md);
decision history = [DECISIONS.md](DECISIONS.md); hidden-bug lessons = [tricky-bugs.md](tricky-bugs.md).
This is a SNAPSHOT, not a log — the round-by-round history lives in DECISIONS + git.

updated: 2026-06-30 · D125 — PLACE CAPABILITY reliable 6/6 (D123); mobile_place productionized + SAFE-DROP guard makes the skill report HONEST (no false success — drops only when EE over receptacle, else dock_off_receptacle). Residual reliability blocker = jam-dock QUALITY (EE lands off-centre). Oracle moat-proven (D116); eyes path fixed (D117).
goal:    a PLUG-AND-PLAY agent-orchestration runtime for physical AI — bring your own robot (urdf+mesh+config),
         policy, skill, capability; plan · route · verify · recover. Bare `vector-cli` + NL is the only
         acceptance face; the honest-verify spine is frozen.
phase:   FIND-AND-GRASP / FETCH campaign on `arch/plug-and-play` (find→navigate→grasp, in- and out-of-reach).
         The plug-and-play platform refactor's S1/S2/S3a/S3b/S5a landed (durable status → ARCHITECTURE §3);
         remaining stage work (S4/S5/S6/S8/S3c) is CEO-gated.
owns:    `skills/{perception_grasp,navigate_to_object,mobile_*}.py`, `perception/object_localizer.py`,
         `tools/acceptance/**` + `acceptance/**`, `docs/*`. Spine `vcli/cognitive/` is FROZEN
         (only-ever-stricter; untouched this campaign — see Standing facts).
doing:   FAR FETCH is ROUTING-INDEPENDENT now (D115): mobile_pick DELEGATES to perception_grasp on an
         un-localizable target (frame-correct, DELEGATE_GROUND_PASS) + the recovery facing is closed-loop
         (_face_object, fixes the open-loop repose undershoot). So whichever skill the model picks, a clean
         single grasp step grounds. REMAINING GATE = model PLANNING variance: the model sometimes emits a
         MULTI-STEP find/detect/explore plan that never reaches a grasp (RAN) — D103/D104 residue, the next
         lever. perception_grasp far grounds 9/9 when a single grasp step is emitted. in-reach 0.8 steady;
         multi-object D108 sealed; eyes far-confirmation still pending a clean grounded trial.
blocked: none non-gated. CEO gates queued (do NOT cross) — see Pending CEO gates.
next:    PLACE capability 6/6 (D123); mobile_place SAFE+HONEST (D125, never falsely claims a place). Remaining for
         a RELIABLE skill place: (1) jam-dock QUALITY — land the EE over the receptacle CENTRE (lateral-centred
         jam; or target the reachable near-edge + receptacle-extent-aware tolerance) -> reproducible SKILL place
         over N -> bare-cli MODEL-PATH pick-and-place; (2) grasp-retry that resets the dog heading; (3) wire
         resting_on_receptacle into the verify namespace. FETCH eyes-rate floor (network-gated): (4) FAR eyes-rate
         over N when the routing net is stable; (5) planning-variance; (6) RED short-can FOV; (7) EGL strip fix.

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
  → Needs Yusen's go/no-go before the deletion.
- **S3c — navigate planner-plugin (DESIGN done, ADR-001; implementation GATED + recommend DEFER).**
  Navigate is already converged at the TOOL layer (one polymorphic `_NativeBaseNavigateTool`; pinned by
  tests/unit/embodiments/test_navigate_contract.py). The Rule-11 convergence of the two PLANNER backends
  (go2 external ROS2-FAR vs g1 in-driver vgraph) = a pluggable planner Capability declared in robot.yaml
  (`planner: far|vgraph`). GATED: new Planner interface + a `nav` robot.yaml field + the FAR external-dep
  formalization. Recommendation (ADR-001): DEFER until N≥3 planners/embodiments motivate the abstraction
  (YAGNI at N=2; no regression risk meanwhile). → Yusen go/no-go, batched.
- **D106 — receptacle-relative place oracle: CEO-APPROVED + BUILT + MOAT-PROVEN (D116).** The height-aware
  `make_resting_on_receptacle` oracle is in the spine (additive, `placed_count` byte-unchanged → monotonicity by
  construction), adversarially moat-proven (skeptic caught+fixed 2 false-greens: velocity fail-safe-reject +
  low-receptacle held-check guard). The CEO-gated spine piece is DONE. REMAINING (non-gated plumbing): wire it
  into the verify namespace (robot.py) · add a height receptacle to the go2 scene · arm↔table descent fix ·
  real-sim ground a bare-cli pick-AND-place. Until those land, place still ships as the grasp→release primitive.
- Plug-and-play stage gates: S4 embodiment-registration interface · S5 `ControlPolicy` interface + convex_mpc dep
  · S6 side-effecting-capability permission/security. Plus: nav→FAR cmd_vel causation (SPINE D14) · strategy_params
  preservation (SPINE D52) · explore TARE · VLN SysNav. New deps / interfaces / hardware / security route here.
