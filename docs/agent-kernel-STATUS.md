# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R6 REVIEW — MOAT AUDITED CLEAN + TIDY + HONEST CAPSTONE (D62). Post-violation consolidation after the D61 false-green fix. INDEPENDENT honesty audit (re-done from scratch + a 2nd independent read-only sweep, NOT trusting R5's audit): swept EVERY GROUNDED-eligible oracle that can enter the live verify namespace (engine._build_verifier_namespace + DevWorld/RobotWorld/PlaygroundWorld.build_verify_namespace → arm_sim_oracle + go2_sim_oracle; there is NO g1-specific oracle — g1 uses the SAME base path). VERDICT: every oracle reads INDEPENDENT SIM/disk GT, NONE reads the means' own output. arm detect/describe/holding/placed/at_home → get_object_positions/FK/gripper.is_holding/get_joint_positions (GT); base at_position/facing/visited → get_position/get_heading (GT, downgraded RAN via UNCAUSED for nav); dev file/grep/path/tests → disk (GT); Phase-3 last_seen/find_object/room_coverage → SceneGraph/ObjectMemory world-model (GT, not single-action self-read). No self-read (B) / trivial-true (C) GROUNDED-eligible oracle exists — the D61 fix HOLDS, moat clean of false-greens. ONE finding fixed world-side (spine BYTE-UNCHANGED): `agent._last_detection` (write at native_loop.py:248) was ORPHANED after D61 (no oracle reads it) + its comment was STALE — REMOVED the write + replaced the comment with a moat-discipline warning so no future round re-wires the means' output into verify; updated 2 R4 tests to assert `not hasattr(agent,"_last_detection")`. TIDY: deleted 15 scratch round-probes (git is the archive); kept scripts/g1_capstone_demo.py (consolidated 3-turn demo). Fast moat-semantics suite 71 passed/1 xfail. NOT a CEO gate. Spine vector_os_nano/vcli/cognitive/ BYTE-UNCHANGED across 62 decisions.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the North-Star axes (route-to-MODEL ✓ · cross-embodiment ✓ · their COMPOSITION ✓ now on g1 · live orchestration), moat-graded.
phase:   M4 cross-EMBODIMENT × cross-MODEL COMPOSED + MOAT AUDITED CLEAN — the runtime routes a LEARNED model (grounding-dino) to a
         2nd embodiment's (g1's) sensor + localizes + navigates, THROUGH THE BARE-CLI ACCEPTANCE INTERFACE, graded RAN-honest (nav
         + detect both correctly RAN; zero false-greens, audited from scratch R6). Both North-Star axes demonstrated together on a
         humanoid, honestly. (M2 cross-model D48-50 + M3 cross-embodiment D57-59 both remain proven.)
owns:    vcli/native_loop.py (removed orphaned `_last_detection` self-read stash + moat-discipline comment — R6), tests/vcli/
         test_r4_g1_detect_route.py (asserts no self-stash), docs/DECISIONS.md (D62), docs/agent-kernel-STATUS.md,
         scripts/g1_capstone_demo.py (kept; consolidated 3-turn cross-embodiment demo, supersedes probe_r1..r5).
         KEPT from R3-R5: vcli/worlds/robot.py (camera-presence gate; NO self-read oracle), perception/g1_head_perception.py,
         vcli/tools/sim_tool.py (_start_g1), the _NativeDetectTool route, sensors/g1_lidar.py, hardware/sim/mujoco_g1.py (797 LOC).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 62 DECISIONS / since 7b220d9; R6 = audit + world-side tidy + tests only.)
doing:   G1 R6 REVIEW — DONE. Independent honesty audit (re-done from scratch + 2nd independent sweep): every GROUNDED-eligible
         oracle in the live verify namespace reads independent SIM/disk GT — NO self-read, NO trivial-true; the D61 fix holds, moat
         clean. Fixed the one residue (orphaned `_last_detection` write + stale comment, world-side, spine byte-unchanged). Tidied
         15 scratch probes. Capstone: bare-cli g1 start→nav→detect, foreground-verified (transcript /tmp/r6_g1_capstone.txt + frame).

blocked: none — NOT a CEO gate (no new ROS2 interface / external dep / hardware / security; world-side audit + tidy only).
         HONEST state after R6: (1) g1 detect correctly grades RAN — a LEGITIMATE GROUNDED needs a GT-BACKED SPATIAL MATCH (box
         back-projects to where SIM GT get_object_positions says the object is, independent of the means) = R7. (2) g1 detect
         localizes "a red object" without red-vs-green DISCRIMINATION — still open. (3) Single deterministic spawn — no honest
         success RATE yet. (4) g1 navigate_to is OPEN-SPACE-only (no obstacle avoidance — walks into the pick_table on +x). (5) the
         FaceLLM token stream is faked (caveat D46-D62) — a LIVE-LLM producer on g1 still open.

next:    R7 (cross-EMBODIMENT × cross-MODEL, evolve — pick the highest ambition×feasibility): (a) the GT-BACKED SPATIAL-MATCH oracle
         so detection can LEGITIMATELY ground — the detector's box back-projects to the SIM-GT object position (independent of the
         means; the ONLY honest path to a GROUNDED detect; the natural R7 after R6 proved the moat clean); OR (b) obstacle-aware g1
         nav (recover the vgraph router so navigate_to avoids the pick_table, not open-space-only); plus (c) colour/named
         DISCRIMINATION (GREEN vs RED) for perceptual selection; (d) randomized g1 spawn → honest detect success RATE (3-5 trials).
         Real-verify in the sim + Read the annotated frame every round.
         Gated leaps (CEO queue): re-plan strategy_params-preservation (SPINE — D52), actor-causation→cmd_vel for GROUNDED
         base-nav (SPINE — D14), explore (TARE), VLN (SysNav), merge→master.
         Repro: `.venv` needs `timm>=1.0`; grounding-dino-tiny weights cached at HF_HOME (offline OK); set MUJOCO_GL=egl.
         Bare vector-cli + NL = ONLY acceptance; spine only STRICTER; never trust skill.success / sub-agent claims.


## G1 cross-embodiment (durable summary; round narrative in DECISIONS D57-D62 + git)
- g1 (12-dof RL gait) STANDS + WALKS in the go2 room with lidar+camera (D57-58), is a MOAT-GRADED routable
  embodiment with go2 parity via the SAME world seam — NO g1-specific oracle (D59, at_position→RAN honest, D14).
- The learned grounding-dino detector ROUTES to g1's head camera + localizes the red object (D60); its grade is
  RAN-honest (read-only perception; D50/D61 — the R4 self-certifying GROUNDED was a false-green, removed).
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
