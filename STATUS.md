# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R215 (E47 CONFIRMED) VERIFY — purple-box novel-object grounding REPRODUCES N=3
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R215 (E47, VERIFY). Adjudicated the R212/E47 purple-box provisional (the preflight blocker) on the real
  bare face: GROUNDED 3/3 fresh sims, SAME brain (deepseek-v4-flash), `把紫色的盒子拿过来` ->
  holding_object('pickable_box_purple') all 3; eyes(self-read) all 3: purple box held aloft by the Piper gripper,
  blue/green/red cylinders remain on the pedestal (isolated among 5); launch_explore_seen=False x3 (in-process, D163).
  Moat oracle reads deterministic MjData (weld + z>=lift + EE-radius, target-aware) — actor cannot author it.
  REFINES R212's "brain-fragile at N=1": the sibling yellow (E46) refuted 0/2 under the SAME harness because of its
  out-of-easy-FOV placement (y=3.11 -> perception not-visible -> brain wandered), NOT geometry; an IN-FOV
  grasp-reachable novel object (box y=2.89) grounds ROBUSTLY. Prior R213/R214 fetch turns died mid-turn (round
  deadline, no verdict) -> this round ran all 3 in the foreground. Confirmed acceptance row supersedes the provisional.

frontier: Novel-object grounding proven for COLOUR (R211) and GEOMETRY (R212/R215 box), now ROBUST N=3 for an in-FOV
  object — the plug-in surface (5-site config+driver+skill, 0 kernel edits) is NOT the bottleneck; placement/FOV is
  (yellow refuted only because out-of-FOV). Real next bars, in order: (1) a 2nd WORLD/embodiment (BYO URDF+manifest,
  one generic driver) — the true plug-and-play breadth proof, > more single-scene object variants; (2) the D182
  world-owned NL->object grounder (CEO spine gate) to make grasp-vs-wander deterministic; (3) welds+colour maps still
  HARDCODED per-object (S4/D182) — object plug-in is not yet pure config.

next:
  1. [FRONTIER/breadth] a 2nd world/embodiment (BYO robot URDF+manifest, one generic driver) — the real
     plug-and-play proof. THIS is the frontier now that colour+geometry novel-object grounding is confirmed robust;
     > more single-scene NL/object variants (a LOCAL HILL, per the frontier note).
  2. [FRONTIER/robustness] land the D182 world-owned NL->object grounder (CEO spine gate) so grasp-vs-wander stops
     being model-strategy/placement-dependent — OR a more reliable brain (deepseek-chat, E39) for out-of-FOV fetch.
  3. [breadth, cheap] if a novel-object variant IS run, place it IN the front FOV band (y~2.8-2.9) per R215 lesson;
     do NOT re-run yellow at y=3.11 without a world-owned grounder or nav-then-grasp fix (E46 refuted, do-not-retry).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder would fix witness-only fidelity
    AND make grasp-vs-wander deterministic (E46). META: plug-and-play verify-predicates (`_PREDICATE_ORACLES`
    hardcoded). Object plug-in is ALSO not pure config yet (per-object weld tuple + colour maps) -> S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6 ladder ·
    BILLING (external: VLM-judge + BYO-N>=4) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair — audited clean. No new crossings R213-R215.
last_review: R210
