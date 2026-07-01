# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D171 — ACCEPTANCE FACE UN-BLOCKED via bring-your-own model (DeepSeek). FETCH re-accepted
on the bare REPL by NL with a NON-qwen brain; PLACE compound is model-sensitive (routes to legacy VGG). Two sims.
UNBLOCK (no Yusen action needed): qwen/DashScope STILL in arrears (live 400 Arrearage), BUT last round's
provider-agnostic driver (VECTOR_PROVIDER) + a live provider ping found DeepSeek LIVE. The bare `vector-cli`+NL
acceptance face now RUNS via `VECTOR_PROVIDER=deepseek` — the North Star "bring your own model" proven on the true face.
DID this round (REAL-VERIFY, in-process, launch_explore EMPTY):
 (1) FETCH GROUNDED via DeepSeek — "把绿色的瓶子拿过来" → perception_grasp → holding_object('pickable_bottle_green')
     verified=True (1/1), actor=CAUSED; EYES: I read the offscreen verdict frame — green bottle in gripper, others on
     table. Oracle+eyes agree. Red-team: DeepSeek by elimination (qwen 400 can't ground); GT oracle not self-report;
     in-process. RESIDUAL: N=1; eyes read by me not automated VL (VL provider down) — flagged.
 (2) PLACE compound "把绿色的瓶子放到架子上" via DeepSeek = 0 verdicts: routed to LEGACY VGG
     (find_green_bottle/place_bottle_on_shelf → "no strategy matched for 'unmatched'" → VGG FAIL), NOT native ReAct.
     Model-sensitivity + routing finding (native prompt/route tuned on qwen); spine never reached, nothing faked.

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/CAPABILITY/MODEL; plan·route·
         verify·recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   UN-BLOCKED (DeepSeek brain). Capability re-verify RESUMES. FETCH re-accepted; PLACE routing to fix next.
owns:    scratchpad/repl_accept.py (provider-agnostic driver; unchanged this round). Spine vcli/cognitive/ +
         arm_sim_oracle verify predicates FROZEN. No code edits this round (verify + record only).
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES still down (I substitute by reading the render). Yusen: qwen top-up
         restores VL eyes + a 2nd brain. NOT loop-blocking anymore — DeepSeek carries the planner face.
next:
  1. [DEBUG PROTOCOL] WHY does place-led NL route to legacy VGG under DeepSeek while fetch takes native?
     (should_attempt_native vs should_use_vgg × provider/phrasing). Intertwined w/ S8 legacy-producer retirement.
     Fix, then re-attempt PLACE via DeepSeek → full fetch+place BYO-model acceptance.
  2. [FIRM] DeepSeek FETCH N≥3 + 3 colours (red/blue/green) to firm the N=1.
  3. [FRONTIER] OpenRouter as a 3rd brain (fix the model-id 404) → real multi-model plug-and-play on one face.
  4. [FRONTIER, needs LLM face — now available] combo N≥3 (D169), harder NL (relational near() gate), g1 2nd
     embodiment config-only, BYO skill.
  5. [OFFLINE] object-blind receptacle identity+delta predicate design + exec summary (spine-semantics gate).
tooling (scratchpad/, git-tracked): repl_accept.py (BARE-REPL pexpect driver — the true face; VECTOR_PROVIDER picks
  the brain: qwen|deepseek|openrouter; MODE=fetch|place|both|combo; combo captures multi-step verdicts). Driver
  stdout has the [RESULT] line — REDIRECT it to a file (parent pipe is lost for orphaned runs); repl.raw.log =
  REPL child output only. GOTCHAS: `rosm nuke --yes` between sims, NEVER pkill mujoco; NEVER kill supervisor/sibling/
  session MCP; a cold-start may find a prior tick's sim still live — OBSERVE it, don't double-drive.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **S8** retire legacy keyword producer (READY; now ALSO implicated in D171 place-routing): delete IntentRouter/
  StrategySelector/_DIR_MAP + legacy GoalDecomposer; rewire 4 should_use_vgg sites onto should_attempt_native (D74);
  keep VECTOR_LEGACY_TURN hatch. → go/no-go. (Place-compound routed here under DeepSeek — retiring it may fix D171.)
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only
  spine change) so multi-object place can't credit a pre-existing/wrong object. → go/no-go (spine-semantics gate).
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed.
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
