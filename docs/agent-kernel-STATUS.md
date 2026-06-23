# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R5 CORRECTION — MOAT INTEGRITY RESTORED (D61). Red-team caught R4's g1-detect GROUNDED as a FALSE GREEN: the `detect_objects()` oracle R4 added (`_make_perceived_detections`, worlds/robot.py) read `agent._last_detection` = the LEARNED detector's OWN stashed boxes (the MEANS' output), so `len(detect_objects())>0` was a TAUTOLOGY (the detector certifying ITSELF) and the R1 evidence gate graded GROUNDED — a moat violation in SPIRIT (rule 5: the sandbox only gets stricter). FIX (world-side; spine BYTE-UNCHANGED): removed that self-read oracle + its camera-no-arm binding. With no `detect_objects` in the g1 verify namespace, `classify_verify_expr("len(detect_objects())>0", oracle_names)` finds no oracle → returns RAN (fail-closed to the honest D50 grade) via the classifier's existing single-sourced `oracle_names` — NO spine edit. KEPT: grounding-dino still REGISTERS for g1 (camera guard `_agent_has_camera`), still ROUTES to g1's head camera, still LOCALIZES — cross-EMBODIMENT × cross-MODEL holds, now RAN-honest. SIBLING AUDIT: `_make_perceived_detections` was the ONLY world-side self-read oracle; arm/base oracles all read INDEPENDENT SIM GT (left, legitimately GROUNDED). RE-VERIFY: bare cli.main two-turn REPL, transcript /tmp/r5_g1_detect_ran.txt — verdict now RAN (not GROUNDED), detector still routed+localized. Tests: replaced the 2 false-green asserts with no-self-read + RAN-classifies proofs; 16 targeted + 89 cognitive green. NOT a CEO gate. Spine vector_os_nano/vcli/cognitive/ BYTE-UNCHANGED.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the North-Star axes (route-to-MODEL ✓ · cross-embodiment ✓ · their COMPOSITION ✓ now on g1 · live orchestration), moat-graded.
phase:   M4 cross-EMBODIMENT × cross-MODEL COMPOSED + MOAT CORRECTED — the runtime routes a LEARNED model (grounding-dino) to a
         2nd embodiment's (g1's) sensor + localizes, THROUGH THE BARE-CLI ACCEPTANCE INTERFACE, now graded RAN-honest (the R4
         false-green GROUNDED removed, D61). Both North-Star axes demonstrated together on a humanoid, honestly. (M2 cross-model
         D48-50 + M3 cross-embodiment D57-59 both remain proven.)
