# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R195 (E31) — ordinal SELECTION fixed (passthrough+resolver→green); grasp-miss blocks GROUNDED
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R195 (E31) — WIRED `_resolve_ordinal_target` into perception_grasp (catalog-projection:
  project GT catalog via world_to_pixel → filter category → cx-extreme; sign from geometry). Sim run_a
  REFUTED wiring-alone: brain (deepseek-v4-flash) PRE-RESOLVES 最左边→"blue bottle" (WRONG) and passes a
  COLOUR query, bypassing the resolver (verified=False, blue on floor). FIX: ordinal-PASSTHROUGH prompt
  (native_loop grasp guidance — pass spatial phrases VERBATIM). run_b: query reaches skill VERBATIM,
  resolver correctly SELECTS green — verify holding_object(pickable_bottle_green), eyes-confirmed. SELECTION
  FIXED. But grasp EXECUTION missed (green→floor) → verified=False 1/2. 17 ordinal+34 pgrasp unit green; non-spine.

frontier: ordinal SELECTION deterministic+correct (E31). RAISE: isolate the grasp-EXECUTION miss on the
  ordinal→colour path (why green knocked off despite R190 grasp-reliable), then 把最左边的瓶子→green N≥3
  GROUNDED → confirmed row. AMBITION: a world-owned NL→object spatial grounder (D182 spine, CEO-gated).

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  Ollama model is the plug-and-play workaround for the perception VLM (recipe: LESSONS/.env.example).

scene (real mujoco_go2 room XML, collinear along y, rightmost=smallest y): blue(2.78)=rightmost-BOTTLE,
  green(3.00)=leftmost-BOTTLE, red_can(3.22)=leftmost-OBJECT (excl. by 瓶子). world-y↔image-cx sign
  CONFIRMED R195: larger world-y → smaller cx → leftmost (offline test + sim run_b targeted green).

next:
  1. [FRONTIER] Isolate the ordinal grasp-EXECUTION miss: run_a (blue) AND run_b (green) both knocked the
     target to the FLOOR (verified=False) though SELECTION was correct in b. Debug why the ordinal→colour
     path misses the weld (approach standoff? the ordinal path differs from R190's grasp-reliable green?);
     Hypothesis-Loop in DEBUG.md. Then 把最左边的瓶子→green N≥3 GROUNDED → confirmed row.
  2. [FRONTIER] after ordinal GROUNDED: quantity (两个/两瓶) + ambiguity (那个/它 anaphora); bank each
     failure mode as a Casebook case, not just a count.
  3. [DEBT] 6 aging N=1 provisional acceptance rows (R168/174/176/177/182/184) — batch re-verify on a
     review round (check.sh doesn't block, but the confirmation debt is real).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder would fix E25/E30/E31
    fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
