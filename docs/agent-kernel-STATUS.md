# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R8 — obstacle-aware navigate_to via visibility-graph planner (g1_vgraph recovered, obstacles_from_model for go2-room scene, _walk_to_waypoint chain refactor). Planner routes AROUND pick_table/walls/furniture. 32 offline unit tests pass (12 vgraph + 20 new). mujoco_g1.py 1093 LOC. Spine BYTE-UNCHANGED. Awaiting lead sim-verify. Previous: G1 R7 — g1's FIRST HONEST GROUNDED PERCEPTION (D63). The HONEST redemption of R4's false green: g1 (camera, NO arm → no weld) now reaches a LEGITIMATE GROUNDED via a GT-backed PERCEPTION MATCH, verified against INDEPENDENT sim ground truth (NOT a self-read), through the bare-cli REPL. NEW (all WORLD-side; spine BYTE-UNCHANGED): (1) MuJoCoG1.get_object_positions() — sim GT, mirrors Piper; (2) depth_projection.world_to_pixel() — world→pixel (kept, unused by the live oracle — see below); (3) vcli/worlds/g1_perception_oracle.detection_matches_gt(target, tol) — the verify oracle: independent GT = a MuJoCo SEGMENTATION render (renderer's own geom-id image, never shown to the detector); claim = the detector's box on RGB-only; returns True IFF a box center is within tol px of the matching-colour segmentation centroid. NOT len(detect_objects())>0; NOT a self-read. (4) RobotWorld.build_verify_namespace binds it ONLY for a camera+live-MuJoCo, arm-less base (g1 shape); (5) _NativeDetectTool emits the matched verify hint. HONEST PIVOT (recorded honestly): the freejoint pickables are OCCLUDED in g1's spawn view (segmentation: 0 px) — the red the detector sees is the static red bar STOOL — AND the head-camera pose-vs-frame did not reconcile under a pinhole world_to_pixel (44° depression rendering at mid-frame), so a hand-rolled projection was UNRELIABLE. SWITCHED to the segmentation render: convention-free, renderer-native, strictly MORE independent + reliable. REAL-VERIFY (bare cli.main, foreground, torn down; transcripts /tmp/r7_g1_grounded.txt): RED `▸ detect → verify detection_matches_gt('红色') == True ✓ (actor=NOT_GRADED)` → `verdict GROUNDED verified=True (1/1 grounded)`; REFUTATION GREEN (same frame, only colour differs, green NOT in view) `▸ detect → verify detection_matches_gt('绿色') == True · (actor=NOT_GRADED)` → `verdict RAN verified=False (0/1 grounded)`. Eyes-on frame /tmp/r7_g1_grounded.png (box on the red stool + cyan GT seg-centroid coincide); refute frame /tmp/r7_g1_refute.png (g1 faces blank wall, no GT crosshair). 102 passed (incl. 8 R7 honesty-contract tests). NOT a CEO gate. Spine vcli/cognitive/ BYTE-UNCHANGED across 63 decisions.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the North-Star axes (route-to-MODEL ✓ · cross-embodiment ✓ · their COMPOSITION ✓ on g1 · HONEST GROUNDED perception on a 2nd body ✓ · live orchestration), moat-graded.
phase:   M4 cross-EMBODIMENT × cross-MODEL COMPOSED + HONEST GROUNDED PERCEPTION — the runtime routes a LEARNED model (grounding-dino)
         to a 2nd embodiment's (g1's) sensor, localizes the red object, and that localization GROUNDS against INDEPENDENT sim GT
         (segmentation render) through the bare-cli interface (red → GROUNDED; green refutation → RAN). g1's first non-RAN grade, EARNED.
         (M2 cross-model D48-50 + M3 cross-embodiment D57-59 + the R6 audit-clean moat all remain proven.)
