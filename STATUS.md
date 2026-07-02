# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R183 adopted+recorded (round died on API disconnect mid-flight; owner
         session finished its RECORD per ROUND.md §1a — recovery path exercised for real)
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R183 (E20) — adjudicated ALL 5 backfilled provisional rows on the real bare-REPL
  face (= the independent red-team of the 14h-loop claims): 3 CONFIRMED (negated-distractor,
  category-only, g1.navigation 2/2 legs CAUSED) · 1 REFUTED (compound fetch-place: grasp
  CAUSED but the PLACE leg walk-loops → RAN 1/4) · 1 SUPERSEDED (gpt-4o-mini, credit dead).
frontier: harder find-fetch NL (combo multi-clause, ambiguity, N-to-failure) → LESSONS ## Frontier
blocked: provider credit for OpenRouter-N≥4 + the automated VLM vision-judge (external, queued)

next:
  1. FIX the compound fetch-place PLACE-leg walk-loop (R183 refuted row, 1/4; E9/E10 flaky
     history) — Hypothesis Loop in DEBUG.md, then re-accept MODE=combo on the face.
  2. [FRONTIER] harder find-fetch NL: ambiguity ("那个"), quantity, ordinal; push N per
     phrasing to first failure. Eyes = NL-intent witness.
  3. [FRONTIER] g1 GROUNDED nav — non-gated build on the confirmed 2/2 base; VLN GROUNDED
     accept stays gated (near_object).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — witness- not oracle-certified; candidate =
    world-owned NL→object grounder feeding the verify target.
  - META: plug-and-play verify-predicates — `_PREDICATE_ORACLES` hardcoded kernel list.
  - D178 near_object VLN predicate · D176 cmd_motion driver seam · D168 place-oracle harden ·
    S8 retire legacy producer · relational near(a,b) · S4 generic driver / S5 policy plugin /
    S6 capability exposure · BILLING top-up (external).
  - ELP wiring PR (EvolvingLoop protocol extensions E1-E7: events/rounds/gates JSONL, Round
    trailer, elp.json — touches run.sh/check.sh/ROUND.md) → ~/Desktop/evolvingloop/DESIGN.md.
  - RELEASE: restructure merge to master = release gate (owner).

last_review: R182-restructure (owner session 2026-07-01/02)
