# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D173 — the D172 "red 0/3 = grasp-robustness ceiling" was a FALSE CEILING (a transient).
Debug Protocol (DEBUG.md) refuted it: red-can grasp is ROBUST 8/8 (4/4 skill-direct + 4/4 bare-REPL). RED now
GROUNDS on the true face -> all 3 colours (green/blue D172, red this round) accepted by NL. Fetch firmed across colours.
- WHY D172 was wrong: red is a CAN (pickable_can_red r=0.033), not a bottle; weld is center-based so radius is
  irrelevant. Skill-direct grasp succeeds 4/4 with BOTH the correct term "红色的罐子" AND D172's wrong term
  "红色的瓶子". So neither physics nor the term explains 0/3 -> it was a one-off transient, mislabeled as a ceiling.
- REAL-VERIFY (bare vector-cli+NL, VECTOR_PROVIDER=deepseek, in-process launch_explore EMPTY x4, nuke between):
  "把红色的罐子拿过来" x3 -> verified=True (1/1) each; "把红色的瓶子拿过来" (wrong term) -> verified=True.
  Eyes x3 (redcan1/redcan3/redwrong): red CAN held aloft, green+blue on table. Oracle + eyes agree. NL-robust to
  the colloquial "bottle" term. No code change — a false-ceiling correction (grasp_probe.py + repl_accept.py guard it).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/CAPABILITY/MODEL; plan·route·
         verify·recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   FETCH re-accepted across ALL 3 colours on the true face (green/blue/red). Grasp "ceiling" disproven.
owns:    DEBUG.md (D173 Hypothesis Loop). No product code touched — grasp physics/perception/spine all UNCHANGED.
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (I substitute by reading the offscreen render). NOT loop-blocking
         — DeepSeek carries the planner face. Yusen top-up restores VL 2nd-witness + a 2nd brain.
next:
  1. [PLACE via DeepSeek, harness now reliable] re-run PLACE (MODE=place) + compound (MODE=combo) via DeepSeek on
     the FIXED sim-start harness — D171's "place routes to legacy VGG" finding PREDATES the D172 harness fix AND
     DeepSeek native tool-use is now proven fine for fetch, so re-check before trusting it. Firm 3 colours N≥3.
  2. [FRONTIER] harder NL: relational near() place ("放到瓶子旁边" — spine-semantics gate), multi-object, negation.
  3. [FRONTIER] OpenRouter 3rd brain (model-id 404) → real multi-model plug-and-play on one face.
  4. [FRONTIER] g1 2nd embodiment config-only (seam proven open D170); BYO skill.
tooling: scratchpad/repl_accept.py (BARE-REPL pexpect driver = the true face; args FETCH PLACE TAG MODE;
  VECTOR_PROVIDER=qwen|deepseek|openrouter; MODE=fetch|place|both|combo). scratchpad/grasp_probe.py (skill-direct,
  deterministic, ~35s/run — fast root-cause without the LLM/harness). eyes frame = /tmp/repl_accept/<tag>/eyes_<mode>.png
  (READ it). GOTCHAS: `rosm nuke --yes` between sims, NEVER pkill mujoco; NEVER kill supervisor/sibling; keep each
  foreground REPL timeout <10min so an outer wrapper can't cut it mid-run and leak a sim.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go. (Re-check
  place-routing on the fixed harness first — next#1 — before acting on D171's implication.)
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change) so multi-object place can't credit a pre-existing/wrong object. → go/no-go (spine-semantics gate).
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
