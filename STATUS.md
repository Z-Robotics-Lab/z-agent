# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R198 (E35) — quantity-place predicate CORRECTED: placed_count REFUTED, resting_on_receptacle()>=N
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R198 (E35, build) — CODE-LEVEL FINDING (no sim): R197/E34's "quantity = placed_count()
  >=2" REFUTED. go2 pickables spawn z=0.320, place_bin top ~0.31, BOTH above placed_count's floor
  cutoff _LIFT_MIN_Z=0.10 → placed_count() STRUCTURALLY 0 (probe: 0 at start AND 0 with 2 in bin) =
  a structural false-RED. Correct ungated predicate = EXISTING D106 resting_on_receptacle(), which
  RETURNS A COUNT (probe 2 in-bin, 0 start): quantity-place = resting_on_receptacle()>=N — NO spine
  change (same residual as accepted place.nl-plain-colour). Landed: regression test 4/4, native_loop
  QUANTITY-place prompt guidance, repl_accept.py quantity mode. Sim REAL-VERIFY DEFERRED to R199.

frontier: quantity-place predicate CORRECTED (E35). RAISE: REAL-VERIFY the quantity place on the bare
  face (把两个瓶子放到架子上 → 2×grasp+place → resting_on_receptacle()>=2). Then anaphora (那个/它 →
  last-referenced object). AMBITION: world-owned NL→object grounder (D182 spine, CEO-gated).

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  Ollama model is the plug-and-play workaround for the perception VLM (recipe: LESSONS/.env.example).
scene (real go2_room.xml): pickables ON pick_table(10.95,3.0) at z=0.320: blue(y=2.78)=rightmost-
  BOTTLE, green(y=3.00)=leftmost-BOTTLE, red_can(y=3.22). place_bin(10.95,4.60) top~0.31. Green/blue
  grasp-reliable. placed_count (floor z<0.10) CANNOT grade a place here; use resting_on_receptacle().

next:
  1. [FRONTIER] REAL-VERIFY quantity-place on the bare `vector-cli` face (provider/model per
     .env.example, the v4-flash recipe): `python tools/acceptance/repl_accept.py "把两个瓶子放到架子
     上" "" q2 quantity` → collect the 2×(grasp+place) verdicts + final resting_on_receptacle()>=2
     True, eyes on frames. Bank acceptance row quantity-place.nl (provisional). Machinery landed R198.
  2. [FRONTIER] anaphora: 它/那个 → last-referenced object; needs turn-local referent memory in
     native_loop (scope prompt-change vs state-seam first).
  3. [DEBT] 6 aging N=1 provisional rows (R168/174/176/177/182/184) — superseded by R183/R186
     (check.sh supersession-aware, non-blocking); batch-close on review R200.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder would fix E25/E30/E32
    model-strategy fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle (identity+delta; quantity-place
    uses resting_on_receptacle count = SAME residual, not a new gate) · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
