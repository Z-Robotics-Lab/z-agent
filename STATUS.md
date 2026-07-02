# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R191 (E27) — RECOVERY: cleared R190 append-only quarantine (benign reformat)
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R191 (E27) RECOVERY. R190 quarantined: acceptance+experiments.jsonl "deletions w/o
  CEO-APPROVED". ROOT (benign): R190 re-dumped 2 EXISTING rows via a json round-trip (R184 runs
  +", "; R187 —→literal em-dash) — byte-identical content, numstat scores it a DELETION → gate
  FAILED correctly. Fix: accept the reformat (restore=2nd rewrite, compounds), regen stale BOARD,
  lesson E27 (append ONE preformatted line), clear quarantine. No open provisional wedge (all
  superseded; the "8" is a naive literal count). No sim run (recovery). check.sh green.

frontier: clean ordinal GROUNDED (grasp-reliable target + non-handover utterance); then
  quantity ("两个") + ambiguity ("那个"/"它"); world-owned spatial grounder kills the fragility.
  AMBITION: grounding cadence slow (last NEW GROUNDED = R186); plug-and-play thesis is
  GATE-BLOCKED (grounder/VLN/S4-S6 all CEO-gated) — highest leverage needs a CEO call.

blocked: provider credit for OpenRouter-N≥4 + the automated VLM vision-judge (external, queued)

next:
  1. [FRONTIER] clean ordinal GROUNDED — SCENE PINNED (R191 recon): mujoco_go2.py:216 bodies =
     bottle_green y=10.88 (dead-ahead), bottle_blue y=2.78, can_RED y=3.22. R188 miss was blue
     being grasp-VARIANT (D137/8) + 拿过来 handover-release (D182). FIX: target the RED CAN
     (grasp-reliable, R168/R183) via an ordinal-on-OBJECT utterance (最右/最左的东西, NOT 瓶子)
     + a NON-handover verb (抓起来/举起来, verify holding_object persists). repl_accept MODE=fetch.
     Confirm y-sign→ordinal first (R188: blue y=2.78=rightmost-bottle; is can y=3.22 更左?).
  2. [FRONTIER] quantity ("两个"/"两瓶") + ambiguity ("那个"/"它" anaphora); N-to-first-fail per
     phrasing on v4-flash. Bank each failure mode as a Casebook case, not just a count.
  3. [HARNESS] g1_accept GREEN honest-negative flails ~14 turns before finish (blows 400s) —
     cap turns / prompt earlier honest-stop before the next g1 skeptic re-run (R190 lesson).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — witness- not oracle-certified; candidate =
    world-owned NL→object grounder feeding the verify target (would also fix E25 fragility).
  - META: plug-and-play verify-predicates — `_PREDICATE_ORACLES` hardcoded kernel list.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · S8 retire legacy producer
    · relational near(a,b) · S4 driver / S5 policy / S6 capability · BILLING (external).
  - RELEASE: restructure merge to master = release gate (owner).
last_review: R190
