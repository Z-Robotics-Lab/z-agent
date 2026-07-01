# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read FIRST. GOAL = [../CLAUDE.md](../CLAUDE.md) North Star; durable
design = [ARCHITECTURE.md](ARCHITECTURE.md); decisions = [DECISIONS.md](DECISIONS.md); hidden bugs =
[tricky-bugs.md](tricky-bugs.md). SNAPSHOT, not a log — round history lives in DECISIONS + git.

updated: 2026-07-01 · D164 — TRIAGE done + 3 CEO decisions APPROVED (A->C->B). #1 OPEN ITEM = ACCEPTANCE-FACE GAP.
Prior FETCH (0.93/0.87) + PLACE (8/8, e2e 3/3) numbers were on the FLAG-GATED `--sim-go2` IN-PROCESS sim, NOT the
bare `vector-cli` REPL + NL face → DOWNGRADED to "not yet re-accepted" (approved). D163's crash claim CORRECTED: the
ROS2 stack comes up HEALTHY (~53s FAR/TARE) then dies on TEARDOWN — "rcl context invalid" is teardown noise, not a
crash; the real defect = a Rule 3/11 SPLIT-BRAIN (cli.py `--sim-go2` in-process vs sim_tool._start_go2 which ignores
VECTOR_NO_ROS2 + always launches the ROS2 stack). Pipeline OpenRouter-INDEPENDENT: routing=Qwen(qwen-max) + eyes=
Qwen3-VL-plus via DashScope (Clash RULE mode; DeepSeek-direct + OpenRouter dead). `~/.local/bin/vector-cli` = WRAPPER
(backup `.orig`) → Qwen + VECTOR_MAX_TOKENS=8000 + --native-loop + sim env.
TRACK A DONE — the loop-driver is the maintainer's PRIVATE self-dev harness, OUTSIDE this repo; a clone neither has
nor needs it (it only DRIVES development, it is not part of the shipped runtime). That harness was hardened (systemd
--user supervisor, Restart=always + per-round scope + per-dir lock + never-kill rule), code-reviewed + verified.
Loops STOPPED until C(b) re-acceptance lands.

goal:    PLUG-AND-PLAY agent-orchestration runtime for physical AI — bring your own robot/policy/skill/capability;
         plan · route · verify · recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen.
phase:   Post-fetch-place. The SKILLS work in-process (perception_grasp + R11 grasp-retry; mobile_place + R14
         central-drop + R15 12s-settle; moat resting_on_receptacle D106/D116). The gap is the acceptance FACE (D163).
