# Plan — find-and-grasp pipeline refactor (CURRENT phase plan)

> Resume anchor for the mobile-manipulation refactor. A fresh session should cold-read:
> THIS doc + `docs/agent-kernel-STATUS.md` + `docs/DECISIONS.md` (D88, D89, D90) + `git log`.
> Branch: `arch/plug-and-play`. Don't touch `vcli/cognitive/` (the honest-verify spine).

## Goal — the correct workflow (Yusen)

explore → **build map ONCE** → **persist** (sim is static) → `/clear_memory` to rebuild →
scene graph with **accurate object GLOBAL positions** → **navigate to the object's vicinity** →
on arrival **re-perceive with depth and adjust** → **grasp**.

**AGENT-ADAPTIVE, not a hardcoded pipeline:** the OS provides accurate data (scene graph) +
verifiable building-block tools + persistent memory; the *model* composes them per situation
(map empty → explore; object known → navigate→grasp; not found → look around). Reuse R12
`perception_grasp` as the stage-5 grasp substrate.

## Root cause (verified — D88/D89)

The robot's **sensors are CORRECT** (depth metric, intrinsics, camera pose, camera→world all
verified line-by-line). The scene graph was "completely inaccurate" because the **observe path
never used depth** — it passed object *names only*, so every object fell to `merge_object`'s
`x=0,y=0` defaults → stored at room-center. The accurate depth→world machinery
(`grasp_point_from_rgbd`) existed but was never invoked during mapping. Fixed in stage #1.

## Decisions (approved by Yusen)

- **Map building = external TARE/FAR explore** (real geometry, one-time, persisted). The nav
  stack lives at `~/Desktop/vector_navigation_stack`, launched via `scripts/launch_nav_explore.sh`.
- **SceneGraph = the single source of object positions** (unify the separate WorldModel into it).
- **Orchestration stays model-driven / agent-adaptive** (building blocks, not a fixed pipeline).
- Object positions come from **perception (depth)**, never hardcoded; the persistent
  `scene_graph.yaml` holds discovered objects. Rooms may be seeded from config.

## Staged plan

- [x] **#1 — accurate object positions. REAL-SIM VERIFIED (D91, ed2e810).** `localize_objects_3d()`
  wired into `look.py` → scene graph stores real `(x,y)`. Real sim: green/blue/red ~2.3-2.8 cm vs
  MuJoCo GT; full look→scenegraph stores+persists; red-team CONFIRMED the narrow claim.
  Bug found+fixed (only e2e caught it): localizer keyed by detector label ("a green bottle") not the
  query → objects stored at (0,0); now keyed by input query. Harness: `tools/verify_localize_scenegraph.py`.
- [x] **#2 — `navigate_to_object(object)` tool. REAL-SIM VERIFIED (D92, c4cf5cc).**
  `skills/navigate_to_object.py`: object name → `find_objects_by_category` → nearest localized match →
  `compute_approach_pose` 0.7m standoff (object cell is an inflated obstacle) → NavigateSkill coordinate
  path. Registered in `get_go2_skills()`. Real sim: dog 2.67m→0.95m to green bottle (GT-measured).
  Harness `tools/verify_navigate_to_object.py`. 9 offline tests.
