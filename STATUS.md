# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R186 (E23) — adjudicated the R184 compound provisional via the A/B
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R186 (E23) — isolating A/B on STATUS next#1: OLD pre-fix prompt (4f0cf36
  native_loop.py) + SAME deepseek-v4-flash + MODE=combo grounded 2/2 (True(2/2)×2, zero
  at_position, no walk-loop-to-failure). Holding prompt=OLD, model deepseek-chat (R183 RAN
  1/4) → v4-flash flips RAN→GROUNDED. Verdict: the R184 prompt fix did NOT drive 1/4→3/3 —
  the MODEL did (E23 CONFIRMED refutation of the E21 causal claim). Fix is still correct+
  harmless. Capability fetch-place.nl-compound CONFIRMED on v4-flash (5/5: R184 3/3 new +
  R186 2/2 old prompt); provisional superseded. Also cleared R185 BOARD-stale quarantine.

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
     (fixed) prompt — if the fix rescues deepseek-chat (RAN→GROUNDED), that is the fix's real
     value and worth a fresh confirmed row; if it still RANs, the fix is purely defensive.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — witness- not oracle-certified; candidate =
    world-owned NL→object grounder feeding the verify target.
  - META: plug-and-play verify-predicates — `_PREDICATE_ORACLES` hardcoded kernel list.
  - D178 near_object VLN predicate · D176 cmd_motion driver seam · D168 place-oracle harden ·
    S8 retire legacy producer · relational near(a,b) · S4 generic driver / S5 policy plugin /
    S6 capability exposure · BILLING top-up (external).
  - RELEASE: restructure merge to master = release gate (owner).

last_review: R182-restructure (owner session 2026-07-01/02)
