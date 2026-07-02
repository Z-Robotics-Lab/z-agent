# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R211 (E45) BUILD — novel 4th object (yellow bottle) GROUNDED on the real bare face
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R211 (E45, BUILD). BREADTH PIVOT delivered its first OBJECT-DIVERSITY proof (R200 critic). Added a
  YELLOW bottle — the FIRST non-RGB pickable — as CONFIG+driver+skill, ZERO kernel edits, across 5 plug-in sites
  (go2_room.xml body + MuJoCoGo2 welds tuple + front_object HSV band + grounding_dino vocab + perception_grasp
  _COLOR_TO_SCENE). Bare face (deepseek-v4-flash): `把黄色的瓶子拿过来` -> perception_grasp(黄色的瓶子) ->
  holding_object('pickable_bottle_yellow')==True actor=CAUSED -> GROUNDED 1/1. eyes(self-read): yellow held
  aloft, red+green+blue all remain (isolated among 4). Unit test_novel_yellow_object.py 6/6; 68 perception/skill
  regression green. Gotchas banked (E45): scene_room_piper.xml is a GENERATED output (edit SOURCE go2_room.xml);
  off-frame y=2.56 first mis-navved (fixed to in-FOV y=3.11); an offline synthetic-depth probe MISpredicted a
  fusion the real depth-cam didn't have -> offline perception probe is a debugging lens, never acceptance.

frontier: Object diversity now has ONE proof point (yellow, N=1). Still the SAME scene/robot and witness-only (D182).
  The weld tuple + colour maps are HARDCODED per-object (not pure config) — the 5-site plug-in surface is the
  S4/D182 gap made concrete. Real next bar: a 2nd WORLD/embodiment (BYO URDF+manifest, one generic driver) OR the
  D182 world-owned NL->object grounder. More single-scene colour variants = a LOCAL HILL.

next:
  1. [§1b] adjudicate the R211/E45 fetch.nl-novel-object-yellow provisional -> confirmed (re-run on the bare face
     across the round boundary + red-team) OR refuted. THEN raise: an N>=2 novel-object run, or a novel CATEGORY
     (non-cylinder, e.g. a box '盒子') to test perception/grasp on new geometry, not just a new colour.
  2. [FRONTIER/breadth] a 2nd world/embodiment (BYO robot URDF+manifest, one generic driver) OR land the D182
     world-owned NL->object grounder (CEO spine gate) — the real plug-and-play proof; > more single-scene NL.
  3. [quantity, low-pri] deterministic quantity still OPEN (E41 guardrail REFUTED): stronger runner-side
     goal-authenticity guardrail OR a brain that reliably self-splits 两个.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder would fix witness-only fidelity
    AND isolate dense/clutter objects the classical HSV resolver strains on. META: plug-and-play verify-predicates
    (`_PREDICATE_ORACLES` hardcoded). Object plug-in is ALSO not pure config yet (per-object weld tuple + colour maps) -> S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6 ladder ·
    BILLING (external: VLM-judge + BYO-N>=4) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair — audited clean. No new crossings R211.
last_review: R210
