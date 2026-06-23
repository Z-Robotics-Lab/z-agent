# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R2 LANDED + foreground real-verified (D58) — G1 humanoid WALKS to commanded points in the go2 apartment room via a 12-DOF RL policy (motion.pt, 50 Hz) WITHOUT FALLING, and lidar+camera UPDATE while moving. Replaced R1's stand-only 29-DOF menagerie model with the matched pair g1_12dof.xml + motion.pt (the only policy-walkable combo; lead spiked it first: 2.70m in 6s, z 0.765-0.791). VERDICT (probe scripts/probe_r2_g1_walk.py, MUJOCO_GL=egl, torn down): 2/2 trials reached (deterministic=1 real sample), base-z 0.770-0.793 throughout (no fall), net 1.04m/path 2.49m over two legs (pivot+walk, pivot+walk). Sensors change: lidar min 3.0->1.77->2.05m, near-pts(<2m) 194->1021->180; head camera VISIBLY distinct at start (kitchen-through-doorway) / mid (near-blank south wall) / arrival (doorway new angle, red object) — lead Read all 3 PNGs. NL-switch DONE (routing already supported g1; added prompt line; verified "启动 g1 仿真"->tool_use->sim_type=g1->_start_g1). 5/5 unit tests. Commit a7afaf9 (WIP floor). Spine vector_os_nano/vcli/cognitive/ BYTE-UNCHANGED.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M3 cross-EMBODIMENT — G1 humanoid added as a 3rd embodiment (alongside go2 / go2+arm), standing in the SAME
         go2 room with working lidar+camera. The cross-embodiment North-Star axis now has its first real 2nd body-class
         beyond the quadruped. (M2 cross-model — learned detector routed-to BY THE PRODUCER, D48-D50 — remains proven.)
owns:    hardware/sim/mujoco_g1.py (R2: 12-DOF gait + room scene + navigate_to + lidar + camera),
         hardware/sim/mjcf/g1/scene_g1_12dof_room.xml (generated), tests/unit/hardware/sim/test_g1_room.py.
         R1 artifacts preserved: build_g1.py, g1.xml, scene_g1_room.xml (29-DOF stand scene still on disk).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 57 decisions; g1 is sim/world-side only — no spine edit.)
doing:   G1 R2 — DONE + foreground real-verified (D58). g1 WALKS to commanded points without falling + sensors update
         while moving + NL-switch wired. 12-DOF g1_12dof.xml + motion.pt policy (only walkable combo) attached into the go2
         room; single-threaded synchronous gait; absolute mesh paths (dual-meshdir fix, D57 lesson recurred). Combined-scene
         offsets: pelvis_qpos_adr=21, leg_qpos=28:40, ctrl=0:12 (a _G1Offsets class — the flat-spike's qpos[7:]/qvel[6:]
         would be WRONG in the room scene). Public API: connect/close/walk/navigate_to/set_velocity/stop/get_position/
         get_base_height/get_heading/get_lidar_scan/get_camera_frame/get_camera_pose. probe_r2_g1_walk.py is the acceptance.

blocked: none — not a CEO gate (sim asset + in-sim locomotion + a prompt-string add; no new ROS2 interface, no new external
         dep). HONEST shakiness for R3: (1) navigate_to is OPEN-LOOP straight-line — NO obstacle avoidance (the recovered
         _nav_controller/g1_vgraph were not in HEAD, not recovered). It walks STRAIGHT INTO the table/walls if commanded
         through them — the probe HAD to route around the pick_table (which blocks +x at x~=10.80) to reachable open points.
         R3: recover/inline the vgraph obstacle router. (2) Only 1 REAL sample (deterministic, no randomized start) — R3 add
         randomized spawns for an honest success RATE. (3) Table doesn't enter close LIDAR range at the standoff (it's a camera
         target here) — R3 approach the table front from the open south side. (4) mujoco_g1.py is 917 lines (>800) — extract
         the lidar method. (5) Gait tested only on open floor — R3 walk a longer cross-room path over rugs/thresholds. (6) The
         29-DOF menagerie model is set aside for locomotion (no matched policy) — a 29dof gait needs its own trained policy.
next:    R3 (cross-EMBODIMENT, evolve) — bundle: (a) g1 OBSTACLE-AWARE navigate_to — recover/inline the vgraph router (or
         enumerate obstacles + plan around them) so g1 walks to ANY commanded point incl. the pick_table front without
         colliding/stalling; (b) randomized spawns → honest success RATE (say 3-5 starts); (c) a longer cross-room walk
         (through the west doorway / over the hall rug) to stress gait on non-flat geometry; (d) then a cross-embodiment TASK
         graded by the moat: g1 navigates to + PERCEIVES an object via bare vector-cli NL (close the orchestration loop on the
         humanoid). Real-verify in the sim + Read a moving render every round.
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
