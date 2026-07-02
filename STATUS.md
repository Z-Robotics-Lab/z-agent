# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R200 (E37, REVIEW) — skeptic 2/2 re-confirmed on the real face; gates clean
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R200 (E37, review). SKEPTIC pass on the REAL bare-REPL face (deepseek-v4-flash brain +
  local Ollama gemma4:e4b eyes, launch_explore empty = in-process): (1) place.nl-plain-colour re-confirmed
  GROUNDED 2/2 — eyes: green bottle IN the receptacle, blue+red untouched; (2) fetch.nl-negated-distractor
  re-confirmed GROUNDED 1/1 — eyes: gripper holds RED can, green+blue untouched. §1b: R199 quantity-place.nl
  provisional → refuted (E36 brain-decomposition, machinery correct). LESSONS: folded ordinal E30/E31 saga to
  1 line (settled by E33); added AMBITION-CRITIC frontier line. WIRING verified-against e7adec0=R182 (18r<25,
  not due). Sim-cap FIX: use `systemd-run --user --scope -p MemoryMax=26G` (RSS cap), NOT `ulimit -v 24G`
  (virtual cap starves OpenBLAS → false OOM RED — see next).

frontier: AMBITION CRITIC (R200): ~10 rounds refined single-object NL on ONE frozen 3-object go2 scene, all
  witness-only (D182). Risk = LOCAL HILL. PIVOT candidates BEFORE more NL variants: (a) world-owned NL→object
  grounder (kills witness-only, unblocks robustness, D182 spine gate) or (b) a 2nd world/scene variant to
  actually prove plug-and-play. Nearer floor: quantity-place brain-decomposition guardrail (E36) then re-verify.

next:
  1. [FRONTIER] quantity-place: ISOLATE R199 blocker (grasp-EXECUTION stall vs brain DECOMPOSITION) with a
     2-turn probe — after a blue place, can the brain grasp+place green ALONE? If yes → land a native_loop
     QUANTITY guardrail (forbid navigate-as-goal in a place plan; explicit per-object grasp→place loop), re-verify.
  2. [PIVOT] ambition: prove plug-and-play breadth — either the world-owned NL→object grounder (D182, CEO-gated)
     or add a 2nd scene/world variant, rather than another single-object NL variant on the same frozen scene.
  3. [FRONTIER] anaphora: 它/那个 → last-referenced object; turn-local referent memory (prompt vs seam).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SELF-APPROVAL AUDIT (R200 review, since last_review R190): only crossed gate = G-187-1 (R187, CEO-APPROVED
    self-delegate: provisional age-check supersession-awareness) — D183 [RULING] filed, checker manifest-hashed.
    G-183-12 (ELP wiring) fully closed (answered+crossed a64149f). No un-audited self-approvals.
  - SPINE (D182): actor-authored verify target — world-owned NL→object grounder would fix witness-only fidelity
    + E25/E30/E32 model-strategy fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6 ladder ·
    BILLING (external: VLM-judge + BYO-N≥4) · RELEASE: restructure merge to master (owner).
last_review: R200
