# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R3 LANDED + foreground real-verified, BARE-CLI acceptance (D59) — g1 is now a MOAT-GRADED ROUTABLE EMBODIMENT (parity with go2). The SAME orchestration drives g1 via the literal bare cli.main REPL: two NL turns "启动 g1 仿真" (→ "▸ sim start g1 ok 0.9s", NL embodiment-switch) then "走到坐标 (10.0,1.5)" (→ "native navigate (x=10.0,y=1.5)" → g1.navigate_to RL gait → "▸ navigate → verify at_position(10.0,1.5) ✓ (actor=UNCAUSED)" → "verdict RAN verified=False (0/1 grounded)"). The `✓` = at_position PREDICATE TRUE = g1 PHYSICALLY ARRIVED (moat read g1's pelvis pose); RAN (not GROUNDED) is the CORRECT HONEST grade — base cmd_vel/gait is not actor-causation-gated (D14), identical to go2; SUCCESS not failure. Probe corroborates (/tmp/r3_g1_nav_probe.json): (10,3,z.793)→(10.03,1.83,z.773), dist 1.5→0.331m, no fall (z min .773), reason=arrived. THE REAL FINDING: the wiring was already body-agnostic (RobotWorld for any base; at_position reads get_position generically; navigate routes via getattr) — the ONLY gap was a return-contract mismatch (g1 navigate_to returned a dict→always-truthy vs go2's bool). FIX = _G1NavResult(dict) with __bool__==reached + timeout kwarg; NO world-wiring change needed. De-sloppify: lidar extracted to sensors/g1_lidar.py, mujoco_g1.py 917→797 (<800). Transcript /tmp/r3_g1_nav.txt. Commit f991e27. Spine vector_os_nano/vcli/cognitive/ BYTE-UNCHANGED.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M3 cross-EMBODIMENT — G1 humanoid PROVEN as a moat-graded routable embodiment THROUGH THE ACCEPTANCE INTERFACE
         (bare cli + NL → switch → command → moat grades), parity with go2. The cross-embodiment North-Star axis is now
         demonstrated end-to-end on a 2nd body-class. (M2 cross-model — learned detector routed-to BY THE PRODUCER, D48-D50 —
         remains proven.)
owns:    hardware/sim/mujoco_g1.py (797 ln: 12-DOF gait + room scene + navigate_to(contract-parity) + camera; lidar in
         sensors/g1_lidar.py), hardware/sim/sensors/g1_lidar.py (extracted mj_ray scan), tests/unit/hardware/sim/test_g1_room.py
         (6 tests incl. nav-result-contract), scripts/probe_r3_g1_nav.py (bare-cli + probe acceptance). R1/R2 artifacts on disk.
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 59 decisions; g1 is sim/world-side only — no spine edit.)
doing:   G1 R3 — DONE + foreground real-verified via BARE cli.main REPL (D59). g1 is a moat-graded routable embodiment:
         resolve_for_agent wraps any base in RobotWorld; at_position reads get_position generically; navigate routes via
         getattr — all ALREADY body-agnostic. ONLY fix needed: navigate_to return-contract (g1's dict was always-truthy vs
         go2's bool) → _G1NavResult(dict).__bool__==reached + timeout kwarg + **_ignored (absorbs go2's on_progress); existing
         .get() callers unchanged. Lidar mj_ray extracted to sensors/g1_lidar.py (byte-identical); mujoco_g1.py 917→797.
         Transcript /tmp/r3_g1_nav.txt: verdict RAN verified=False (honest D14 grade — at_position ✓ = arrived, UNCAUSED).

blocked: none — not a CEO gate (a return-contract fix + a code-move refactor; no new ROS2 interface, no new external dep).
         HONEST shakiness for R4: (1) navigate_to still OPEN-LOOP straight-line — NO obstacle avoidance (target chosen in
         clear south space). R4: recover/inline the vgraph obstacle router so g1 reaches ANY point incl. through-furniture.
         (2) Deterministic single sample — R4 add randomized spawns for an honest success RATE (3-5 starts). (3) at_position
         is RAN not GROUNDED — making g1 base-nav GROUNDED needs actor-causation extended to cmd_vel = a SPINE/CEO change
         (D14, GATED — do NOT do autonomously). (4) Gait untested over rugs/thresholds — R4 walk a longer cross-room path.
next:    R4 (cross-EMBODIMENT, evolve) — bundle: (a) g1 OBSTACLE-AWARE navigate_to — recover/inline the vgraph router (or
         enumerate obstacles + plan around them) so g1 walks to ANY commanded point incl. the pick_table front without
         colliding/stalling; (b) randomized spawns → honest success RATE (3-5 starts) via the bare cli; (c) a longer cross-room
         walk (through the west doorway / over the hall rug) to stress gait on non-flat geometry; (d) a cross-embodiment
         PERCEPTION task on g1 via bare cli NL: navigate-to + detect/describe an object (route the detector capability) —
         close the orchestration loop further on the humanoid. Real-verify in the sim + Read a moving render every round.
         Gated leaps (CEO queue): re-plan strategy_params-preservation (SPINE — D52), cross-EMBODIMENT (g1), explore
         (TARE), VLN (SysNav), merge→master.
         ALSO record for reproducibility: `.venv` must have `timm` (uv pip install 'timm>=1.0'); EdgeTAM backbone
         repvit_m1.dist_in1k fetches from HF on first load (network needed once, then cached).
         Bare vector-cli + NL = ONLY acceptance; spine only STRICTER; never trust skill.success / sub-agent claims.


## G1 R1 WIP floor (2026-06-23)
G1 humanoid placed in the go2 apartment room via MjSpec attach (same pattern as go2_piper).
- `vector_os_nano/hardware/sim/mjcf/g1/build_g1.py` — builds g1.xml: absolute mesh paths + head_rgb camera
- `vector_os_nano/hardware/sim/mjcf/g1/g1.xml` — generated, include-safe
- `vector_os_nano/hardware/sim/mujoco_g1.py` — MuJoCoG1: scene builder + stand + lidar + camera
- `vector_os_nano/hardware/sim/mjcf/g1/scene_g1_room.xml` — generated combined scene
- `vector_os_nano/vcli/tools/sim_tool.py` — `_start_g1` wired, "g1" in sim_type enum
- `tests/unit/hardware/sim/test_g1_room.py` — 4/4 pass
- `scripts/probe_r1_g1_room.py` — lead's foreground 2s verify probe
Smoke: base_z=0.791m (stands), lidar n_returns=360 min=3.0m median=4.4m self_hits=0, cam mean=178.
Textures: builtin (gradient/checker) render; PNG furniture textures — texturedir is set, verify visually in foreground.
R2: NL embodiment-switch ("start g1 sim"), full bridge + ros2 topics, gait.

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