owns:    vcli/worlds/robot.py (camera-presence capability gate; NO self-read detect_objects oracle — removed R5), tests/vcli/
         test_r4_g1_detect_route.py (no-self-read + RAN-classifies proofs), docs/DECISIONS.md (D61), docs/agent-kernel-STATUS.md.
         KEPT from R4: perception/g1_head_perception.py (G1HeadPerception.get_color_frame→g1 head cam), vcli/tools/sim_tool.py
         (_start_g1 binds G1HeadPerception), vcli/native_loop.py (_NativeDetectTool + _registered_capability — bare-cli
         detect→learned capability). scripts/probe_r4_g1_detect.py (acceptance harness; R5 re-driven). R1/R2/R3 artifacts on disk.
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 53 DECISIONS / since 7b220d9; R5 fix is world-side + tests only.)
doing:   G1 R5 CORRECTION — DONE + foreground re-verified via BARE cli.main REPL (D61). Removed `_make_perceived_detections` and
         its camera-no-arm `ns["detect_objects"]` binding in RobotWorld.build_verify_namespace. The g1 detect verify
         (`len(detect_objects())>0`) now has no oracle in the live namespace → classify_verify_expr returns RAN (fail-closed to
         D50-honest), with NO spine change (the classifier's oracle_names is single-sourced from the namespace). Detector still
         registers/routes/localizes on g1's head camera (the genuine cross-axis composition, KEPT). Sibling-oracle audit: no
         other world-side self-read oracle (arm/base read independent SIM GT).

blocked: none — NOT a CEO gate (no new ROS2 interface / external dep / hardware / security; world-side moat correction only).
         HONEST shakiness for R6: (1) detection is now correctly RAN — a LEGITIMATE GROUNDED for detection would need a
         GT-BACKED SPATIAL MATCH (the detector's box back-projects to where SIM GT get_object_positions says the object is, an
         oracle INDEPENDENT of the means) — a possible R6, NOT done now. (2) g1 detect still localizes "a red object" without
         red-vs-green DISCRIMINATION — R6 prove perceptual SELECTION. (3) Single deterministic spawn — R6 randomized starts for an
         honest success RATE. (4) the FaceLLM token stream is faked (caveat D46-D61) — R6 a LIVE-LLM producer on g1. (5) navigate-
         THEN-detect on g1 (chain D59 nav + the now-RAN detect) still closes the full plan→route→verify loop on the humanoid.

next:    R6 (cross-EMBODIMENT × cross-MODEL, evolve) — bundle: (a) navigate-THEN-detect on g1 via bare cli NL — chain the D59
         nav (g1 walks to a vantage) with the now-RAN-honest detect (localize there), closing the full orchestration loop on the
         humanoid; (b) the GT-BACKED SPATIAL-MATCH oracle so detection can LEGITIMATELY ground (box back-projects to SIM-GT
         object position — independent of the means; the honest way to a GROUNDED detect); (c) colour/named DISCRIMINATION
         (find GREEN vs RED) to prove perceptual selection; (d) randomized g1 spawn → honest detect success RATE (3-5 trials);
         (e) consider a LIVE-LLM producer round on g1. Real-verify in the sim + Read the annotated frame every round.
         Gated leaps (CEO queue): re-plan strategy_params-preservation (SPINE — D52), actor-causation→cmd_vel for GROUNDED
         base-nav (SPINE — D14), explore (TARE), VLN (SysNav), merge→master.
         Repro: `.venv` needs `timm>=1.0`; grounding-dino-tiny weights cached at HF_HOME (offline OK); set MUJOCO_GL=egl.
         Bare vector-cli + NL = ONLY acceptance; spine only STRICTER; never trust skill.success / sub-agent claims.


## G1 R4 WIP floor (2026-06-23) — learned detector routed to g1's head camera
Compose cross-EMBODIMENT × cross-MODEL on g1. NON-cognitive (spine byte-unchanged). Commit 309d6b3.
- `vector_os_nano/vcli/worlds/robot.py` — `_agent_has_camera` gate (was arm-only) + perception-fed
  `detect_objects()` oracle for the no-arm/camera case (reads `agent._last_detection`; never fabricates).
- `vector_os_nano/perception/g1_head_perception.py` — `G1HeadPerception.get_color_frame()` → MuJoCoG1.get_camera_frame.
- `vector_os_nano/vcli/tools/sim_tool.py` — `_start_g1` binds `agent._perception = G1HeadPerception(g1)`.
- `vector_os_nano/vcli/native_loop.py` — `_NativeDetectTool` + `_registered_capability`: bare-cli `detect`
  routes to the SAME registered grounding-dino capability (wins over classical DetectSkill); stashes boxes.
- `tests/vcli/test_r4_g1_detect_route.py` (12) + updated `test_detector_capability_registration.py` (camera gate).
- `scripts/probe_r4_g1_detect.py` — bare cli.main two-turn REPL + annotated-frame acceptance.
REAL-VERIFY: bare-cli "启动 g1 仿真" → "找前面的红色的东西" → grounding-dino loaded+ran on g1's head cam → verdict
GROUNDED (actor=NOT_GRADED, read-only). Frame /tmp/r4_g1_detect.png: boxes ON the red stool (redness 85.9 vs bg −12.5).
R5: navigate-THEN-detect on g1; red-vs-green discrimination; randomized spawns → success rate; live-LLM producer.

## Standing facts (durable)
- **Branch `feat/orchestrator-redesign`** off master; `feat/playground-vln` is ABANDONED (never touch/delete).
- **Honest-verify axis** (the moat's core): a step grades GROUNDED only when a deterministic predicate
  reads an oracle the ACTOR cannot author (actor-causation + structural classifier). The sandbox may only get
  STRICTER (rule 5). vcli/cognitive/ BYTE-UNCHANGED since 7b220d9 (verified 4 ways R34).
- **Cross-MODEL seam (D48):** engine.py builds a CapabilityRegistry, calls world.register_capabilities, threads
  names→StrategySelector + registry→GoalExecutor. A world registers a Capability(kind=chat|detector|planner|vla|…);
  the spine grades it, it never self-certifies. First real entry: the grounding-dino `detect` capability.
- **Acceptance = bare `vector-cli` + NL only** (cli.main PTY asserting the verify VERDICT); `VECTOR_FAKE_LLM`
  fakes ONLY the network LLM. PTY harness needs HF_HOME pinned for the offline detector (D48 note).
- **Native nav routes through the avoidance planner** (D14, `navigate(x,y)`→FAR); `at_position` grades
  UNCAUSED→RAN until actor-causation extends to cmd_vel (honest, spine byte-unchanged).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- **DEP `timm>=1.0` (1.0.27) — CEO-APPROVED 2026-06-23.** Added to pyproject + .venv to make EdgeTAM actually LOAD
  (its undeclared backbone; EdgeTAM never loaded across the grasp campaign D17-D51 → masks were box-rect). Standard
  PyTorch-image-models lib; EdgeTAM backbone repvit_m1.dist_in1k fetches from HF once then caches. No longer a gate.
- Merge/release `feat/orchestrator-redesign` → master: **CEO-APPROVED + DONE + PUSHED 2026-06-23** (FF, 135 commits;
  origin/master 4158286→cd7029a). cross-MODEL (D48-D50) + the moat are live on the shared GitHub. Release gate CLOSED.
- cross-EMBODIMENT (g1: removed, zero python — large rebuild) ; nav→FAR + explore→TARE (cmd_vel causation +
  nav-stack colcon bring-up, DQ-15) ; VLN→SysNav venv (DQ-16). New external deps / new-or-changed interfaces /
  hardware / security. Real SO-101 arm acceptance gated on `ls /dev/ttyACM*` (absent — sim only).
