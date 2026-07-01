# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · R-arrears — ACCEPTANCE FACE DOWN (DashScope billing), FIRM-D169 eyes-frame discharged OFFLINE.
HARD BLOCKER (Yusen-only, NOT code): the DashScope/Qwen account is in ARREARS ("Arrearage"/overdue-payment, HTTP 400).
Both the planner (qwen-max) AND the eyes judge (qwen3-vl) route through this one key, so the bare `vector-cli`+NL
acceptance face — the ONLY face — cannot run at all. Confirmed by a direct API probe + a live combo attempt that
fell back to a no-op (0/1). NO real-verify possible until Yusen tops up the Alibaba Cloud / DashScope account.
DID (offline, no-LLM): FIRM-D169's eyes-frame half — scratchpad/place_eyes_probe.py drives the REAL skill-direct
pick→place (resting_on_receptacle=1, stable @t2), fires the EXACT verdict-hook snapshot at grasp AND placed state.
Eyes read-back: placed frame shows the green bottle resting ON the receptacle, dog docked, gripper released →
CONCLUSIVE. Since the REPL fires ONE verdict_*.png at turn-end (cli.py:543 = placement state; strips off), the combo
eyes frame IS the placement ⇒ D169's grasp-time-frame caveat is discharged on the mechanism. Harness hardened:
repl_accept.py now LLM-preflights, exits 4 in ~2s on arrears (no 8-min timeout vs a dead API).

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   BLOCKED (acceptance face down, billing). Offline eyes-frame proof landed; combo N≥3 waits on billing.
owns:    scratchpad/place_eyes_probe.py (NEW no-LLM eyes-frame proof), scratchpad/repl_accept.py (arrears preflight),
         docs/*. Code untouched this round. Spine vcli/cognitive/ + arm_sim_oracle verify predicates FROZEN.
blocked: DashScope/Qwen ARREARS → acceptance face (planner+eyes) DOWN. Yusen must restore billing; nothing on the
         true face can proceed until then. Loop stays alive (offline/design work only). CEO gates queued below.
next: (##1 needs the ACCEPTANCE FACE = BLOCKED until billing restored — run repl_accept.py; it arrears-preflights)
  0. [UNBLOCK, Yusen] restore DashScope/Qwen billing (Alibaba Cloud top-up). Verify: `python -c` API probe returns 200,
     or repl_accept.py preflight prints "LLM reachable". EVERYTHING on the true face is dead until this clears.
  1. [FIRM D169 — eyes-frame DONE offline] only combo N≥3 (currently N=1) remains, and it needs the LLM. The final-
     placement eyes frame is ALREADY proven conclusive (scratchpad/place_eyes_probe.py, no-LLM); the REPL snapshots at
     turn-end = placement state (cli.py:543), so the live combo frame will BE the placement. Just re-run combo3 ×3+ once billing is back.
  2. [FRONTIER] relational place "把罐子放到瓶子旁边" (put the can NEXT TO the bottle) — needs a near(a,b) GT predicate.
     Adding a new verify predicate = likely a spine-semantics CEO gate → design + present, do not cross.
  3. [FRONTIER] 2-object sequences ("把红色的和蓝色的都放到架子上"); spatial goals; ambiguous-ref clarification.
  4. [GATE — queued] resting_on_receptacle object-BLIND + absolute count≥1 (no baseline): latent moat weakness for
     MULTI-object place. Harden to identity+delta = stricter-only SPINE change → present as a gate.
  5. [LATER FRONTIER] VLN/SysNav multi-room; 2nd embodiment g1 config-only (Invariant 3, S4 gate); BYO model/skill.
     Track B guardrails (G1..G5) queued (G3↔C(b) VECTOR_NO_ROS2 reconcile noted).
tooling (scratchpad/, git-tracked): repl_accept.py (BARE-REPL pexpect driver — the true face; MODE fetch/place/both/combo;
  combo syncs on grounded) verdicts + braille-strips; NOW arrears-preflights → exit 4 fast if billing down),
  place_eyes_probe.py (NO-LLM skill-direct pick→place → renders the verdict-hook eyes frame; usable while billing down),
  catfirm_campaign.sh / catplace_firm.sh (firm harnesses), dino_probe.py (grounding-dino), grasp_probe.py (skill-direct),
  measure_qwen.py (-p probe, NOT the face).
  GOTCHAS: combo eyes frame is GRASP-time (snapshot fires on the first verify); match launch_explore\.sh + exclude claude;
  pexpect codec_errors='replace'; `rosm nuke` between sims; NEVER kill the loop supervisor / a sibling round (reap only dead-scope debris).

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
