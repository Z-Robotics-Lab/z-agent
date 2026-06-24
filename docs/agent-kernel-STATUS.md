# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this FIRST; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design = [ARCHITECTURE.md](ARCHITECTURE.md); decision history =
[DECISIONS.md](DECISIONS.md); hidden-bug lessons = [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · G1 R8 done · EdgeTAM pinned offline · docs refreshed
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance face.
phase:   M4 cross-EMBODIMENT × cross-MODEL, moat-graded. The runtime switches to a 2nd body (g1),
         routes a learned model (grounding-dino) onto its camera, GROUNDS perception against
         independent sim GT, and navigates AROUND obstacles — all through bare `vector-cli` + NL.

doing:   DONE this session (world/perception/docs only): (1) EdgeTAM tracker pinned strictly OFFLINE
         (commit 0c867d8 — mirrors grounding-dino: HF offline env + `local_files_only`, never downloads;
         real-verified loading from cache). (2) Docs refreshed to R8 reality + `.sdd/DEBUG.md` deleted
         (see "Docs refresh" below). Frontier: g1 cross-embodiment richly proven (R1-R8) — resting at a
         clean milestone; R9 options in `next`.

owns:    perception/tracker.py (offline pin); docs/* (refresh). Spine `vcli/cognitive/` BYTE-UNCHANGED
         across 64 DECISIONS (since 7b220d9) — this session touched no kernel/verify code.

blocked: none — NOT a CEO gate (no new interface / external dep / hardware / security). Honest caveats:
         (1) g1 GROUNDED is a single deterministic spawn — no multi-trial success RATE yet;
         (2) g1 head-cam `world_to_pixel` is UNRELIABLE (kept, unused; R7 uses the seg render instead);
         (3) the FaceLLM token stream is faked (D46-D63) — a LIVE-LLM producer on g1 is still open.

next:    R9 (pick highest ambition×feasibility): (a) a fuller MULTI-STEP cross-embodiment TASK —
         nav-around-obstacle → GROUNDED-detect chained in ONE NL turn; (b) MULTI-TRIAL honest detect
         RATE on a randomized g1 spawn (3-5 trials); (c) a LIVE-LLM producer on g1 (drop the faked token
         stream); (d) a 2nd / larger embodiment. Real-verify in the sim + Read the frame every round.
         Gated CEO-queue (do NOT cross): nav→FAR cmd_vel causation (SPINE — D14), strategy_params
         preservation (SPINE — D52), explore (TARE), VLN (SysNav). merge cross-MODEL→master = DONE.
         Repro: `.venv` needs `timm>=1.0`; grounding-dino + EdgeTAM weights cached (offline OK); MUJOCO_GL=egl.

## G1 cross-embodiment (durable summary; round narrative in DECISIONS D57-D64 + git)
- R1-R2: g1 (12-dof RL gait) STANDS + WALKS in the go2 room with lidar + camera (D57-58).
- R3: a MOAT-GRADED routable embodiment with go2 parity via the SAME world seam — no g1-specific
  oracle (D59; `at_position` → RAN honest, D14).
- R4→R5: the grounding-dino detector ROUTES onto g1's head camera (D60); R4's self-certifying GROUNDED
  was a false-green, fixed to RAN-honest (D61), audit-clean (R6).
- R7: g1's FIRST honest GROUNDED — `detection_matches_gt` checks the detector box against an
  INDEPENDENT MuJoCo segmentation render (red→GROUNDED, green→RAN) (D63).
- R8: obstacle-aware `navigate_to` via the recovered `g1_vgraph` — routes AROUND the pick_table (D64).

## Docs refresh (2026-06-23 — keep the bounded canonical set current to the code)
- `.sdd/DEBUG.md` DELETED (stale R42 nav+grasp debug artifact; conclusion lives in DECISIONS D56).
- ARCHITECTURE: live grounding-dino DetectorCapability (was "does not yet exist"), g1 added to Worlds,
  go2 base predicates single-sourced in `go2_sim_oracle.py`, dead phase-c/d plan links dropped, 8-layer perms.
- cli-tool-system: permission order corrected (intrinsic deny FIRST, 8 layers); file map (cognitive ~22
  modules, `worlds/` under `vcli/`, `native_loop.py`/`verdict.py`, `foxglove_tool.py`→`viz_tool.py`).
- skill-protocol: Built-in Skills table fixed (wave `direct=True`, detect `direct=False`); dropped the
  fabricated `→ home` tail. tricky-bugs: duplicate `## Case 6` → `Case 7`; dropped a rotting line number.

## Standing facts (durable)
- Branch `feat/orchestrator-redesign` off master; `feat/playground-vln` is ABANDONED (never touch/delete).
- Honest-verify moat: a step grades GROUNDED only when a deterministic predicate reads an oracle the
  ACTOR cannot author. The sandbox may only get STRICTER (rule 5). `vcli/cognitive/` BYTE-UNCHANGED since 7b220d9.
- cross-MODEL seam (D48): the engine builds a `CapabilityRegistry`, threads names → StrategySelector +
  registry → GoalExecutor; a world registers a `Capability(kind=chat|detector|…)`; the spine grades it,
  it never self-certifies. First real entry: the grounding-dino `detect` capability.
- Acceptance = bare `vector-cli` + NL only (PTY asserts the verify VERDICT); `VECTOR_FAKE_LLM` fakes ONLY
  the network LLM.
- cross-MODEL (D48-D50) + the moat are LIVE on master (merged + pushed 2026-06-23; origin/master cd7029a).

## Pending CEO gates (decision queue — do NOT cross autonomously)
- DEP `timm>=1.0` — CEO-APPROVED 2026-06-23 (EdgeTAM backbone). Merge cross-MODEL→master — DONE + PUSHED.
- cross-EMBODIMENT rebuild; nav→FAR (cmd_vel causation) + explore→TARE; VLN→SysNav venv; real SO-101
  acceptance (gated on `ls /dev/ttyACM*` — absent, sim only). New external deps / new-or-changed
  interfaces / hardware / security all route here.
