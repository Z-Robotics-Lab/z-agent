# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R212 (E46+E47) BUILD — novel-object grounding is BRAIN-FRAGILE at N=1 (yellow refuted, purple box grounded)
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R212 (E46+E47, BUILD). Two opposite results, SAME brain (deepseek-v4-flash), SAME round — the honest headline:
  novel-object grounding is BRAIN-STRATEGY-FRAGILE at N=1, NOT the geometry/plug-in.
  §1b: the R211/E45 yellow GROUNDED 1/1 did NOT reproduce (E46 REFUTED, supersedes d823c8d): re-run RAN 0/2 —
  perception_grasp(yellow) reported not-visible, brain then WANDERED navigate(5,5)/(1,0), lost in bathroom, never
  grasped. Box edit landed after scene-gen -> NOT a confound; it was the same 4-object scene as R211.
  RAISE (E47): a NOVEL non-cylinder — PURPLE BOX (type=box, 5th pickable, FIRST non-cylinder geometry) — GROUNDED 1/1
  on the bare face: `把紫色的盒子拿过来` -> holding_object(pickable_box_purple) actor=CAUSED; eyes(self-read) box held
  aloft, blue/green/red remain (isolated among 5). Plug-in=5 sites (go2_room.xml box body + MuJoCoGo2 welds + HSV
  purple(140,162) + dino vocab + _COLOR_TO_SCENE), ZERO kernel edits. So the plug-in surface is CORRECT for colour
  AND geometry; the flake is the brain's grasp-vs-wander decision (E36/Case-15). Unit test_novel_purple_box.py 6/6 (box-geometry + hue-disjoint) + 26 perception regression green.

frontier: Novel-object grounding proven for COLOUR (R211) and now GEOMETRY (R212 box) — but every proof is N=1 and
  BRAIN-FRAGILE (E46: a sibling N=1 pass refutes on re-run). The plug-in surface is not the bottleneck; the brain's
  grasp-vs-wander non-determinism is. Real next bar: ROBUSTNESS (N>=2 same-brain reproduction) via either a more
  reliable brain OR the D182 world-owned grounder — NOT more single-scene N=1 object variants (a LOCAL HILL). The
  breadth pivot still owes a 2nd WORLD/embodiment (BYO URDF+manifest, one generic driver). welds+colour maps remain
  HARDCODED per-object (S4/D182).

next:
  1. [§1b] adjudicate the R212/E47 purple-box GROUNDED provisional -> confirmed (re-run on the bare face across the
     boundary + red-team) OR refuted. Given E46, EXPECT fragility: run N>=2 and record the pass-rate honestly.
  2. [FRONTIER/robustness] the N=1 fragility is the real finding — the direct move is a MORE RELIABLE BRAIN
     (deepseek-chat grounded quantity where v4-flash wandered, E39) for the novel-object fetch, OR land the D182
     world-owned NL->object grounder (CEO spine gate) so grasp-vs-wander stops being model-strategy-dependent.
  3. [FRONTIER/breadth] a 2nd world/embodiment (BYO robot URDF+manifest, one generic driver) — the real
     plug-and-play proof; > more single-scene NL/object variants.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder would fix witness-only fidelity
    AND make grasp-vs-wander deterministic (E46). META: plug-and-play verify-predicates (`_PREDICATE_ORACLES`
    hardcoded). Object plug-in is ALSO not pure config yet (per-object weld tuple + colour maps) -> S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6 ladder ·
    BILLING (external: VLM-judge + BYO-N>=4) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R210): R209 CEO-APPROVED schema-cap repair — audited clean. No new crossings R212.
last_review: R210
