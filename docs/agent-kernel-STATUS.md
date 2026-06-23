# Vector OS — STATUS (resume anchor)

One-page "where are we / what's next". Read this first; the GOAL is in [../CLAUDE.md](../CLAUDE.md)
→ North Star; durable design is [ARCHITECTURE.md](ARCHITECTURE.md); decision history is
[DECISIONS.md](DECISIONS.md); hidden-bug lessons are [tricky-bugs.md](tricky-bugs.md). Per-round
narrative + the campaign plan live in `~/.vector-nano-loop/{journal,campaign}.md`.

updated: 2026-06-23 · R39 — nav+grasp chain now COMPLETES end-to-end (nav→dock→perceive→approach→grasp→weld→lift) and GROUNDS when perception localizes the right object (GREEN real weld+lift, 2.3cm). 2 real perception fixes landed; remaining blocker = detection-selection reliability at the dock framing (GREEN 1/3, RED 0/3). Spine byte-unchanged across 52 decisions.
goal:    agent-orchestration runtime for physical AI — plan · route to the right MODEL/skill ·
         verify each step · recover. Sim-first; bare `vector-cli` + NL is the only acceptance interface.
         CURRENT THRUST: prove the 3 under-proven North-Star axes (route-to-MODEL ✓ now at the ORCHESTRATION layer · cross-embodiment · live orchestration), using the moat to grade each.
phase:   M2 cross-model — a learned detector is the first real 2nd model family, now routed-to BY THE PRODUCER via the
         engine capability-dispatch path (D50), not only inside the grasp skill (D48); colour selection PERCEPTUAL (D49).
owns:    perception/grounding_dino.py, perception/detector_capability.py (now AGENT-bound, lazy cold-turn rebind),
         perception/go2_grasp_perception.py (detect→gdino), skills/perception_grasp.py (named→detector routing +
         CONSUMES a producer box), worlds/robot.py (register_capabilities binds the agent for the rebind).
         (Moat vcli/cognitive/ BYTE-UNCHANGED across 50 decisions; engine auto-threads the capability — no spine edit.)
doing:   R39 — nav+grasp now COMPLETES end-to-end and GROUNDS the right object intermittently (honest, not a landed
         headline). ROOT CAUSE found via Debug Protocol (NOT the A/B-probe "off-axis lateral IK" theory): the grasp
         never grounded because PERCEPTION was silently degraded. Two real, independent fixes (both verified):
         (1) `timm` — ALREADY declared in pyproject (perception extra) but MISSING from .venv → EdgeTAM failed to LOAD →
             coarse box-rect mask → depth centroid averaged can+table → z collapsed to ~0.13 → gripper closed below the
             can → no weld. Synced timm==1.0.27 into .venv (env-sync of a declared dep, NOT a new dependency / not a gate).
         (2) EdgeTAM scores-shape bug (perception/tracker.py:330): transformers>=5 returns object_score_logits (N,1), so
             `float(scores[i])` on a (1,)-array raised TypeError → segment() fell back to box-rect EVERY time even with
             timm present. Flatten scores to 1-D (commit 8f9851e). Verified in isolation: EdgeTAM now returns a real mask.
         RESULT (real sim, decompose→vgg_execute, retries=0, 3 trials each): GREEN grasp_GROUNDED 1/3 (green t1: real
         perceive 2.3cm @ y=3.00 z=0.322 → weld + shoulder lift + holding_object('pickable_bottle_green') TRUE); RED 0/3.
         The chain mechanically completes (FAR→dock converges +X→perceive→_approach_object vy-track→PickTopDown weld→lift).
         Spine vcli/cognitive/ BYTE-UNCHANGED (verified empty diff 7b220d9..HEAD). Probes: scripts/probe_r39_e2e_green_red.py
         (acceptance), probe_r39_reperceive_after_seat.py (proved: do NOT re-perceive after approach — close framing looks
         OVER the table → garbage), probe_r39_debug_floor_vs_cans.py. Artifacts /tmp/r39_e2e/*.png + e2e.json.

blocked: NOT a CEO gate — a perception-quality round. The remaining miss is DETECTION SELECTION at the dock framing:
         the 3 pickable objects (blue y=2.78, green 3.00, red 3.22) are only 22cm apart and the dog perceives them ~0.85m
         away and slightly off-center (the dock leaves a small per-trial pose residual), so grounding-dino's colour
         grounding intermittently picks a NEIGHBOUR's box and the back-projected z sometimes still lands low (table). Per
         trial the perceived xy tracks the dog's dock-residual: green t2 grabbed RED's y, red t1 grabbed BLUE's y, etc.
         KNOWN (spine, do-not-touch): re-plan still drops strategy_params (empty query on retry) — retries pinned to 0.
next:    R40 — perception RELIABILITY at the dock framing (NON-gated, non-spine), to lift GREEN→~3/3 and land RED honestly:
         (a) tighten the dock so the perceive pose is repeatable head-on AND closer-but-not-over-table (a fixed perceive
             standoff where the 3 cans subtend more pixels); (b) constrain detection to the near-table depth band + select
             the box nearest the commanded colour's expected screen region, reject low-z (table) back-projections FAIL-LOUD;
             (c) consider a colour-segmentation cross-check (front_object colour resolver) to disambiguate the 3 close cans.
         Then bare-cli two-turn "启动 go2 带机械臂 → 去桌子那里把绿色的瓶子拿起来" → nav RAN + grasp GROUNDED end-to-end.
         Gated leaps (CEO queue): re-plan strategy_params-preservation (SPINE — D52), cross-EMBODIMENT (g1), explore
         (TARE), VLN (SysNav), merge→master.
         ALSO record for reproducibility: `.venv` must have `timm` (uv pip install 'timm>=1.0'); EdgeTAM backbone
         repvit_m1.dist_in1k fetches from HF on first load (network needed once, then cached).
         Bare vector-cli + NL = ONLY acceptance; spine only STRICTER; never trust skill.success / sub-agent claims.


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
- **NEW DEP added (R39, needs retro-approval/notification): `timm>=1.0` (1.0.27)** added to pyproject + installed
  into .venv to make EdgeTAM actually LOAD (it was the undeclared backbone; EdgeTAM never loaded across the whole
  grasp campaign D17-D51 → masks were box-rect all along). Standard PyTorch-image-models lib, low risk; EdgeTAM
  backbone repvit_m1.dist_in1k fetches from HF once then caches. Surfaced to Yusen — approve/deny.
- Merge/release `feat/orchestrator-redesign` → master.
- cross-EMBODIMENT (g1: removed, zero python — large rebuild) ; nav→FAR + explore→TARE (cmd_vel causation +
  nav-stack colcon bring-up, DQ-15) ; VLN→SysNav venv (DQ-16). New external deps / new-or-changed interfaces /
  hardware / security. Real SO-101 arm acceptance gated on `ls /dev/ttyACM*` (absent — sim only).