- [~] **#3 — arrival depth re-perceive + grasp. COMPOSITION VERIFIED E2E (D93, bc477ea).**
  Full `look → navigate_to_object → perception_grasp` grasps+lifts the green bottle in real sim
  (0.32→0.558 m, holding + make_holding_object oracle). Arrival re-perceive is satisfied BY
  COMPOSITION (perception_grasp perceives fresh at the navigate arrival standoff — R12's well-framed
  distance; adding a 0.40 m re-perceive would REGRESS R12, so NOT added). Fixed the real gap:
  pick_top_down required a world_model even with target_xyz (now optional). Harness
  `tools/verify_fetch_flow.py`. **GRASP RELIABILITY RAISED + DIAGNOSIS CORRECTED (D94): 13/17 = 0.765
  GT-measured** (the D93 "1/3" was an unlucky N=3; true baseline was a noisy ~0.67-0.75). D93's
  "terminal-precision/gait-drift" diagnosis was WRONG — a probe proved the base does NOT drift standing
  (0.2 mm/6 s) and the EE lands within 5 mm of the IK target from a good standoff. Real modes: (a)
  PERCEPTION FRAMING (was dominant) — navigate_to_object landing the dog too CLOSE (<0.8 m) → head camera
  pitches OVER the low bottle → scan finds nothing → fail; FIXED by raising the standoff 0.70→0.95 m
  (perceive=None eliminated, 0/17 since). (b) NAV-APPROACH BAIL — `_approach_via_nav`'s `navigate_to` to
  the tight 0.40 m near-obstacle standoff intermittently drives the dog ~4 m past the object; FIXED with a
  scripted-creep recovery guard. REMAINING single mode = APPROACH reliability (dog doesn't always reach the
  IK-reachable head-on standoff). +4 regression tests.**
  **APPROACH UNIFIED + RELIABILITY RAISED (D95, 2389e84): 10/12 = 0.833 GT-measured** (up from 0.765). The
  final hop is now ONE impl for every base — the scripted stall-seating creep `_approach_and_seat`
  (_grasp_ready_repose → _approach_object → _face_object); the flaky vgraph `_approach_via_nav` is RETIRED
  (net −33 lines, dropped _GRASP_STANDOFF_M + _NAV_APPROACH_MAX_OFF). The scripted creep seats the dog against
  the table edge = a kinematically-pinned, planner-variance-free standoff. 2/12 fails are now two DIFFERENT
  modes (1 perception-framing, 1 terminal-grasp) — no single dominant mode left. **Grasp reliability is
  PLATEAUED at ~0.83 after R-D94/D95; per the loop invariant, pivoted down the backlog.**
- [x] **#2b — `home` skill 5-vs-6 DoF bug FIXED + REAL-SIM VERIFIED (D96, 064294f).** The hard-coded
  5-DoF SO-101 home pose crashed `Agent.execute_skill('home')` on the 6-DoF Piper (`move_joints expected
  6 got 5`), crashing the whole planner/executor path (a trailing `home` step is appended to manip plans).
  DoF-aware fix (Rule 11): `len(pose)!=arm.dof` → URDF-zero neutral `[0.0]*dof`. Real sim: execute_skill
  ('home') success, arm reaches neutral, exit 0 (tools/verify_home_dof.py). +4 unit tests. Unblocks the
  bare-cli NL fetch route. NEXT non-gated: drive "把绿色瓶子拿过来" through bare `vector-cli` REPL by NL.
- [ ] **#4 — external-explore integration + persist + rebuild.** Enable observe (with #1 localization)
  during the TARE/FAR explore so the scene graph populates with accurate objects; persist. Add a
  `/rebuild` command (clear → explore → seed → save). (ExploreSkill currently emits `tare_not_running`
  without the external stack.)
- [ ] **#5 — startup seed + world manifest + store unification.** Seed rooms at startup from
  `config/room_layout.yaml` (today only lazy inside explore). Add `config/worlds/<world>.yaml`
  (rooms/boundary/persistence/cameras — world-as-config, Rule 11; objects discovered not declared).
  Unify SceneGraph as the single object store (bridge/retire WorldModel + the paused SysNav bridge).

## Open caveats / known issues (from #1 red-team — D91)

- **Real GPT-4o VLM path unproven.** `look` with the real VLM failed on OpenRouter SSL/network;
  only the stub-named path ran (localization itself was real). Re-run when network is up.
- **bare-cli NL acceptance not yet exercised** (the non-negotiable face). The `home` 5-vs-6 DoF bug that
  blocked the planner/executor path is now FIXED + real-verified (D96), so the full "把绿色瓶子拿过来" NL
  flow can run end-to-end — that bare-cli e2e is the next non-gated chunk (the harnesses are internal only).
- **`merge_object` x=0/y=0 sentinel trap** (`scene_graph.py:458`): FIXED (D98, e762f12). The merge now
  uses a `None` sentinel (`x: float|None=None`) so a real object genuinely at the world origin/axis is
  applied, not discarded; coordinate-less merges keep the existing pose. look's `(0,0)` fallback was
  already removed D97. +6 regression unit tests; 100 scene-graph + 175 core/perception/skills green.
- **`find_objects_by_category` substring match** → "bottle" matches green+blue; merge dedups by exact
  category → possible duplicate nodes at scale. Fine for distinct names now.
