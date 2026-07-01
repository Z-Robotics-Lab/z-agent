# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D172 — the acceptance-face "flakiness" was a HARNESS bug, not model/billing. Root-caused
+ fixed; FETCH firmed on the bare REPL via DeepSeek across 3 colours (green✓ blue✓ red✗-grasp), eyes+oracle agree.
- ROOT CAUSE (Hypothesis Loop): sim-start synced on a LIVE `child.expect("sim start go2 ok")` against the raw PTY
  stream, which prompt_toolkit's repaint+braille-spinner splits with ANSI → the marker NEVER matched even though
  the sim really started (`▸ sim start go2 ok 4.2s` was in the log). Drove ~2-3 rounds of false "SIM NEVER STARTED".
- FIXED (scratchpad/repl_accept.py, harness-only, NON-gated): sim-start drains-to-quiet then greps the ANSI-STRIPPED
  log for the GT tool marker (never the model's chat CLAIM); reverted the harmful `_UP` chat-phrase broadening; loud
  MODE guard (bad arg-order no longer burns a 6-min sim); honest early-abort when the sim never starts.
- REAL-VERIFY (bare vector-cli+NL, VECTOR_PROVIDER=deepseek, in-process — launch_explore EMPTY ×3, nuke between):
  GREEN verified=True(1/1) eyes: green held aloft ✓ · BLUE verified=True(1/1) eyes: blue held ✓ ·
  RED verified=False(0/3): detect+route CORRECT (perception_grasp(red can)), GRASP physics failed — honest ✗.

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/CAPABILITY/MODEL; plan·route·
         verify·recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   UN-BLOCKED (DeepSeek brain) + acceptance HARNESS now reliable. FETCH re-accepted (2/3 colours grounded).
owns:    scratchpad/repl_accept.py (harness: GT-only sim-start, MODE guard). Spine vcli/cognitive/ + arm_sim_oracle
         predicates FROZEN (untouched). No kernel/interface edits this round.
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (I substitute by reading the offscreen render). NOT loop-blocking
         — DeepSeek carries the planner face. Yusen top-up restores VL 2nd-witness + a 2nd brain.
next:
  1. [FRONTIER — the honest red 0/3 exposes it] GRASP ROBUSTNESS: why green/blue grasp but red-can 0/3 (pose/IK
     reach). Investigate + firm each colour to N≥3 on the bare face. Grasp, not routing/model/harness, is the ceiling.
  2. [PLACE, harness now reliable] re-run PLACE via DeepSeek (MODE=place then combo) — D171's place run PREDATES the
     sim-start fix, so its "routes to legacy VGG" finding must be re-checked on the fixed harness before trusting it.
  3. [FRONTIER] OpenRouter 3rd brain (model-id 404) → real multi-model plug-and-play on one face.
  4. [FRONTIER] harder NL (relational near() gate) · g1 2nd embodiment config-only · BYO skill.
tooling: scratchpad/repl_accept.py (BARE-REPL pexpect driver — the true face). VECTOR_PROVIDER=qwen|deepseek|openrouter;
  MODE=fetch|place|both|combo (VALIDATED — bad mode exits 1). Redirect stdout to a file (parent pipe lost for orphans);
  eyes frame = /tmp/repl_accept/<tag>/eyes_<mode>.png (offscreen verdict render — READ it). GOTCHAS: `rosm nuke --yes`
  between sims, NEVER pkill mujoco; NEVER kill supervisor/sibling; a cold-start may find a prior tick's sim live — OBSERVE.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go. (D171
  place-routing was implicated, BUT re-check on the fixed harness first — next#2 — before acting.)
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change) so multi-object place can't credit a pre-existing/wrong object. → go/no-go (spine-semantics gate).
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
