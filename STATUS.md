# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R227 (E51) BUILD — REAL-VERIFIED the R226 VECTOR_SCENE_CLUTTER 2nd scene variant: green fetch GROUNDED N=2 on the bare face under clutter (provisional).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R227 (E51, BUILD). Executed STATUS next#1 (breadth, NON-gated): REAL-VERIFY the R226-built
  VECTOR_SCENE_CLUTTER 2nd scene variant. Ran a CONFIRMED bar — bare-REPL NL green fetch 把绿色的瓶子拿过来,
  deepseek-v4-flash, MODE=fetch — TWICE under VECTOR_SCENE_CLUTTER=1. RESULT: GROUNDED N=2 (both runs
  fetch_verified=True 1/1), in-process (launch_explore_seen=False), NL-started (`sim start go2 ok 4.8s` = real
  SimStartTool). Verified the config TOOK EFFECT: built scene_room_piper.xml contains all 5 clutter geoms incl.
  the same-hue off-centre green decoy (rgba 0.25/0.7/0.35 @ 11.35/3.72, contype/conaffinity=0, no freejoint →
  weldless/unpickable). True = real central green bottle grasped (holding_object moat GT); a mis-ground onto the
  decoy would yield False → discrimination, unfakeable. Reproducible within-round (NOT a lucky sample like R219
  g1.perception). Answers the R200 zero-scene-diversity critic on the SCENE axis. Sim torn down (scripts/sim-teardown),
  no orphan; check.sh green. BANKED provisional (adjudicate R228).

frontier: Plug-and-play breadth now spans model (E23), embodiment (nav E49 + perception E50 N=3) AND scene
  (E51 clutter N=2, provisional). That is a FLOOR. Still ONE room geometry / one robot per scene. Un-crossed bars:
  (1) a genuinely-NEW WORLD — distinct room geometry/layout, not just added geoms in the same tabletop room (Inv.3,
  NON-gated but needs a new room template); (2) a genuinely-NEW 3rd embodiment (BYO URDF+manifest, S4-gated);
  (3) D182 world-owned NL→object grounder (spine gate).

next:
  1. [§1b ADJUDICATE, do FIRST] Promote/refute the R227 E51 fetch.nl-scene-clutter GROUNDED N=2 provisional:
     re-run ONE green fetch under VECTOR_SCENE_CLUTTER across the R227→R228 boundary (fresh sim, oracle byte-
     unchanged). Survives → confirmed row + BOARD flip. This is the round-boundary reproducibility gate R219
     failed (never skip it: N=2 within a round is not yet confirmed).
  2. [FRONTIER/breadth, mostly NON-gated] a genuinely-NEW WORLD: a distinct room template (different geometry/
     layout, not the frozen tabletop + extra_geoms), then re-run a confirmed bar (fetch or g1.perception) on it.
     Deeper than E51 (which reused the same room). New room XML is config, but confirm it needs no driver edits.
  3. [FRONTIER/breadth, GATED] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-
     driver (WIRING:53) + new MuJoCo assets; scope as multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R227.
last_review: R210
