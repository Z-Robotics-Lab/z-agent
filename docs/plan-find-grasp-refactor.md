# Plan — find-and-grasp pipeline refactor (CURRENT phase plan)

> Resume anchor for the mobile-manipulation refactor. A fresh session should cold-read:
> THIS doc + `docs/agent-kernel-STATUS.md` + `docs/DECISIONS.md` (D88, D89, D90 … D110) + `git log`.
> Branch: `arch/plug-and-play`. Don't touch `vcli/cognitive/` (the honest-verify spine).
> Stages #1–#3 + #2b are SHIPPED (one-line pointers below; full records in DECISIONS D90–D96 + git);
> this plan stays LIVE for the OPEN stages #4/#5 and the D106 place-oracle CEO gate.

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

SHIPPED (one-line pointers — full verified records in DECISIONS D90–D96 + git):
- [x] **#1 — accurate object positions** (D91, ed2e810): `localize_objects_3d()` wired into `look.py` →
  the scene graph stores real `(x,y)` (~2.3–2.8 cm vs MuJoCo GT) + persists. Harness
  `tools/verify_localize_scenegraph.py`. (The label≠query localizer bug only e2e caught → tricky-bugs.)
- [x] **#2 — `navigate_to_object(object)` tool** (D92, c4cf5cc): name → `find_objects_by_category` →
  nearest localized match → standoff pose → `NavigateSkill` coordinate path; registered in
  `get_go2_skills()`. Harness `tools/verify_navigate_to_object.py`.
- [~] **#3 — arrival re-perceive + grasp** (D93–D95): full `look → navigate_to_object → perception_grasp`
  composes e2e (arrival re-perceive satisfied BY composition — perception_grasp perceives fresh at the
  standoff). Grasp reliability PLATEAUED ~0.83 GT-measured (D94 0.765 → D95 0.833) on the unified scripted
  seat-creep `_approach_and_seat` (the flaky vgraph `_approach_via_nav` retired). Harness `tools/verify_fetch_flow.py`.
- [x] **#2b — `home` skill 5-vs-6 DoF bug** (D96, 064294f): DoF-aware neutral fallback (`[0.0]*dof`) so a
  trailing `home` step no longer crashes the planner/executor path on the 6-DoF Piper. Unblocks bare-cli NL fetch.

OPEN (the reason this plan is still live — CEO-gated phase stages):
- [ ] **#4 — external-explore integration + persist + rebuild.** Enable observe (with #1 localization)
  during the TARE/FAR explore so the scene graph populates with accurate objects; persist. Add a
  `/rebuild` command (clear → explore → seed → save). (ExploreSkill currently emits `tare_not_running`
  without the external stack.)
- [ ] **#5 — startup seed + world manifest + store unification.** Seed rooms at startup from
  `config/room_layout.yaml` (today only lazy inside explore). Add `config/worlds/<world>.yaml`
  (rooms/boundary/persistence/cameras — world-as-config, Rule 11; objects discovered not declared).
  Unify SceneGraph as the single object store (bridge/retire WorldModel + the paused SysNav bridge).

## Open caveats / known issues

- **`merge_object` x=0/y=0 sentinel trap** (`scene_graph.py:458`): FIXED (D98, e762f12). The merge now
  uses a `None` sentinel (`x: float|None=None`) so a real object genuinely at the world origin/axis is
  applied, not discarded; coordinate-less merges keep the existing pose. look's `(0,0)` fallback was
  already removed D97. +6 regression unit tests; 100 scene-graph + 175 core/perception/skills green.
- **`find_objects_by_category` substring match** → "bottle" matches green+blue; merge dedups by exact
  category → possible duplicate nodes at scale. INTENTIONAL + tested (D107); fine for distinct names now.
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
- `vector_os_nano/skills/perception_grasp.py` (R12 grasp substrate + the D109/D110 far-fetch recovery)
- `config/room_layout.yaml`; `vector_os_nano/vcli/cli.py` (/clear_memory, startup wiring)
- External: `~/Desktop/vector_navigation_stack` (TARE/FAR), `scripts/launch_nav_explore.sh`

## Discipline

Verify every step yourself (read diffs, re-run tests). **Sim verification only when Yusen frees
the sim** (he tests manually). Offline unit tests are necessary but never acceptance — the real
acceptance is bare `vector-cli` + NL in the sim. Don't touch the verify spine.

## Decisions pending (CEO gate — batch into ONE executive summary for Yusen)

- **[RESOLVED D109/D110] Out-of-reach fetch recovery.** The proposed STRUCTURAL verify→FAIL→replan in the
  native kernel ReAct loop was **REJECTED** (it re-grows the hardcoded planner → violates native-is-the-design
  + the `native_loop` import firewall). Instead a **skill-level** far-recovery (CEO **Gate A**, approved) was
  implemented inside `perception_grasp` (D109, 8c5fc00/34e2dbc/ee57a05): on `no_detections` it seeds an un-gated
  localize from the clean forward pose → drives the 0.95 m standoff via the FAR planner → re-perceives at arrival
  → grasps, kernel/moat UNTOUCHED (firewall green). D110 (35307bc) closes the loop through bare-cli + real model:
  "把绿色的瓶子拿过来" with `VECTOR_FETCH_FAR=1` → GROUNDED verified=True (1 logged run). Reliability still
  VARIABLE (model routing / colour-param variance + intermittent VLM SSL). Evidence: DECISIONS D100/D102/D103/D104/D109/D110.

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
  **[CEO APPROVED 2026-06-29 — "build it with the moat proof".]** Build ADDITIVELY: a NEW predicate
  (`resting_on_receptacle`), leaving the floor-only `placed_count` BYTE-UNCHANGED so monotonicity
  holds by construction. Credit ONLY: xy strictly inside the named receptacle region AND z within a
  tight band of the receptacle top AND object AT REST (velocity ~0) AND RELEASED (gripper weld
  broken) — all from independent GT. Prove with an adversarial moat-skeptic (no existing ACCEPT path
  widened; held-above / near-but-not-on / in-flight must NOT credit) before merge.
