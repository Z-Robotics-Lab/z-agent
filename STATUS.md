# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R229 (E52) BUILD — authored a genuinely-NEW WORLD (go2_warehouse.xml) via VECTOR_ROOM_TEMPLATE; SPLIT verdict: BUILD floor met, green-fetch TRANSFER refuted 0/2 on the bare face.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R229 (E52, BUILD). Executed STATUS next#1: authored go2_warehouse.xml — a compact
  industrial box (steel perimeter, concrete floor, orange racking), geometrically distinct from the
  20×14m house, but pick furniture (pick_table + 5 pickables + place_bin) copied byte-for-byte at SAME
  coords. Wired via VECTOR_ROOM_TEMPLATE → build_room_scene(room_template_path=), fail-loud on unknown
  key. 0 kernel/driver edits (Inv.3). Unit test_room_template.py 9/9; default house BYTE-IDENTICAL.
  SPLIT VERDICT (honest): BUILD GROUNDED — warehouse compiles, config verifiably takes effect (built
  scene_room_piper.xml carries ww_south/rack_up_a/mat_concrete; MjModel green [10.88,3,.32], dog [10,3]).
  TRANSFER REFUTED — green fetch RAN 0/2 bare face (v4-flash): run1 WANDERED (walk fwd 2.0×N → pick
  'Cannot locate' → verify fail); run2 perception_grasp×11 never completed. Furniture identical + config
  live ⇒ NOT moved-geometry. Banked 2 acceptance + E52 experiments rows. Sim torn down; check.sh green.

frontier: Plug-and-play breadth CONFIRMED across model (E23), embodiment (nav E49 + perception E50 N=3)
  AND scene-clutter (E51 N=3). NEW finding (E52): a new-world BUILD plugs in as pure config (0 kernel
  edits) but grasp/perception does NOT TRANSFER zero-shot — the build is a FLOOR, transfer is the bar.
  Un-crossed: (1) [E52 debug] make green fetch GROUND in go2_warehouse — root-cause perception_grasp's
  non-completion (detector/approach-lidar/camera). (2) NEW 3rd embodiment (S4-gated). (3) D182 grounder.

next:
  1. [DEBUG/breadth, NON-gated] Hypothesis-Loop why green fetch does NOT complete in go2_warehouse
     (E52 refuted 0/2). OBSERVE with a repeatable probe: (a) does the head-cam detector still SEE green
     in the warehouse (run detect/perception in-process, dump the frame)? (b) does perception_grasp's
     APPROACH stop short / mis-read the new lidar walls (ww_* collidable at x=16.5)? (c) camera framing
     shift from the concrete floor / racks? Falsify one at a time → DEBUG.md. Fix minimally (world-config
     only, e.g. push walls out / adjust a light) then re-verify green fetch N≥2. If it fails in the HOUSE
     too under the same brain, it's brain-flake not world (control run). Deeper than E51 (new enclosure).
  2. [FRONTIER/breadth, GATED] a NEW 3rd embodiment via BYO URDF+manifest — needs S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; scope as multi-round SDD.
  3. [SPINE, GATED] D182 world-owned NL→object grounder — spine-semantics CEO gate.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4; dashscope key Arrearage-blocked R217) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair audited clean. No new crossings R213-R229.
last_review: R210
