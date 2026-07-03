# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R216 (E48 provisional) VERIFY — CROSS-EMBODIMENT: current brain drives the 2nd embodiment
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R216 (E48, VERIFY). Took the frontier next#1 (a 2nd embodiment) via its NON-gated slice: proved the 2nd
  embodiment (g1 humanoid) is LIVE with the CURRENT brain (deepseek-v4-flash — the brain all recent go2 novel-object
  work uses), not just the 32-round-stale R183 deepseek-chat row. Bare face, g1_nav_accept.py, in-process MuJoCoG1
  (VECTOR_NO_ROS2=1): `走到坐标 x=9,y=3` then `x=10,y=4` -> navigate()+at_position() BOTH legs GROUNDED verified=True
  actor=CAUSED, distinct demanded coords (selectivity). Spawn (10,3) so at_position(9,3) FALSE at spawn -> earned.
  0 kernel edits = pure config plug-and-play. Refreshes the stale g1.navigation headline and answers the R200
  ambition critic (recent work was all go2). eyes=oracle-gt (g1-nav renders no frame; deterministic at_position pose
  is the witness, consistent w/ R183). Provisional -> adjudicate next round. The literal next#1 "one generic driver"
  (S4) + a genuinely-new 3rd embodiment stay a queued CEO gate / multi-round SDD effort.

frontier: Cross-embodiment now proven LIVE with the current brain (go2 arm-fetch + g1 humanoid-nav, same runtime,
  same deepseek-v4-flash, 0 kernel edits). Novel-object grounding robust for colour+geometry. The plug-in surface is
  NOT the bottleneck; the real un-crossed bars, in order: (1) a genuinely-NEW 3rd embodiment (BYO URDF+manifest) —
  needs the S4 one-generic-driver (CEO-gated) + new model assets = a multi-round SDD effort, > re-verifying existing
  worlds; (2) the D182 world-owned NL->object grounder (CEO spine gate) to kill witness-only + make grasp-vs-wander
  deterministic; (3) welds+colour maps still HARDCODED per-object (S4/D182) — object plug-in not yet pure config.

next:
  1. [FRONTIER/breadth] a genuinely-NEW 3rd embodiment via BYO URDF+manifest. THIS needs the S4 one-generic-driver
     (CEO-gated, WIRING:53) + new MuJoCo model assets — scope it as an SDD multi-round effort, NOT a single build
     round. Until S4 lands, breadth on EXISTING embodiments (g1) is the non-gated proxy (R216 did this).
  2. [adjudicate] promote the R216/E48 g1-nav cross-embodiment provisional -> confirmed next round (boundary+red-team),
     OR refute. Also the R211 yellow / other pendings per §1b.
  3. [FRONTIER/robustness] land the D182 world-owned NL->object grounder (CEO spine gate) so grasp-vs-wander stops
     being model-strategy/placement-dependent — OR a more reliable brain (deepseek-chat, E39) for out-of-FOV fetch.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder fixes witness-only fidelity AND
    makes grasp-vs-wander deterministic (E46). META: `_PREDICATE_ORACLES` hardcoded; object plug-in not pure config
    yet (per-object weld tuple + colour maps) -> S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder ·
    BILLING (external: VLM-judge + BYO-N>=4) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair — audited clean. No new crossings R213-R216.
last_review: R210
