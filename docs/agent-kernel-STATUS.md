# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R4 LANDED + foreground real-verified, BARE-CLI acceptance (D60) — the LEARNED grounding-dino detector is ROUTED to g1's HEAD camera and LOCALIZES the red object, moat-graded, via bare cli + NL. TWO North-Star axes composed on ONE humanoid body: cross-EMBODIMENT (g1, D57-59) × cross-MODEL (grounding-dino, D48-50). Two NL turns on the literal cli.main REPL: "启动 g1 仿真" (→ "▸ sim start g1 ok 1.5s") then "找前面的红色的东西" (→ "native detect (query=找前面的红色的东西)" + "Loading weights: 978/978" = the LEARNED model genuinely loaded+ran inside the bare-cli child on g1's camera, NOT faked → "▸ detect → verify len(detect_objects()) > 0 ✓ (actor=NOT_GRADED)" → "verdict GROUNDED verified=True (1/1)"). Annotated frame /tmp/r4_g1_detect.png (Read back): 4 "a red object" boxes all centred, top 0.373; red-team pixel check — tight box redness 85.9 (R=198≫G,B) ON the red stool vs background −12.5 / floor 5.7, i.e. 3-15× redder = GENUINE localization, not background. HONEST nuance: graded GROUNDED + actor=NOT_GRADED (read-only marker — no causation claimed for perception, D50 spirit); moat NOT loosened (oracle reads the model's observation, never fabricates, no GT leaked to the means). Transcript /tmp/r4_g1_detect.txt; probe scripts/probe_r4_g1_detect.py. Commit 309d6b3 (WIP). Spine vector_os_nano/vcli/cognitive/ BYTE-UNCHANGED (3 ways).
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the North-Star axes (route-to-MODEL ✓ · cross-embodiment ✓ · their COMPOSITION ✓ now on g1 · live orchestration), moat-graded.
phase:   M4 cross-EMBODIMENT × cross-MODEL COMPOSED — the runtime routes a LEARNED model (grounding-dino) to a 2nd
         embodiment's (g1's) sensor + localizes, moat-graded, THROUGH THE BARE-CLI ACCEPTANCE INTERFACE. Both North-Star
         axes now demonstrated together on a humanoid. (M2 cross-model D48-50 + M3 cross-embodiment D57-59 both remain proven.)
owns:    vcli/worlds/robot.py (camera-presence capability gate + perception-fed detect_objects oracle for no-arm/camera),
         perception/g1_head_perception.py (G1HeadPerception.get_color_frame→g1 head cam), vcli/tools/sim_tool.py (_start_g1
         binds G1HeadPerception), vcli/native_loop.py (_NativeDetectTool + _registered_capability — bare-cli detect→learned
         capability), tests/vcli/test_r4_g1_detect_route.py (12), tests/vcli/test_detector_capability_registration.py (camera
         gate). scripts/probe_r4_g1_detect.py (bare-cli + annotated-frame acceptance). R1/R2/R3 artifacts on disk.
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 52 DECISIONS / since 7b220d9; R4 is world/perception-side only.)
doing:   G1 R4 — DONE + foreground real-verified via BARE cli.main REPL (D60). 4 NON-cognitive changes: (1) robot.py loosen
         register_capabilities from arm-presence → CAMERA-presence (_agent_has_camera, world-agnostic rule 7); (2) G1HeadPerception
         (get_color_frame→MuJoCoG1.get_camera_frame, mirrors Go2GraspPerception); (3) _start_g1 binds it; (4) native_loop
         _NativeDetectTool routes a bare-cli detect to the SAME registered grounding-dino capability (wins over classical
         DetectSkill on 'detect') + a perception-fed detect_objects() verify oracle for the no-arm case (reads agent._last_detection,
         never overwrites arm GT). The model LOADED + localized the red object inside the bare-cli child on g1's frame.

blocked: none — NOT a CEO gate (no new ROS2 interface / external dep / hardware / security; world+perception wiring only).
         HONEST shakiness for R5: (1) the box localizes "a red object" but does NOT yet DISCRIMINATE red-vs-green on g1 —
         R5 prove perceptual SELECTION (find the green vs the red). (2) Single deterministic spawn — R5 randomized starts for an
         honest detect success RATE (3-5 trials). (3) the FaceLLM token stream is faked (the detect turn is canned), same caveat
         as D46-D60 — R5 a LIVE-LLM producer emitting the detect route on g1. (4) g1 perceives only from spawn (object already
         framed) — R5 chain D59 nav + D60 detect so g1 DRIVES to a vantage THEN perceives (full plan→route→verify loop on g1).

next:    R5 (cross-EMBODIMENT × cross-MODEL, evolve) — bundle: (a) navigate-THEN-detect on g1 via bare cli NL — chain the D59
         nav (g1 walks to a vantage) with the D60 detect (localize there), closing the full orchestration loop on the humanoid;
         (b) colour/named DISCRIMINATION (find GREEN vs RED) to prove perceptual selection, not "something red exists";
         (c) randomized g1 spawn/heading → honest detect success RATE (3-5 trials) via the bare cli; (d) consider a LIVE-LLM
         producer round (no faked token stream) on g1. Real-verify in the sim + Read the annotated frame every round.
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
