# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D178 — g1 VLN (perception-DRIVING-locomotion) infrastructure LANDED + the honest-grounding
blocker turned from a flagged guess into a HARD, evidenced CEO gate. Non-gated pieces shipped + real-verified; the
GROUNDED bare-REPL acceptance is one approved spine-allowlist line away.
- SHIPPED (non-gated, reproducible from git): (1) scene_builder gains additive `extra_geoms` (default ()→go2 byte-unchanged);
  g1 injects a blue VLN target mat (12.6,3) in the +x head-cam FOV (visible ~3800px, planner arrives 0.28m). (2) pure
  ground-projection util `project_pixel_to_ground` (5 unit tests incl. live-probe regression) turns a detected blob pixel
  into a world (x,y) via sim-owned intrinsics/extrinsics the actor cannot author. (3) `MuJoCoG1.get_camera_fovy()`.
- REAL-VERIFY (deterministic chain probe, ONE sim, nuked): detect(head-cam)→ground-project→navigate lands **0.18m from the
  mat GT**, actor=CAUSED. RED-TEAMED: projected target TRACKS the mat (y follows 3.0/2.2/3.8 as the mat moves; bbox NOT
  degenerate) ⇒ perception genuinely load-bearing, NOT a fixed forward walk. Projection err 0.37–2.33m (bottom-centre
  heuristic degrades for close/tall boxes) — honest limit.
- CONFIRMED BLOCKER (was D177's flagged guess): honest VLN GROUNDING on the bare REPL REQUIRES a GT-backed
  `near_object(colour)` predicate added to the KERNEL allowlist `vcli/cognitive/evidence_classifier._PREDICATE_ORACLES`
  (precedent: `resting_on_receptacle` was such an edit, D106 CEO-APPROVED) ⇒ honest-verify-SPINE gate, do NOT self-cross.
  WHY needed: raw grounding-dino is NOT colour-selective on the mat (boxes it for BOTH blue & green) → the raw box is not a
  moat; only the GT object-pos oracle + actor-causation guard can honestly ground/refute. `at_position(projected_xy)` is
  CIRCULAR (actor authors the coord) → rejected as a moat.

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   VLN (g1's 3rd capability = perception-driving-action) infra landed + chain real-verified; GROUNDED accept
         gated on ONE approved spine-allowlist predicate. BYO-MODEL proven ×3 families; BYO-ROBOT go2+g1.
owns:    hardware/sim/scene_builder.py (extra_geoms), hardware/sim/mujoco_g1.py (mat const + get_camera_fovy),
         perception/ground_projection.py (+test), scratchpad/g1_{vln_probe,mat_probe,vln_chain_probe,vln_redteam}.py.
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (substitute: seg-GT oracle / deterministic probe). NOT loop-blocking.
         PRE-EXISTING: tests/unit/vcli/test_config_deepseek_provider.py 3 fails (provider naming drift) — untouched.
next:
  1. [GATE-THEN-BUILD] On near_object approval: register world-side near_object(colour) oracle (reads coloured-geom GT xy
     + robot GT pos) + add to _PREDICATE_ORACLES; wire an `approach(query)` native tool (detect→project→navigate, gated on
     has_base+camera, verify_hint near_object); ACCEPT g1 VLN on the bare REPL by NL ("走到蓝色的东西那里" GROUNDS via
     blue-mat GT + actor CAUSED; a no-such-colour / no-move command REFUTES). red-team the number.
  2. [FRONTIER, non-gated] 4th model family meta-llama/llama-3.3-70b via OpenRouter (preflighted OK) → N=4 plug-and-play.
  3. [FRONTIER, non-gated] arm-free `describe` via OpenRouter VLM (VisionJudge already OpenRouter-wired) — new g1 caption capability.
  4. [SPINE] D168 place-oracle identity+delta — LOAD-BEARING (D174 place leans on it). CEO gate, queue for Yusen.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **D178 near_object VLN predicate** (CONFIRMED gate, EXEC SUMMARY in DECISIONS D178): add a world-side
  `near_object(colour,radius)` verify oracle (coloured-object GT pos vs robot GT pos — actor-unauthored) AND list it in the
  kernel allowlist `evidence_classifier._PREDICATE_ORACLES`. Same category as `resting_on_receptacle` (D106-approved).
  grade() logic byte-unchanged; stricter-only. Unblocks a GROUNDED bare-REPL g1 VLN acceptance. → go/no-go.
- **D176 cmd_motion driver seam** (flagged, likely non-gate): enables g1 nav GROUNDED; grade() spine byte-unchanged.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only). LOAD-BEARING. → go/no-go.
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg → should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
