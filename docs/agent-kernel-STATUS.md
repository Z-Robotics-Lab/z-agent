# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this FIRST; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design = [ARCHITECTURE.md](ARCHITECTURE.md); how to start = [getting-started.md](getting-started.md);
decision history = [DECISIONS.md](DECISIONS.md); hidden-bug lessons = [tricky-bugs.md](tricky-bugs.md).

updated: 2026-06-23 · arch/plug-and-play S1 done (embodiment config + g1 BaseProtocol)
goal:    a PLUG-AND-PLAY agent-orchestration runtime for physical AI — bring your own robot
         (urdf+mesh+config), policy, skill, capability; plan · route · verify · recover. Bare
         `vector-cli` + NL is the only acceptance face; the honest-verify spine is frozen.
phase:   PLUG-AND-PLAY PLATFORM REFACTOR (branch `arch/plug-and-play` off `feat/orchestrator-redesign`).
         Make the OS config-driven (a robot = a CONFIG file, not a driver class — Rule 11) + model-routed
         (strangle the legacy keyword producer), staged strangler-fig with bare-cli e2e each stage (Rule 12).

doing:   S1 DONE + e2e-verified (additive, spine BYTE-UNCHANGED): `embodiments/config.py` (frozen
         `EmbodimentConfig` + fail-loud loader) + `embodiments/{go2,g1}/robot.yaml` (faithfully capture the
         current driver constants) + MuJoCoG1 made BaseProtocol-uniform (fixed a latent g1 `disconnect`
         OOM leak). 67 unit green; g1 real-sim e2e (connect / methods / teardown). Config NOT yet read by
         the driver (that is S2). Also this session: North Star expanded (5 contracts + moat), Rules 11/12
         added, 5 dead files removed, DECISIONS compacted 494→250, ARCHITECTURE high-level rewrite +
         getting-started.md in flight.

owns:    `embodiments/**` (NEW), `hardware/sim/mujoco_g1.py` (+BaseProtocol, additive), `docs/*`. Spine
         `vcli/cognitive/` BYTE-UNCHANGED since 7b220d9.

blocked: none for S1. Later stages carry CEO gates (surface, do NOT cross): S4 embodiment-registration
         interface (replace the `sim_tool` enum); S5 `ControlPolicy` interface + convex_mpc as an explicit
         dep; S6 capability permission/security path for side-effecting VLAs. Full analysis: /tmp/pnp_synthesis.md.

next:    S2 — the GENERIC driver READS the config (delete hardcoded spawn/qpos/stance/sensor constants; DoF
         self-introspect from `root_body`, generalizing `_G1Offsets`); migrate go2 then g1, each bare-cli
         e2e. Then S3 (ONE shared impl per capability — navigate / lidar / scene-build, killing the go2-vs-g1
         forks), S4 (embodiment registry), S5 (ControlPolicy plugin), S6 (capability planner-exposure +
         permission path), S8 (delete the legacy keyword producer + tables), S9 (doc CI drift gate).
         Repro: MUJOCO_GL=egl; serialize sims + `rosm nuke` after; spine only ever STRICTER.

## The 5 plug-and-play contracts (the refactor's structural spine — R11; detail → ARCHITECTURE.md)
- **Embodiment**: urdf+mesh+`robot.yaml` → ONE generic driver (S1 schema done; S2 wires it).
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
