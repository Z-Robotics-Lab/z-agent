# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · R-catfix (D168) — COLOURLESS CATEGORY-only find-fetch-place now GROUNDS on the bare REPL.
Root-caused (DEBUG.md + dino_probe): "罐子"→"a can." scores all 3 near-identical cylinders within 0.02 noise, so
max-conf grabbed a RANDOM one (eyes: blue bottle grabbed, can on floor). FIX (perception_grasp._resolve_unique_category):
a colourless category UNIQUE in the scene catalog → resolve to its object+colour → drive the PROVEN colour path.
"罐子"→pickable_can_red(red). Verify oracle BYTE-UNCHANGED (steers the actor only, moat holds).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   D168 landed — category-only fetch+place grounded on the true face. Frontier continues.
owns:    skills/perception_grasp.py (_resolve_unique_category + colour-resolution wiring), perception/grounding_dino.py
         (_ZH_NOUN_EN reused), tests/unit/skills/test_category_resolve.py, scratchpad/{dino_probe,repl_accept}.py, docs/*.
         Spine vcli/cognitive/ + arm_sim_oracle verify predicates FROZEN.
blocked: none. CEO gates queued below — do NOT cross.
next:
  1. [DONE] D168 — colourless unique-category → colour path. REPL FETCH "把罐子拿过来" verified=True (1/1,
     holding_object('pickable_can_red'), eyes=red can grasped, in-process). PLACE "把罐子放到架子上" verified=True
     (2/2, pick+place oracles, eyes=can on receptacle). Skill-direct: weld+lift confirmed. Unit 6/6 + 64 grasp green.
  2. [NOW — firm the number] run N≥3 more category-only fetch+place REPL samples (single-sample re-accept → firm to N≥3).
  3. [FRONTIER] harder NL: multi-clause / relational refs ("把罐子放到瓶子旁边"), 2-object sequences, spatial goals.
  4. [GATE — queued] resting_on_receptacle object-BLIND (ignores target) + absolute count>=1 (no baseline): latent
     moat weakness for MULTI-object place. Harden to identity+delta = stricter-only SPINE change → present as a gate.
  5. [LATER FRONTIER] VLN/SysNav multi-room; 2nd embodiment g1 config-only (Invariant 3, S4 gate); BYO model/skill.
     Track B guardrails (G1..G5) queued (G3↔C(b) VECTOR_NO_ROS2 reconcile noted).
tooling (scratchpad/, git-tracked): repl_accept.py (BARE-REPL pexpect driver — the true face, MODE fetch/place/both),
  dino_probe.py (grounding-dino box/label/score inspector — NEW D168), grasp_probe.py (skill-direct grasp), measure_qwen.py
  (-p probe, NOT the face). GOTCHAS: match `launch_explore\.sh` + exclude claude (loop argv false-positive); pexpect
  codec_errors='replace'; verdict renders `verified=True/False (n/m grounded)` with ANSI splitting `=`; `rosm nuke` between sims.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **D168-place-oracle** resting_on_receptacle object-BLIND + absolute-count: harden to identity+delta (stricter-only
  spine change) so multi-object place can't credit a pre-existing/wrong object. → go/no-go (spine-semantics gate).
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **D106** receptacle place oracle: spine piece APPROVED+BUILT+moat-proven (D116); non-gated plumbing REMAINS (verify
  namespace · height receptacle · arm↔table descent · bare-cli pick-AND-place). Else place = grasp→release.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed +
  `config/worlds/<world>.yaml` + unify SceneGraph store (retire WorldModel/SysNav). Keys → core/scene_graph.py, perception/object_localizer.py.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
