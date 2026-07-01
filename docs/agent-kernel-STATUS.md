# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · R-combo (D169) — COMPOUND single-utterance FETCH-AND-PLACE now grounds on the bare REPL.
Frontier probe "把红色的罐子拿过来放到架子上" (fetch AND place in ONE command) FAILED pre-fix: the planner-free
native producer grasped, verified holding_object, and finished — DROPPING the place clause (the sentence LEADS with
拿过来, a grasp trigger). FIX (_native_system_prompt): a FETCH-AND-PLACE guidance block (manipulation-world gated) —
after the grasp verifies, call mobile_place + verify resting_on_receptacle before finish; NEVER finish on grasp alone.
No runner-side clause parsing (MODEL still decides; runner stays planner-free). Verify oracles BYTE-UNCHANGED.

goal:    PLUG-AND-PLAY runtime for physical AI — bring your own robot/policy/skill/capability; plan·route·verify·
         recover. Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   D169 landed — compound fetch+place decomposes + grounds 2/2 (GT moat) on the true face. Frontier continues.
owns:    vector_os_nano/vcli/native_loop.py (_native_system_prompt place_guidance), tests/unit/vcli/test_native_loop.py
         (compound-place prompt test), scratchpad/repl_accept.py (combo sync-on-verdict + braille-strip fix),
         scratchpad/catplace_firm.sh, docs/*. Spine vcli/cognitive/ + arm_sim_oracle verify predicates FROZEN.
blocked: none. CEO gates queued below — do NOT cross.
next:
  1. [FIRM D169] combo N≥3 (currently N=1) AND capture a FINAL-PLACEMENT eyes frame — snapshot_on_verdict fires on the
     GRASP verify, so the combo3 frame is grasp-time + inconclusive on the place; grab a frame at the LAST verdict / pre-quit.
  2. [FRONTIER] relational place "把罐子放到瓶子旁边" (put the can NEXT TO the bottle) — needs a near(a,b) GT predicate.
     Adding a new verify predicate = likely a spine-semantics CEO gate → design + present, do not cross.
  3. [FRONTIER] 2-object sequences ("把红色的和蓝色的都放到架子上"); spatial goals; ambiguous-ref clarification.
  4. [GATE — queued] resting_on_receptacle object-BLIND + absolute count≥1 (no baseline): latent moat weakness for
     MULTI-object place. Harden to identity+delta = stricter-only SPINE change → present as a gate.
  5. [LATER FRONTIER] VLN/SysNav multi-room; 2nd embodiment g1 config-only (Invariant 3, S4 gate); BYO model/skill.
     Track B guardrails (G1..G5) queued (G3↔C(b) VECTOR_NO_ROS2 reconcile noted).
tooling (scratchpad/, git-tracked): repl_accept.py (BARE-REPL pexpect driver — the true face; MODE fetch/place/both/combo;
  combo now syncs on grounded) verdicts + braille-strips the parse), catfirm_campaign.sh / catplace_firm.sh (firm harnesses),
  dino_probe.py (grounding-dino inspector), grasp_probe.py (skill-direct), measure_qwen.py (-p probe, NOT the face).
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
