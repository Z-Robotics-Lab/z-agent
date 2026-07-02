# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R192 (E28) — CLEAN ordinal GROUNDED (最左边的瓶子→green, 1/1, eyes-confirmed)
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model;
      plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R192 (E28) FRONTIER win — next#1 delivered: clean ordinal GROUNDED on the bare REPL.
  Two-run A/B: run1 the perception VLM's cloud default was out of credit (402) → model passed raw
  "最左边的瓶子" to perception_grasp → 0/5 (E25 reproduced). run2 routed the perception VLM to a
  LOCAL model (plug-and-play, no credit, existing seam — recipe: LESSONS/.env.example) → `look`
  resolved 最左→green → grasp pickable_bottle_green, holding_object CAUSED → GROUNDED 1/1.
  Eyes(var/evidence/R192/eyes_fetch.png): GREEN held raised, blue+red untouched → no false-green.
  A/B isolates the perception VLM as THE ordinal resolver. CAVEATS: N=1; fidelity witness-only
  (D182). Acceptance + E28 banked; promote next-round after a boundary + red-team.

frontier: clean ordinal GROUNDED is a FLOOR now. RAISE: robustness (N runs; 中间的/最右边的东西→can)
  → quantity (两个/两瓶) → ambiguity (那个/它). AMBITION: grounding is model+VLM-fragile (E25/E28) AND
  the perception VLM is BILLING-gated — the world-owned spatial grounder (D182 spine) fixes both; CEO-gated.

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  model is the plug-and-play workaround for the perception VLM only (recipe: LESSONS/.env.example).

scene (real mujoco_go2 room XML — corrects prior x/y mislabel): x≈10.9, collinear along y,
  rightmost=smallest y (R188 最右→blue): blue(2.78)=rightmost, green(3.00)=middle/leftmost-BOTTLE
  (grasp-reliable R190), red_can(3.22)=leftmost-OBJECT (blue grasp-variant D137; red CAN excl. by 瓶子).

next:
  1. [FRONTIER] ordinal ROBUSTNESS — re-run 最左边的瓶子→green N≥3 (local-VLM route) for a confirmed
     row, THEN a NEW ordinal that lands on the CAN: 最右边的东西/物体 (not 瓶子) — verify y-sign first.
  2. [FRONTIER] quantity (两个/两瓶) + ambiguity (那个/它 anaphora); bank each failure mode as a
     Casebook case, not just a count (needs the local-VLM route while cloud is 402).
  3. [HARNESS] g1_accept GREEN honest-negative flails ~14 turns before finish (blows 400s) — cap
     turns / prompt earlier honest-stop before the next g1 skeptic re-run (R190 lesson).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder feeding it would
    fix E25/E28 fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
