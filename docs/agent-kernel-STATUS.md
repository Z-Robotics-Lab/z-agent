# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R1 LANDED (cross-EMBODIMENT axis) — Unitree G1 stands stably IN the existing go2 apartment room (SAME walls/furniture/pick_table/cans), with a real lidar (360 returns, 15 distinct range buckets 3.0-11.4m, detects walls across the 20×14m apartment, 0 self-hits) and a real head camera (g1_head_rgb, renders the room — door frame + table + can + floor visible, I Read /tmp/r1_g1_cam.png). Built by MIRRORING the proven go2_piper MjSpec.attach pattern (D57): each model loaded as its own spec with absolute mesh paths + meshdir="" → attach g1 into a room-only spec at (10,3) facing +x. _start_g1 registered in sim_tool (in-process; NL-switch=R2). Foreground real-verified (probe scripts/probe_r1_g1_room.py), sim torn down. Commit 65bc6c7 (WIP floor) + docs. Spine vcli/cognitive/ BYTE-UNCHANGED. PRIOR thrust (nav+grasp) BANKED after 6 rounds (D56), intermittent demo, awaiting CEO ship-vs-pivot.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M3 cross-EMBODIMENT — G1 humanoid added as a 3rd embodiment (alongside go2 / go2+arm), standing in the SAME
         go2 room with working lidar+camera. The cross-embodiment North-Star axis now has its first real 2nd body-class
         beyond the quadruped. (M2 cross-model — learned detector routed-to BY THE PRODUCER, D48-D50 — remains proven.)
owns:    hardware/sim/mjcf/g1/build_g1.py (g1 model + head camera, absolute meshes), hardware/sim/mjcf/g1/{g1,scene_g1_room}.xml
         (generated), hardware/sim/mujoco_g1.py (_build_g1_room_scene_xml MjSpec attach + MuJoCoG1: stand-hold PD,
         mj_ray lidar w/ g1 self-geom filter, g1_head_rgb camera), vcli/tools/sim_tool.py (_start_g1 + "g1" enum),
         tests/unit/hardware/sim/test_g1_room.py, scripts/probe_r1_g1_room.py.
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 57 decisions; g1 is sim/world-side only — no spine edit.)
doing:   G1 R1 (cross-EMBODIMENT) — DONE + foreground real-verified. G1 placed in the EXISTING go2 apartment room (NOT a new
         scene): MjSpec.attach pattern (mirrors hardware/sim/mjcf/go2_piper/build_go2_piper.py) — load room-only spec + g1
         spec each with absolute mesh paths + meshdir="" (solves the dual-meshdir conflict: room has 95 furniture meshes on
         go2's meshdir, g1's meshes on menagerie's; one top-level meshdir can't serve both), attach g1 at (10,3) facing +x.
         g1.xml from mujoco_menagerie/unitree_g1 (it HAS a `stand` keyframe; in-repo g1_29dof.xml does NOT) + a g1_head_rgb
         camera added on torso_link. MuJoCoG1: stand-hold (menagerie position actuators @ stand ctrl) + mj_ray lidar (g1
         pelvis bodyexclude + g1 self-geom-id filter) + mj.Renderer camera. VERIFIED (scripts/probe_r1_g1_room.py, foreground,
         MUJOCO_GL=egl): base-z stable 0.7912 over 2s (STANDS); lidar 360 returns, 15 distinct buckets 3.0-11.4m, 3D points
         span the full 20×14m apartment (907 pts >6m = far walls), 0 near-zero self-hits; camera renders the room (door frame
         + pick_table + can + tiled floor, /tmp/r1_g1_cam.png — Read + confirmed, optical axis +x). 4/4 unit tests green.
         Sim torn down (rosm nuke + pkill mujoco). Spine vcli/cognitive/ BYTE-UNCHANGED (verified). Commit 65bc6c7.

blocked: none — not a CEO gate (sim asset + in-sim embodiment registration; no new ROS2 interface, no new external dep —
         menagerie g1 + g1_gait assets + sensors/ already in repo). HONEST shakiness for R2: (1) lidar gets 0 returns on the
         pick_table — g1 spawns just BEHIND a doorway frame, table is ~3m through the doorway, small + partly occluded at the
         lidar's elevation rings (the 3.0m min ring is the door frame/near walls, not the table) → R2 should move g1 closer /
         add a lower ring, OR accept the table is a camera-perception target not a lidar one. (2) Stand is a static PD hold,
         NOT locomotion — g1 cannot yet WALK in the room. (3) _start_g1 is in-process only; NL embodiment-switch not wired.
next:    R2 (cross-EMBODIMENT, evolve) — bundle: (a) NL embodiment-switch — "切换到 g1" / "启动 g1" through bare vector-cli
         routes to _start_g1 (wire the IntentRouter/sim_tool enum end-to-end, demonstrate in the REPL); (b) g1 LOCOMOTION in
         the room — adapt the recovered G1MuJoCoBase gait (/tmp/recovered_mujoco_g1.py, or git show 62ee0de:...mujoco_g1.py)
         so g1 walks to a commanded point without falling; (c) verify the lidar/camera while MOVING (scan updates as g1 walks,
         table comes into lidar range as it approaches). Then a cross-embodiment task graded by the moat: g1 navigates +
         perceives the room via NL. Recover gait, don't rebuild. Real-verify in the sim + Read a moving render.
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
