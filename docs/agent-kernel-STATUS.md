# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D174 (IN FLIGHT) — PLACE compound now GROUNDS on the bare REPL via DeepSeek, REFUTING
D171's "place routes to legacy VGG". D171's finding predated the D172 sim-start harness fix; on the FIXED harness a
single compound utterance "把绿色的瓶子拿过来放到架子上" decomposes native perception_grasp→mobile_place and grounds.
- REAL-VERIFY (bare vector-cli+NL, VECTOR_PROVIDER=deepseek→deepseek-chat, MODE=combo, in-process launch_explore=False,
  sim torn down after): GREEN combo → `perception_grasp → holding_object('pickable_bottle_green') ✓ (actor=CAUSED)` +
  `mobile_place → resting_on_receptacle() ✓ (actor=NOT_GRADED)` → `verdict GROUNDED verified=True (2/2)`. EYES
  (verdict PNG, read by me): green rests on the receptacle/shelf, gripper EMPTY, blue+red still on source table —
  oracle + eyes agree. BLUE + RED combos firming now (one sim at a time, nuke between).
- RED-TEAM: bare REPL (no -p/--sim-go2, sim by NL); in-process proven; grasp verify is object-SPECIFIC + CAUSED;
  DeepSeek live (pinged). RESIDUAL (honest, flagged): N=1 so far per colour; resting_on_receptacle is the object-BLIND
  NOT_GRADED oracle (D168 gate below) — grounded on current spine, would tighten under D168.

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/CAPABILITY/MODEL; plan·route·
         verify·recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   FETCH firm 3 colours (D172/D173); PLACE compound now grounds on the true face via DeepSeek (D171 refuted).
owns:    scratchpad/repl_accept.py MODE=combo runs. No product code touched this round.
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (I substitute by reading the offscreen render). NOT loop-blocking
         — DeepSeek carries the planner face. Yusen top-up restores VL 2nd-witness + a 2nd brain.
next:
  1. [FINISH D174] blue+red combo results in; if all 3 ground, PLACE is accepted across colours on the true face.
  2. [FRONTIER] harder NL: relational near() place ("放到瓶子旁边" — spine-semantics gate), multi-object, negation.
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
