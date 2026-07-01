# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · R-boundary (D170) — plug-and-play kernel↔world boundary now EXECUTABLE + a drift fixed. Offline substrate round; acceptance face STILL DOWN (billing).
HARD BLOCKER (Yusen-only, NOT code): DashScope/Qwen account in ARREARS ("Arrearage", HTTP 400) — re-confirmed
LIVE this round on BOTH qwen-max (planner) AND qwen3-vl-plus (eyes). The bare `vector-cli`+NL acceptance face —
the ONLY face for CAPABILITY claims — cannot run until Yusen tops up Alibaba Cloud / DashScope. No capability
re-verify possible; loop pivoted to non-gated OFFLINE substrate work (per discipline).
DID this round (D170, d47460b — OFFLINE, no-LLM, ground truth = the import graph, not the actor): made Invariants
3+4 EXECUTABLE. Found+fixed drift: worlds/__init__.py eagerly imported DevWorld+RobotWorld → importing the kernel
leaked concrete worlds. Fix = LAZY PEP-562 re-exports (identity-equal, seam no longer drags in a world). NEW
tests/vcli/test_plug_and_play_boundary.py (TDD RED→GREEN): fresh-subprocess kernel-import purity + a synthetic
BYO world driven through every seam with ZERO kernel edits. Verify: boundary 5/5 + world/registry/capability 79/79
green; all consumers import. NOT a capability re-acceptance (that stays billing-blocked).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   BLOCKED for CAPABILITY work (billing). Substrate/architecture work proceeds offline.
owns:    vcli/worlds/__init__.py (lazy re-exports), tests/vcli/test_plug_and_play_boundary.py (NEW boundary guard).
         Spine vcli/cognitive/ + arm_sim_oracle verify predicates FROZEN. scratchpad/* harnesses unchanged.
blocked: DashScope/Qwen ARREARS → capability acceptance face (planner+eyes) DOWN. Yusen must restore billing.
         Loop stays alive on offline substrate/design work. CEO gates queued below.
next: (capability items #1-#3 need the ACCEPTANCE FACE = BLOCKED until billing; run scratchpad/repl_accept.py — it arrears-preflights, exit 4 fast)
  0. [UNBLOCK, Yusen] restore DashScope/Qwen billing. Verify: repl_accept.py preflight prints "LLM reachable".
  1. [FIRM D169] combo N≥3 (eyes-frame already discharged) — needs the LLM.
  2. [FRONTIER] harder NL: relational place "放到X旁边" (near(a,b) predicate = spine-semantics gate); 2-object
     sequences; ambiguous-ref clarification — all need the LLM.
  3. [FRONTIER] g1 2nd embodiment config-only — D170 PROVES the seam is genuinely open (BYO world, no kernel
     edits). Registration mechanism = S4 gate; a pure config still needs the LLM face to REAL-VERIFY end-to-end.
  4. [OFFLINE, if billing stays down] more substrate hardening: extend the boundary guard to cli.py's load path
     (assert no domain-world leak); add a real BYO-world example under examples/; audit other import-time side
     effects (mcp/__main__ runs on `-m` only = fine, but smokes must skip __main__).
  5. [GATE — queued] resting_on_receptacle object-BLIND + absolute count≥1: identity+delta = stricter-only SPINE
     change → present as a gate (multi-object place moat weakness).
tooling (scratchpad/, git-tracked): repl_accept.py (BARE-REPL pexpect driver — the true face; arrears-preflights →
  exit 4 fast if billing down), place_eyes_probe.py (NO-LLM skill-direct pick→place eyes frame), catfirm_campaign.sh
  / catplace_firm.sh, dino_probe.py, grasp_probe.py, measure_qwen.py (-p probe, NOT the face).
  GOTCHAS: `rosm nuke --yes` between sims, NEVER pkill mujoco; NEVER kill the loop supervisor / sibling round /
  session MCP (stdio) — reap only dead-scope debris; import smokes must EXCLUDE `__main__` modules (they run on import).

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **relational-place near(a,b) predicate** (D169 next): a NEW verify predicate for "放到X旁边" → spine-semantics gate. Design + present.
- **D168-place-oracle** resting_on_receptacle object-BLIND + absolute-count: harden to identity+delta (stricter-only
  spine change) so multi-object place can't credit a pre-existing/wrong object. → go/no-go (spine-semantics gate).
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg sites onto should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **S3c** navigate planner-plugin (DESIGN done ADR-001; GATED, recommend DEFER at N=2). → go/no-go, batched.
- **D106** receptacle place oracle: spine piece APPROVED+BUILT+moat-proven (D116); non-gated plumbing REMAINS.
- **find-and-grasp #4/#5 (OPEN, CEO-gated):** #4 external-explore integ + persist + `/rebuild`; #5 startup room-seed +
  `config/worlds/<world>.yaml` + unify SceneGraph store (retire WorldModel/SysNav).
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
