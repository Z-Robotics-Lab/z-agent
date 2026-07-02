# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R199 (E36) — quantity-place REAL-VERIFY on the bare face: REFUTED (honest RED)
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R199 (E36, build) — SIM REAL-VERIFY of R198's quantity-place machinery, bare face
  (deepseek-v4-flash): `把两个瓶子放到架子上` → RAN verified=False (3/4), eyes 1/2 placed. HONEST RED,
  no false-green. Brain grasped+placed bottle 1 (blue, resting_on_receptacle ✓) then ABANDONED bottle
  2 (green) after its grasp stalled → navigate→at_position(10.5,2.9) loop (Case 15 place/navigate
  cross-talk in the QUANTITY context) → terminal verify was at_position, NOT the count. R198 machinery
  CORRECT (oracle path proven on blue); gap = BRAIN DECOMPOSITION of N grasp+place cycles. Banked
  provisional quantity-place.nl (RAN 0/1) + E36 (refuted). No fix: isolate first (E23).

frontier: quantity-place REFUTED on first real verify (E36) — machinery correct, brain won't compose
  N grasp+place. RAISE: land a native_loop QUANTITY decomposition guardrail (forbid navigate-as-goal
  inside a place plan; explicit per-object grasp→place loop) + re-verify. Then anaphora (那个/它 →
  last-referenced object). AMBITION: world-owned NL→object grounder (D182 spine, CEO-gated).

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  Ollama model is the plug-and-play workaround for the perception VLM (recipe: LESSONS/.env.example).
scene (real go2_room.xml): pickables ON pick_table(10.95,3.0) at z=0.320: blue(y=2.78)=rightmost-
  BOTTLE, green(y=3.00)=leftmost-BOTTLE, red_can(y=3.22). place_bin(10.95,4.60) top~0.31. Green/blue
  grasp-reliable. quantity-place graded by resting_on_receptacle()>=N (D106 count oracle); NOT placed_count.

next:
  1. [FRONTIER] ISOLATE the R199 quantity blocker BEFORE any fix: was bottle-2 (green) abandoned by a
     grasp-EXECUTION stall or brain DECOMPOSITION? 2-turn probe — after a blue place, can the brain
     grasp+place green alone? If yes → the gap is multi-object PLANNING → land a native_loop QUANTITY
     guardrail (forbid navigate-as-goal in a place plan; explicit per-object grasp→place loop), re-verify.
  2. [FRONTIER] anaphora: 它/那个 → last-referenced object; turn-local referent memory (prompt vs seam).
  3. [DEBT] adjudicate the R199 quantity-place.nl provisional next round; batch-close the 6 aging N=1
     rows (R168/174/176/177/182/184, superseded, non-blocking) on review R200.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder would fix E25/E30/E32
    model-strategy fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle (identity+delta; quantity-place
    uses resting_on_receptacle count = SAME residual, not a new gate) · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
