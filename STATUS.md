# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R228 (E51) BUILD — ADJUDICATED the R227 scene-clutter provisional: green fetch REPRODUCED across the R227→R228 boundary → E51 CONFIRMED (N=3).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R228 (E51, BUILD). Executed STATUS next#1 (§1b adjudication): re-ran ONE bare-REPL NL green
  fetch 把绿色的瓶子拿过来 (deepseek-v4-flash, MODE=fetch) under VECTOR_SCENE_CLUTTER=1 in a FRESH sim across
  the round boundary — the exact reproducibility gate R219 g1.perception FAILED. RESULT: GROUNDED
  verified=True 1/1 on holding_object('pickable_bottle_green') (moat GT). In-process (launch_explore_seen=
  False), NL-started (marker `sim start go2 ok 5.1s` = real SimStartTool, not a chat claim); eyes frame
  shows the cluttered scene rendered (orange/green/blue/red/purple distractor boxes) + arm in a grasp/lift
  pose. Same-hue weldless green decoy → a mis-ground yields False → True=discrimination, unfakeable. Oracle
  byte-unchanged (Inv.1). → fetch.nl-scene-clutter PROMOTED provisional→CONFIRMED N=3 (R227 2/2 + R228 1/1);
  BOARD flipped; supersedes row banked. Sim torn down (pgrep-clean, no orphan); check.sh green.

frontier: Plug-and-play breadth CONFIRMED across model (E23), embodiment (nav E49 + perception E50 N=3)
  AND scene-clutter (E51 N=3). That is a FLOOR. Un-crossed bars: (1) a genuinely-NEW WORLD — distinct room
  template (different geometry/layout), NOT the frozen tabletop + extra_geoms. The seam ALREADY EXISTS:
  build_room_scene(room_template_path=...) is parameterized (mujoco_go2.py:427); R229 needs an alternate
  room XML + an env selector (mirror VECTOR_SCENE_CLUTTER) + a bare-face re-verify. (2) a genuinely-NEW 3rd
  embodiment (BYO URDF+manifest, S4-gated); (3) D182 world-owned NL→object grounder (spine gate).

next:
  1. [FRONTIER/breadth, mostly NON-gated] a genuinely-NEW WORLD: author a distinct minimal room template
     (different enclosure/geometry — e.g. a compact warehouse box, NOT the 722-line house), keep the tuned
     pick-table + pickables + spawn(10,3) so grasp/perception stay reachable, wire via VECTOR_ROOM_TEMPLATE
     env → build_room_scene's room_template_path (config seam, mirror CLUTTER; confirm 0 driver edits). Unit-
     test it compiles + has the 5 pickables as a WIP floor; then REAL-VERIFY a confirmed bar (green fetch) on
     the bare face. Deeper than E51 (which reused the same room). Multi-round like R226→R227 (build then verify).
  2. [FRONTIER/breadth, GATED] a genuinely-NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-
     driver (WIRING:53) + new MuJoCo assets; scope as multi-round SDD.
  3. [SPINE, GATED] D182 world-owned NL→object grounder — kills witness-only fidelity + makes ordinal/
     relational NL robust; spine-semantics CEO gate.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R228.
last_review: R210
