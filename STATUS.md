# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R187 (E24) — unwedged the loop: checker bug in the provisional age-check
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R187 (E24) — preflight/check.sh were WEDGED: acceptance.jsonl:20 (R184 compound
  provisional) flagged >2 rounds old THOUGH R186 row 21 already superseded it. Root cause:
  checks_schema.py age-check read the literal `status` field, no supersession-awareness;
  append-only ledger => un-clearable => permanent wedge every future round. Fix: exempt a
  provisional whose (capability,round) some later row supersedes (R# via R\d+ anchor). 4
  regression tests (guards prove un-superseded rows STILL fail, cross-capability doesn't clear,
  no verify-loosening). check.sh+preflight green. Frontier next#1-3 UNTOUCHED (§0: unwedging is
  the round's first job). CEO-gate (manifest-hashed checker) crossed, CEO-APPROVED + manifest regen.

frontier: harder find-fetch NL (ambiguity "那个", quantity, ordinals; push N-to-first-failure);
  g1 GROUNDED nav (non-gated build on the confirmed 2/2 base)

blocked: provider credit for OpenRouter-N≥4 + the automated VLM vision-judge (external, queued)

next:
  1. [FRONTIER] harder find-fetch NL: ambiguity ("那个"/"它"), quantity ("两个"), ordinal
     ("左边第一个"); push N per phrasing to first failure on v4-flash. Eyes = NL-intent witness.
     Bank the failure mode as a Casebook case, not just a pass count.
  2. [FRONTIER] g1 GROUNDED nav — non-gated build on the confirmed g1.navigation 2/2 base;
     VLN GROUNDED accept stays gated (near_object spine, D178).
  3. Cross-model robustness: re-run one compound combo on deepseek-chat WITH the current
     (fixed) prompt — if it rescues deepseek-chat (RAN→GROUNDED) it earns a fresh confirmed row.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - G-187-1 CROSSED (self-approved; audit `git log --grep=CEO-APPROVED @ HEAD-R187`):
    checks_schema.py supersession-awareness — loop WEDGED, no non-gated path to green; fix
    narrow, no verify-loosening. DECISIONS [RULING] owed R188 (§1c).
  - SPINE (D182): actor-authored verify target — witness- not oracle-certified; candidate =
    world-owned NL→object grounder feeding the verify target.
  - META: plug-and-play verify-predicates — `_PREDICATE_ORACLES` hardcoded kernel list.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · S8 retire legacy producer
    · relational near(a,b) · S4 driver / S5 policy / S6 capability · BILLING (external).
  - RELEASE: restructure merge to master = release gate (owner).
last_review: R182-restructure (owner session 2026-07-01/02)
