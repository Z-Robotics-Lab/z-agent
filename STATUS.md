# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R197 (E33) — ordinal fetch CONFIRMED: opposite-ordinal red-team GROUNDED 2/2
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R197 (E33) — ADJUDICATED R196 ordinal provisional → CONFIRMED. Reproduced 把最左边的瓶子拿过来
  →green GROUNDED verified=True (1/1, 0 handover, green held aloft) across the round boundary on v4-flash.
  ADVERSARIAL red-team: opposite ordinal 把最右边的瓶子拿过来 → blue (rightmost bottle) GROUNDED
  verified=True (1/1, 0 handover, blue held aloft, eyes-confirmed). Resolver is genuinely DIRECTION-
  sensitive (leftmost=green, rightmost=blue), NOT a lucky green default — the opposite-ordinal is what
  proves a spatial resolver real. Promoted R196→confirmed; superseded R188/R195 ordinal provisionals.
  fetch.nl-ordinal-spatial now CONFIRMED on BOARD (2/2). NO code change (pure adjudication+verify round).

frontier: ordinal fetch CONFIRMED bi-directional (E33). RAISE (STATUS next): quantity (两个/两瓶 — gripper
  holds ONE, needs place/stage between grasps) + anaphora (那个/它 → last-referenced object). AMBITION: a
  world-owned NL→object spatial grounder (D182 spine, CEO-gated) removes model-strategy fragility.

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  Ollama model is the plug-and-play workaround for the perception VLM (recipe: LESSONS/.env.example).
scene (real mujoco_go2 room XML): blue(y=2.78,r=.028)=rightmost-BOTTLE, green(y=3.00,r=.028)=leftmost-
  BOTTLE, red_can(y=3.22,r=.033)=leftmost-OBJECT (excl. by 瓶子). larger world-y → smaller cx → leftmost.
  Green/blue grasp-reliable (probe 5/5). Resolver sort(cx): left=[0]=green, right=[-1]=blue (R197 sim ✓).

next:
  1. [FRONTIER] quantity NL — frame as a PLACE task, NOT hold (R197/E34 scope): make_placed_count
     (arm_sim_oracle.py:183) ALREADY counts resting GT objects in a region, so 把两个瓶子放到架子上 →
     placed_count>=2 is the predicate. Build: sequential grasp+place of 2 bottles + native_loop
     decomposition; add a quantity mode to repl_accept.py; bank each failure mode as a Casebook case.
     CHECK the D168 place-oracle CEO gate BEFORE any sim (place verify may be gated).
  2. [FRONTIER] anaphora: 它/那个 → last-referenced object; needs turn-local referent memory in
     native_loop (scope prompt-change vs state-seam first).
  3. [DEBT] 6 aging N=1 provisional rows (R168/174/176/177/182/184) — superseded by R183/R186
     (check.sh supersession-aware, non-blocking); batch-close on review R200.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder would fix E25/E30/E32
    model-strategy fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
