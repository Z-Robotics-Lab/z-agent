# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this FIRST; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design = [ARCHITECTURE.md](ARCHITECTURE.md); how to start = [getting-started.md](getting-started.md);
decision history = [DECISIONS.md](DECISIONS.md); hidden-bug lessons = [tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-24 · D69 fakeable-grasp false-green CLOSED (Prong 1 routing + Prong 2 stricter-only grasp gate)
goal:    a PLUG-AND-PLAY agent-orchestration runtime for physical AI — bring your own robot
         (urdf+mesh+config), policy, skill, capability; plan · route · verify · recover. Bare
         `vector-cli` + NL is the only acceptance face; the honest-verify spine is frozen.
phase:   PLUG-AND-PLAY PLATFORM REFACTOR (branch `arch/plug-and-play` off `feat/orchestrator-redesign`).
         Make the OS config-driven (a robot = a CONFIG file, not a driver class — Rule 11) + model-routed
         (strangle the legacy keyword producer), staged strangler-fig with bare-cli e2e each stage (Rule 12).

doing:   D69 (this session) — CLOSED the FAKEABLE-GRASP false-green (deepseek satisfied "抓前面的东西" by
         file_write('grabbed.txt') + verify(file_exists(...)) → GROUNDED). Prong 1 (world-side, no spine):
         a robot world DROPS file_write/file_edit/bash from the native loop's action toolset (keeps read-only
         file_read/glob/grep) + persona binding "never fake a physical action via files/bash". Prong 2 (the
         un-fakeable backstop; DELIBERATE rule-5 STRICTER-ONLY spine edit): `cognitive/object_goal.py` (grasp
         analogue of coord_goal) + `_object_goal_turn_ok` in `trace_store.evidence_passed` — a grasp-intent
         goal must be GROUNDED via a NECESSARY `holding_object`/`placed_count` conjunct, else RAN. Proven
         stricter-only (real grasp→GROUNDED, 3 fabrication vectors→RAN, all non-grasp turns UNCHANGED, nothing
         greened); 745 unit green (3 pre-existing env reds only); regression pinned. Bare-cli live deepseek
         acceptance: grasp turn ROUTES to the REAL perception_grasp+detect+walk, ZERO file_write/bash/marker
         (Prong 1 proven live). Clean end-to-end GROUNDED blocked by a PRE-EXISTING unrelated arm bug surfaced
         by the run (`PiperROS2Proxy.move_joints: expected 6 positions, got 5` in `scan` — NOT D17, separate
         fix). NOT committed (orchestrator reviews + commits).
         ---
         S1+S2+S3a+S3b DONE + verified (behavior-preserving). S3b: ONE scene builder —
         `hardware/sim/scene_builder.py build_room_scene(...) -> (MjModel, path)` via `MjSpec.attach`;
         BOTH `_build_room_scene_xml` (go2, prefix="") and `_build_g1_room_scene_xml` (g1, prefix="g1_") call
         it (the two-scene-builder fork is KILLED). Root blocker was a MuJoCo-3.9 `attach`+`to_xml` serializer
         bug (anonymous nested `<default>` → reload "empty class name"); fixed (B) = in-memory `compile()`
         authoritative + `normalize_attach_defaults` repairs the FILE (go2.xml NOT touched — fix A rejected).
         2nd blocker (build agent STOPPED at the byte-id guardrail): attach reorders go2 qpos (freejoint
         0→21, arm 19→40); finished D66's missed qpos-order literals (arm-stow + MPC pin) to DofLayout. Latent
         bug fixed: arm-stow guard nq≥27→nu≥19 (pickables inflate bare nq to 40 → Case 8). BYTE-IDENTICAL all
         3 cases (go2+arm/bare/g1: counts+name-sets+class-default params by NAME). ORCHESTRATOR VERIFICATION
         caught+fixed a 2nd reorder regression the build agent MISSED: `MuJoCoPiper` IK base-sync read literal
         `qpos[0:19]` → pickables under attach (root=21); fixed to DofLayout-derived (Case 9); IK-base-sync e2e
         CONFIRMED (IK tracks the moved dog, not the default). 50 driver + 17 piper unit green. FULL bare-cli
         grasp e2e still OWED before S3b is 100% done (R12).
         S2: drivers READ `robot.yaml` + generic `DofLayout`. S1: config schema + g1 BaseProtocol uniformity.

owns:    `embodiments/**`, `hardware/sim/{scene_builder.py, mujoco_go2.py, mujoco_g1.py, mujoco_piper.py}`,
         `vcli/native_loop.py`, `vcli/cognitive/{object_goal.py NEW, trace_store.py}`, `docs/*`.
         Spine `vcli/cognitive/` was byte-unchanged 7b220d9→D68; D69 is the FIRST deliberate edit since — a
         PURELY STRICTER object-goal turn-gate (rule 5 "only ever stricter"; evidence_classifier / actor_causation
         / coord_goal still UNTOUCHED).

blocked: none. Later stages carry CEO gates (surface, do NOT cross): S4 embodiment-registration
         interface (replace the `sim_tool` enum); S5 `ControlPolicy` interface + convex_mpc as an explicit
         dep; S6 capability permission/security path for side-effecting VLAs. Full analysis: /tmp/pnp_synthesis.md.

next:    S3b bare-cli e2e (Rule 12 acceptance, still OWED before "done"): go2+arm grasp + bare go2 nav + g1
         through bare `vector-cli` + NL, honest verdict surfaces. Then S3c navigate (g1 in-driver vgraph vs
         go2 external ROS2-FAR — genuinely different mechanisms, needs design, possibly gate-adjacent).
         Then S4 (embodiment registry — replace the `sim_tool` enum, CEO gate), S5 (ControlPolicy plugin +
         convex_mpc dep, CEO gate), S6 (capability planner-exposure + side-effecting permission path, CEO
         gate), S8 (delete the legacy keyword producer + tables), S9 (doc CI drift gate).
         Repro: MUJOCO_GL=egl; serialize sims + `rosm nuke` after; spine only ever STRICTER.

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
  cannot author. The sandbox may only get STRICTER (rule 5). `vcli/cognitive/` BYTE-UNCHANGED since 7b220d9.
- `native_loop.run_turn_native` is the default model-driven producer (no keyword table); the legacy keyword
  producer is being strangled (delete at S8). Acceptance = bare `vector-cli` + NL only.
- cross-MODEL (D48-D50) + the moat are LIVE on master (origin/master cd7029a).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- Plug-and-play stage gates: S4 embodiment-registration interface · S5 `ControlPolicy` interface + convex_mpc dep
  · S6 side-effecting-capability permission/security. Plus: nav→FAR cmd_vel causation (SPINE D14) · strategy_params
  preservation (SPINE D52) · explore TARE · VLN SysNav. New deps / interfaces / hardware / security route here.