owns:    vcli/worlds/g1_perception_oracle.py (NEW — detection_matches_gt, segmentation-GT match), vcli/worlds/robot.py (binds the
         oracle for the g1 shape), hardware/sim/mujoco_g1.py (get_object_positions GT accessor; 845 LOC), perception/depth_projection.py
         (world_to_pixel), vcli/native_loop.py (adaptive verify hint), tests/vcli/test_r7_g1_gt_match.py (8 honesty tests),
         scripts/r7_g1_grounded_demo.py + scripts/r7_probe.py (R7 demos), docs/DECISIONS.md (D63), docs/agent-kernel-STATUS.md.
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 63 DECISIONS / since 7b220d9; R7 = world-side oracle + tests + sim accessor only.)
doing:   G1 R7 — DONE. Honest GROUNDED by construction: the spine grades `detection_matches_gt('x') == True` GROUNDED ONLY when the
         oracle returns True, and the oracle returns True ONLY when the detector's box matches the INDEPENDENT segmentation GT. Both
         verdicts proven in the real sim AND through the bare cli.main REPL (red→GROUNDED, green→RAN). Eyes-on frames Read back.

blocked: none — NOT a CEO gate (no new ROS2 interface / external dep / hardware / security; world-side oracle + sim GT accessor only).
         HONEST state after R7: (1) GROUNDED is EARNED via segmentation-GT match (the firewall holds: detector sees only RGB). (2) The
         match is COLOUR-discriminating (red grounds, green/blue refute — they are not in view). (3) Single deterministic spawn — no
         multi-trial success RATE yet. (4) The hand-rolled world_to_pixel is UNRELIABLE for g1's head camera (kept but unused by the
         live oracle) — needs the pose-vs-frame convention nailed before any projection-based oracle. (5) g1 navigate_to is
         OPEN-SPACE-only (no obstacle avoidance). (6) The FaceLLM token stream is faked (caveat D46-D63) — a LIVE-LLM producer on g1 open.

next:    R8 (evolve — pick highest ambition×feasibility): (a) MULTI-TRIAL honest success RATE — randomized g1 spawn/heading, report
         the GROUNDED detect rate across 3-5 trials (R7 was one deterministic spawn); (b) LIVE-LLM producer on g1 (drop the faked
         token stream — the standing D46-D63 caveat) emitting the detect+verify route; (c) obstacle-aware g1 nav (recover the vgraph
         router so navigate_to avoids the pick_table); (d) nail the head-camera world_to_pixel convention so a projection oracle can
         DISCRIMINATION (GREEN vs RED) for perceptual selection; (d) randomized g1 spawn → honest detect success RATE (3-5 trials).
         Real-verify in the sim + Read the annotated frame every round.
         Gated leaps (CEO queue): re-plan strategy_params-preservation (SPINE — D52), actor-causation→cmd_vel for GROUNDED
         base-nav (SPINE — D14), explore (TARE), VLN (SysNav), merge→master.
         Repro: `.venv` needs `timm>=1.0`; grounding-dino-tiny weights cached at HF_HOME (offline OK); set MUJOCO_GL=egl.
         Bare vector-cli + NL = ONLY acceptance; spine only STRICTER; never trust skill.success / sub-agent claims.


## G1 cross-embodiment (durable summary; round narrative in DECISIONS D57-D62 + git)
- g1 (12-dof RL gait) STANDS + WALKS in the go2 room with lidar+camera (D57-58), is a MOAT-GRADED routable
  embodiment with go2 parity via the SAME world seam — NO g1-specific oracle (D59, at_position→RAN honest, D14).
- The learned grounding-dino detector ROUTES to g1's head camera + localizes the red object (D60); R4's self-certifying
  GROUNDED was a false-green (RAN-honest after D50/D61), then R7 (D63) made it a LEGITIMATE GROUNDED via an INDEPENDENT
  GT match: `detection_matches_gt` checks the box against a MuJoCo segmentation render (red→GROUNDED, green→RAN).
- Wiring (all NON-cognitive, spine byte-unchanged): `vcli/worlds/robot.py` (`_agent_has_camera` gate, NO self-read
  oracle), `perception/g1_head_perception.py` (get_color_frame→g1 head cam), `vcli/tools/sim_tool.py` (`_start_g1`),
  `vcli/native_loop.py` (`_NativeDetectTool`→registered capability; NO self-stash since R6), `sensors/g1_lidar.py`,
  `hardware/sim/mujoco_g1.py` (797 LOC). Demo: `scripts/g1_capstone_demo.py` (bare-cli 3-turn start→nav→detect).

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