- **Single viewpoint only.** #1 accuracy proven at the fixed spawn (~0.9 m, well-framed); other
  poses/distances/occlusion/clutter untested. #3's arrival re-perceive is what handles inexact arrival.

## What already EXISTS (reuse, don't rebuild)

- Scene-graph persistence: `SceneGraph.save()/load()` → `~/.vector_os_nano/scene_graph.yaml`
  (rooms+viewpoints+objects-with-xyz+doors); restore-at-startup; save-on-exit.
- `/clear_memory` slash command (wipes scene_graph.yaml + terrain_map.npz + in-memory graph).
- The correct depth→world pipeline: `perception/grasp_point.py`, `perception/depth_projection.py`.
- R12 grasp (reach + obstacle-avoidance approach + dock): `skills/perception_grasp.py`,
  `MuJoCoGo2.navigate_to` (vgraph).

## Key files

- `vector_os_nano/perception/object_localizer.py` (#1, NEW), `grasp_point.py`, `depth_projection.py`
- `vector_os_nano/skills/go2/look.py` (observe), `explore.py` (explore), `vector_os_nano/skills/navigate.py`
- `vector_os_nano/core/scene_graph.py` (`observe_with_viewpoint`, `find_objects_by_category`, save/load)
- `vector_os_nano/skills/perception_grasp.py` (R12 grasp substrate)
- `config/room_layout.yaml`; `vector_os_nano/vcli/cli.py` (/clear_memory, startup wiring)
- External: `~/Desktop/vector_navigation_stack` (TARE/FAR), `scripts/launch_nav_explore.sh`

## Discipline

Verify every step yourself (read diffs, re-run tests). **Sim verification only when Yusen frees
the sim** (he tests manually). Offline unit tests are necessary but never acceptance — the real
acceptance is bare `vector-cli` + NL in the sim. Don't touch the verify spine.

## Decisions pending (CEO gate — batch into ONE executive summary for Yusen)

- **[D103/D104, 2026-06-29] Structural verify→FAIL→replan in the native kernel ReAct loop.**
  The composed out-of-reach fetch grounds 0/N: the model's far routing is too variable, and the
  non-gated prompt nudge (D103) did NOT fix it (far N=4 = 0/4, chaotic). D104 then RULED OUT the
  last non-gated hypothesis — the near blue/red distractor confound — by moving ALL THREE bottles
  far (clean scene): a clean-far turn STILL does not ground, the model burns the entire 24-turn
  ReAct cap (_MAX_NATIVE_TURNS) on mis-sequenced nav/grasp attempts (>10 min, far past the ~280s
  acceptance budget). The non-gated levers are now EXHAUSTED/PLATEAUED. The real fix is to make the
  KERNEL deterministically inject `navigate_to_object(name) → perception_grasp` when a far grasp
  returns no_detections / runs without a weld — the absent Rule-1 "recover" pillar — instead of
  relying on the model self-directing. This is an architectural plan.md change → **CEO approval
  required** (executive summary + ADR). Evidence: DECISIONS D100/D102/D103/D104. Do NOT implement
  autonomously. Non-gated work continues meanwhile (ran-no-weld diagnosis ✅ D105, pick-and-place
  ✅ D106, slop cleanup).

- **[D106, 2026-06-29] Receptacle-relative place oracle (replace floor-only `placed_count`).**
  The go2+arm pick→place WIRING is proven (grasp→GT-weld-release, test_go2_pick_place_composition).
  But a `placed_count`-GROUNDED place is unreachable on a tall mobile manipulator at a table:
  empirically (probe 2026-06-29) the loaded Piper COLLIDES with the table front edge on descent
  (stalls z~0.30, the bottle settles near the table top, placed_count stays 0) — NOT an IK-reach
  limit (collision-free IK converges to z=0.10). And even with clear floor, dropping an object on
  the ground is the wrong task: the natural place target is a RECEPTACLE at height, which the
  frozen `placed_count` (credits only z<0.10) structurally cannot grade. The fix is a
  receptacle-relative resting predicate (object supported on/within a named receptacle's region,
  any z) in `vcli/worlds/arm_sim_oracle.py` — a **spine semantics change = CEO gate** (the honest
  -verify moat may only get stricter; a new oracle needs review it doesn't widen any ACCEPT path).
  Until approved, go2+arm place ships as the honest grasp→release primitive only.
