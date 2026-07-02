# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R188 (E25) — ordinal NL resolution confirmed on the real face
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R188 (E25) — FRONTIER ordinal NL. Real bare-REPL, deepseek-v4-flash, in-process.
  "把最右边的瓶子..." x2: BOTH runs resolved rightmost→BLUE (non-central y=2.78, NOT default
  green) via describe_scene+detect → perception_grasp(query=blue). Run1 grasped blue CAUSED,
  EYES=only blue off table (green+red untouched) → then 拿过来=handover release → RAN 1/2
  (D182 neg_green pattern). Run2 targeted blue but grasp MISSED (UNCAUSED) → RAN 0/9 (blue-
  bottle grasp variance D137/8). Resolution 2/2, grasp 1/2; no false-green. Ordinal→object
  fidelity WITNESS-certified (D182 gap). §1c done: R187 checker fix promoted to D183 [RULING].

frontier: clean ordinal GROUNDED (grasp-reliable target + non-handover utterance); then
  quantity ("两个") + ambiguity ("那个"/"它"); world-owned spatial grounder kills the fragility

blocked: provider credit for OpenRouter-N≥4 + the automated VLM vision-judge (external, queued)

next:
  1. [FRONTIER] clean ordinal GROUNDED — re-run 最右/最左 with a grasp-reliable target (red can)
     + a NON-handover utterance (e.g. 把最右边的拿起来放到架子上) to convert E25's resolution-
     confirmed (2/2) result into a GROUNDED acceptance row. Eyes = the NL-intent witness.
  2. [FRONTIER] quantity ("两个"/"两瓶") + ambiguity ("那个"/"它" anaphora); push N-to-first-fail
     per phrasing on v4-flash. Bank each failure mode as a Casebook case, not just a count.
  3. [FRONTIER] g1 GROUNDED nav — non-gated build on the confirmed g1.navigation 2/2 base;
     VLN GROUNDED accept stays gated (near_object spine, D178).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-187-1 CROSSED+PROMOTED (self-approved; audit `git log --grep=CEO-APPROVED @ HEAD~R187`):
    checks_schema.py supersession-awareness → landed as D183 [RULING] this round (§1c done).
  - SPINE (D182): actor-authored verify target — witness- not oracle-certified; candidate =
    world-owned NL→object grounder feeding the verify target (would also fix E25 fragility).
  - META: plug-and-play verify-predicates — `_PREDICATE_ORACLES` hardcoded kernel list.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · S8 retire legacy producer
    · relational near(a,b) · S4 driver / S5 policy / S6 capability · BILLING (external).
  - RELEASE: restructure merge to master = release gate (owner).
last_review: R182-restructure (owner session 2026-07-01/02)
