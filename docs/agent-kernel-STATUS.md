# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D174 — PLACE compound (fetch AND place in one NL command) GROUNDS on the bare REPL via
DeepSeek across ALL 3 colours, REFUTING D171's "place routes to legacy VGG" (a pre-D172-fix harness artifact). On the
FIXED harness DeepSeek's NATIVE loop decomposes "把<色>的{瓶子|罐子}拿过来放到架子上" → perception_grasp→mobile_place→grounds.
- REAL-VERIFY (bare vector-cli+NL, VECTOR_PROVIDER=deepseek→deepseek-chat, MODE=combo, in-process launch_explore=False
  every run, nuke between, one sim at a time): GREEN True(2/2) 1st try · RED-can True(2/2) 1st try · BLUE True(2/2) on
  2nd try (1st = grasp transient holding_object UNCAUSED 0/1, never reached place; re-run grounded). Each grounded run:
  `holding_object('pickable_<obj>') ✓ (actor=CAUSED)` + `resting_on_receptacle() ✓ (NOT_GRADED)` → GROUNDED verified=True.
  EYES (verdict PNGs, read by me): correct-colour object rests on the RECEPTACLE, gripper EMPTY, others at source —
  oracle+eyes agree on all 3; blue's failed run shows empty gripper (agrees with False).
- RED-TEAM: bare REPL (no -p/--sim-go2, sim by NL); in-process proven; grasp verify object-SPECIFIC + CAUSED; DeepSeek
  pinged live. RESIDUALS (flagged): resting_on_receptacle is object-BLIND/NOT_GRADED (D168 gate — now LOAD-BEARING);
  1 grasp transient in 4 attempts; N=1 grounded/colour. Headline = "place grounds across 3 colours", NOT "N=3 flawless".

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/CAPABILITY/MODEL; plan·route·
         verify·recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   FETCH firm 3 colours (D172/D173) + PLACE compound firm 3 colours (D174) — both accepted on the true face via
         DeepSeek (BYO model holds for full fetch-and-place). D171 refuted. Next frontier = harder NL / D168 spine / 2nd model.
owns:    scratchpad/repl_accept.py MODE=combo runs (guard the place compound). No product code touched this round.
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (I substitute by reading the offscreen render). NOT loop-blocking
         — DeepSeek carries the planner face. Yusen top-up restores VL 2nd-witness + a 2nd brain.
next:
  1. [FRONTIER] harder NL: relational near() place ("放到瓶子旁边" — spine-semantics gate D169), multi-object, negation.
  2. [SPINE, high-value] D168 place-oracle identity+delta — now LOAD-BEARING (D174 place leans on the object-blind
     resting_on_receptacle); tightening it is the top spine gate. Queue for Yusen (spine-semantics gate).
  3. [FRONTIER] OpenRouter 3rd brain (model-id 404) → real multi-model plug-and-play on one face.
  4. [FRONTIER] g1 2nd embodiment config-only (seam proven open D170); BYO skill.
tooling: scratchpad/repl_accept.py (BARE-REPL pexpect driver = the true face; args FETCH PLACE TAG MODE;
  VECTOR_PROVIDER=qwen|deepseek|openrouter; MODE=fetch|place|both|combo). scratchpad/grasp_probe.py (skill-direct,
  deterministic). eyes frame = /tmp/repl_accept/<tag>/verdict_*.png (READ it). GOTCHAS: `rosm nuke --yes` between sims,
  NEVER pkill mujoco; NEVER kill supervisor/sibling; combo run ~8min; DeepSeek combo sync = post-hoc parse (live
  pexpect "saw 0 verdicts" is the ANSI-split miss, the raw log holds the real verdict).

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change) so multi-object place can't credit a pre-existing/wrong object. → go/no-go (spine-semantics gate).
  NOW LOAD-BEARING: D174's place verdicts lean on it; the grasp verify (object-specific+CAUSED) is the strong half.
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go. (D171's
  "place→legacy VGG" is REFUTED for DeepSeek combo — native handles it — so S8 is now dead-code removal, not a fix.)
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