owns:    skills/{perception_grasp,navigate_to_object,mobile_*}.py, vcli/tools/sim_tool.py, tools/acceptance/**,
         acceptance/**, docs/*. Spine vcli/cognitive/ FROZEN (stricter-only).
blocked: bare-cli fetch/place — awaiting Track C(b) (D164). CEO gates queued below — do NOT cross.
next (per D164, approved A->C->B; A DONE):
  1. [DONE] Self-dev loop-driver made reliable — the maintainer's PRIVATE loop harness lives OUTSIDE this repo (a
     clone neither has nor needs it); systemd Restart=always + scoped rounds + per-dir lock + never-kill rule; verified.
     No loop RUNNING until step 2 re-acceptance lands.
  2. [NEXT] CLOSE D163 via APPROVED (b)+hybrid: SINGLE-SOURCE extract cli.py's in-process go2+arm build (cli.py:747-888)
     into ONE shared helper; make sim_tool._start_go2 (sim_tool.py:476-654) call it when VECTOR_NO_ROS2=1 (NOT a copy —
     a copy re-splits the brain). Preserve the ROS2 path (explore/nav) + add a parity e2e; fix runtime.py:132/139
     teardown ordering. Then RE-ACCEPT fetch+place on the BARE REPL (no -p/--sim-go2; `pgrep -f launch_explore` EMPTY
     proves (b) took), all 3 colours, N>=5, Qwen3-VL eyes, red-team. Non-gated code; this IS the approved gate.
  3. [THEN] Track B guardrails (G1=C(b) removes the flag path; G2 harness flag-guard; G3 RECORD provenance gate;
     G4 env split; G5 red-team provenance question) — make bare-cli+NL un-bypassable. Then #3 frontier.
tooling (scratchpad/, git-tracked): place_probe.py + run_probe.sh (fast skill-direct place ~120s/trial, no LLM,
  reads moat oracle + bottle xyz); measure_qwen.py + run_measure_qwen.sh (bare-cli fetch/place rate + Qwen3-VL eyes).
  GOTCHAS: inline sim cmds must NOT pre-`pkill 'vector_os_nano.vcli.cli'` (self-kills the bash -c shell); `rosm nuke`
  between sims, NEVER pkill mujoco; serialize sims. EVERY change: git commit.

## The 5 plug-and-play contracts (the refactor's structural spine — R11; detail → ARCHITECTURE.md)
- **Embodiment**: urdf+mesh+`robot.yaml` → drivers READ it via `DofLayout` (S1 schema + S2 wired; S4 = one generic driver class).
- **Policy**: gait/control plugged separately by an obs/action spec (S5).
- **Skill**: `@skill` declaring `requires` arm|base|camera; may wrap an external VLA/VLM or a classical stack.
- **Capability**: register an external model/stack (detector/planner/VLA) as a routable unit (S6 planner-exposure).
- **Verify**: a world-side predicate reading INDEPENDENT GT; the frozen spine grades it.

## G1 cross-embodiment (durable summary; round narrative in DECISIONS D57-D64 + git)
- R1-R8: g1 (12-dof RL gait) STANDS+WALKS in the go2 room (D57-58); a MOAT-GRADED routable embodiment with
  go2 parity (D59, `at_position`→RAN honest D14); grounding-dino routes onto its head camera (D60), R4's
  false-green fixed→RAN (D61), audit-clean (R6); FIRST honest GROUNDED via GT-segmentation match (D63);
  obstacle-aware `navigate_to` via `g1_vgraph` (D64). cross-MODEL (D48-D51) is LIVE on master.

## Standing facts (durable)
- Branch `arch/plug-and-play` off `feat/orchestrator-redesign` off master; `feat/playground-vln` is ABANDONED.
- Honest-verify moat: a step grades GROUNDED only when a deterministic predicate reads an oracle the ACTOR
  cannot author. The sandbox may only get STRICTER (rule 5). `vcli/cognitive/` was byte-unchanged 7b220d9→D68;
  D69 (object_goal.py + the trace_store gate) is the ONE deliberate edit since, and it is STRICTER-ONLY; the spine
  tree-hash has been byte-frozen across the entire R1-R8 loop arc (independently re-verified R9/D79). [Was a stale
  absolute "BYTE-UNCHANGED since 7b220d9" slogan — corrected R9 since D69 made it literally false.]
- `native_loop.run_turn_native` is the default model-driven producer (no keyword table); the legacy keyword
  producer is being strangled (delete at S8). Acceptance = bare `vector-cli` + NL only.
- cross-MODEL (D48-D50) + the moat are LIVE on master (origin/master cd7029a).

## find-and-grasp OPEN stages (migrated from plan-find-grasp-refactor.md — OPEN + CEO-gated, NOT done)
- **#4 — external-explore integration + persist + rebuild (OPEN, CEO-gated).** Enable observe (with #1
  localization) during the TARE/FAR explore so the scene graph populates with accurate objects; persist. Add a
  `/rebuild` command (clear → explore → seed → save). (ExploreSkill today emits `tare_not_running` without the
  external stack.)
- **#5 — startup seed + world manifest + store unification (OPEN, CEO-gated).** Seed rooms at startup from
  `config/room_layout.yaml` (today only lazy inside explore). Add `config/worlds/<world>.yaml`
  (rooms/boundary/persistence/cameras — world-as-config, Rule 11; objects discovered not declared). Unify
  SceneGraph as the single object store (bridge/retire WorldModel + the paused SysNav bridge).
- Reuse (don't rebuild): `SceneGraph.save()/load()`→`~/.vector_os_nano/scene_graph.yaml`; `/clear_memory` (wipes
  scene_graph.yaml + terrain_map.npz + graph); depth→world = `perception/{grasp_point,depth_projection}.py`; R12
  grasp = `skills/perception_grasp.py` + `MuJoCoGo2.navigate_to` (vgraph).
- Key files: `perception/object_localizer.py`, `skills/go2/{look,explore}.py`, `skills/navigate.py`,
  `core/scene_graph.py`, `skills/perception_grasp.py`, `config/room_layout.yaml`, `vcli/cli.py` (/clear_memory +
  startup wiring); external `~/Desktop/vector_navigation_stack` (TARE/FAR) + `scripts/launch_nav_explore.sh`.

## Pending CEO gates (decision queue — do NOT cross autonomously)
- **S8 — retire the legacy keyword producer (READY for approval; all preconditions S5a/S5b/S5c done).**
  One-liner: delete the keyword routing layer so routing is model + declared-metadata only (North Star).
  Remove: `IntentRouter` (`_RULES`/`should_use_vgg`/`is_complex`/`_MOTOR_*` keyword sets) + `StrategySelector`
  keyword ladder + `engine._DIR_MAP`/`_VERIFY_MAP`/`_ROOM_ALIASES` + the legacy `GoalDecomposer`/`GoalExecutor`
  producer; rewire the 4 `should_use_vgg` gate sites (cli.py:414/2445, engine.py:1090/1707) onto the proven
  `should_attempt_native` (D74). Keep `legit-config` rows (stop-words, `_TOOL_CATEGORIES`, `_COLOR_TO_SCENE` until a
  scene-name binder lands). WHY GATED: changes the routing CONTRACT + the `-p`/REPL acceptance entrypoints + retires
  a producer; a big, owner-visible behavior-contract change. RISK: a goal the model can't route loses the legacy
  fallback (mitigation: keep `VECTOR_LEGACY_TURN`/`VECTOR_PRINT_NATIVE` escape hatches one milestone). VERIFY: full
  S0 regression + a novel 3rd-language phrasing all route with ZERO keyword tables; `red-team` before sealing.
  → Needs Yusen's go/no-go before the deletion.
- **S3c — navigate planner-plugin (DESIGN done, ADR-001; implementation GATED + recommend DEFER).**
  Navigate is already converged at the TOOL layer (one polymorphic `_NativeBaseNavigateTool`; pinned by
  tests/unit/embodiments/test_navigate_contract.py). The Rule-11 convergence of the two PLANNER backends
  (go2 external ROS2-FAR vs g1 in-driver vgraph) = a pluggable planner Capability declared in robot.yaml
  (`planner: far|vgraph`). GATED: new Planner interface + a `nav` robot.yaml field + the FAR external-dep
  formalization. Recommendation (ADR-001): DEFER until N≥3 planners/embodiments motivate the abstraction
  (YAGNI at N=2; no regression risk meanwhile). → Yusen go/no-go, batched.
- **D106 — receptacle-relative place oracle: CEO-APPROVED + BUILT + MOAT-PROVEN (D116).** The height-aware
  `make_resting_on_receptacle` oracle is in the spine (additive, `placed_count` byte-unchanged → monotonicity by
  construction), adversarially moat-proven (skeptic caught+fixed 2 false-greens: velocity fail-safe-reject +
  low-receptacle held-check guard). The CEO-gated spine piece is DONE. REMAINING (non-gated plumbing): wire it
  into the verify namespace (robot.py) · add a height receptacle to the go2 scene · arm↔table descent fix ·
  real-sim ground a bare-cli pick-AND-place. Until those land, place still ships as the grasp→release primitive.
- Plug-and-play stage gates: S4 embodiment-registration interface · S5 `ControlPolicy` interface + convex_mpc dep
  · S6 side-effecting-capability permission/security. Plus: nav→FAR cmd_vel causation (SPINE D14) · strategy_params
  preservation (SPINE D52) · explore TARE · VLN SysNav. New deps / interfaces / hardware / security route here.
