# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R184 (E21) — fixed the compound fetch-place PLACE-leg walk-loop
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R184 (E21) — Hypothesis Loop (DEBUG.md): the compound place clause walk-looped
  because `_native_system_prompt` locomotion_guidance routed "放到架子上" to navigate (H1
  CONFIRMED / H3 mobile_place-bug REJECTED). Fix (native_loop.py, non-spine): place_guidance
  forbids navigate/walk for a place clause; locomotion_guidance scopes navigate to an explicit
  user-given coordinate. Real-face MODE=combo → GROUNDED 3/3, ZERO navigate calls (was RAN 1/4).
  PROVISIONAL: model confound (v4-flash vs R183 deepseek-chat) — A/B isolation owed (next #1).
frontier: harder find-fetch NL (combo multi-clause, ambiguity, N-to-failure) → LESSONS ## Frontier
blocked: provider credit for OpenRouter-N≥4 + the automated VLM vision-judge (external, queued)

next:
  1. ADJUDICATE R184 compound provisional: run the isolating A/B — OLD prompt (HEAD 4f0cf36
     native_loop.py) + SAME deepseek-v4-flash, MODE=combo. Fix-caused ⇒ old still walk-loops;
     model-caused ⇒ old also grounds. Then append confirmed/refuted. (E9/E10 model-sensitivity trap.)
  2. [FRONTIER] harder find-fetch NL: ambiguity ("那个"), quantity, ordinal; push N per
     phrasing to first failure. Eyes = NL-intent witness.
  3. [FRONTIER] g1 GROUNDED nav — non-gated build on the confirmed 2/2 base; VLN GROUNDED
     accept stays gated (near_object).
  4. [HYGIENE] fix test_isaac_sim_proxy MagicMock hot-loop (E18 root cause #2: patched
     time.sleep spins navigate_to's 3s probe; fake clock or bounded side_effect); accept =
     TEST_MEM_GB=4 scripts/run-tests tests/unit/test_isaac_sim_proxy.py green.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — witness- not oracle-certified; candidate =
    world-owned NL→object grounder feeding the verify target. (R184 relevance: the walk-loop
    root was the model AUTHORING at_position(10,5) — a self-authored verify target; the fix
    removed the routing, but bounding actor-authored targets remains this gate.)
  - META: plug-and-play verify-predicates — `_PREDICATE_ORACLES` hardcoded kernel list.
  - D178 near_object VLN predicate · D176 cmd_motion driver seam · D168 place-oracle harden ·
    S8 retire legacy producer · relational near(a,b) · S4 generic driver / S5 policy plugin /
    S6 capability exposure · BILLING top-up (external).
  - RELEASE: restructure merge to master = release gate (owner).

last_review: R182-restructure (owner session 2026-07-01/02)
