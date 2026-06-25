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

- [x] **#1 — accurate object positions.** `perception/object_localizer.py` `localize_objects_3d()`
  (reuses `grasp_point_from_rgbd`: detect→segment→depth→world centroid, SysNav-style) wired into
  `skills/go2/look.py` observe path → scene graph stores real `(x,y)`. Offline-verified (18 tests,
  no sim). **E2E in the real sim PENDING (needs Yusen's sim).** ← verify this first on resume.
- [ ] **#2 — `navigate_to_object(object)` tool.** Bridge: object name → `SceneGraph.find_objects_by_category`
  → world `(x,y)` → `base.navigate_to(x,y)` to the vicinity. No standalone bridge exists today
  (D88); navigate only takes coordinate/room. Add as a skill the agent can call.
- [ ] **#3 — arrival depth re-perceive + adjust, then grasp.** On arrival near the object, re-perceive
  with depth (`object_localizer`/`grasp_point`) to correct the position (arrival isn't exact), then
  approach+grasp (reuse R12 `perception_grasp`). NB: `perception_grasp` currently does NOT re-perceive
  after the approach (explicit comment) — this stage adds that.
- [ ] **#4 — external-explore integration + persist + rebuild.** Enable observe (with #1 localization)
  during the TARE/FAR explore so the scene graph populates with accurate objects; persist. Add a
  `/rebuild` command (clear → explore → seed → save). (ExploreSkill currently emits `tare_not_running`
  without the external stack.)
- [ ] **#5 — startup seed + world manifest + store unification.** Seed rooms at startup from
  `config/room_layout.yaml` (today only lazy inside explore). Add `config/worlds/<world>.yaml`
  (rooms/boundary/persistence/cameras — world-as-config, Rule 11; objects discovered not declared).
  Unify SceneGraph as the single object store (bridge/retire WorldModel + the paused SysNav bridge).

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
