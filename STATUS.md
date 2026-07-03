# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R217 (E49 confirmed) VERIFY — adjudicated R216 g1-nav cross-embodiment provisional
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R217 (E49, VERIFY). Adjudicated the R216/E48 g1.navigation cross-embodiment provisional across a
  round boundary. Re-ran g1_nav_accept on the bare face with the CURRENT brain (deepseek-v4-flash) at
  NON-MEMORIZED coords (12,3)/(11,4) — different from R216's (9,3)/(10,4). Result GROUNDED 1/2: legA (12,3)
  GROUNDED verified=True actor=CAUSED → independent non-memorized reproduction (R216 was not a fixed-pair fluke).
  legB (11,4) RAN/UNCAUSED = HONEST-UNREACHABLE, probe-proven: plan_path→inf (goal inside an inflated obstacle,
  66-obstacle g1 room), navigate_to reason=unreachable moved_m=0 → the verify MOAT refused to fabricate an arrival.
  So R216's cross-embodiment nav is CONFIRMED as a capability; the "2/2" strength refines to reachable-only. Added
  a G1_NAV_A/B coord override to the harness. Side-findings: (a) sim-teardown does NOT reap in-process no-ROS2 sims
  (double-drove 2 g1 sims mid-round → killed by PID, LESSONS hazard); (b) round env selects the qwen/dashscope
  provider, billing-blocked (Arrearage) — deepseek unaffected. eyes=self-read (g1-nav renders no frame).

frontier: Cross-embodiment nav CONFIRMED live with the current brain at a non-memorized coord + moat refuses
  unreachable targets. Plug-in surface is NOT the bottleneck. Un-crossed bars, in order: (1) a genuinely-NEW 3rd
  embodiment (BYO URDF+manifest) — needs S4 one-generic-driver (CEO-gated) + new model assets = multi-round SDD;
  (2) the D182 world-owned NL→object grounder (CEO spine gate) to kill witness-only; (3) welds+colour maps still
  HARDCODED per-object (S4/D182).

next:
  1. [FRONTIER/breadth] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-driver
     (CEO-gated, WIRING:53) + new MuJoCo assets, scope as multi-round SDD. Non-gated proxy until S4: a clean g1-nav
     2/2 at TWO probe-verified REACHABLE non-memorized coords, or refresh g1.perception with the current brain
     (BOARD row is deepseek-chat, 27 rounds stale) — same rationale as R216/R217.
  2. [adjudicate] no live provisionals pending (R216 g1-nav adjudicated). §1c: E49 confirmed is a DECISIONS
     candidate only if it hardens to an invariant.
  3. [FRONTIER/robustness] land the D182 world-owned NL→object grounder (CEO spine gate) so grasp-vs-wander stops
     being model-strategy/placement-dependent.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). META: `_PREDICATE_ORACLES` hardcoded; object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217, VLM-judge still down) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R217.
last_review: R210
