# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-02 · R194 (E30) — ordinal robustness REFUTED; deterministic resolver landed (offline)
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R194 (E30) — cleared quarantine (BOARD regen). Adopted R193 inflight (E29):
  把最左边的瓶子拿过来 re-run MISSED — grasped pickable_can_red, verified=False 1/4 (eyes: Go2 drags the
  red CAN, both bottles untouched). => R192 ordinal GROUNDED 1/1 REFUTED (no reproduce). Root cause:
  the VLM bbox route honours the ordinal POSITION but DROPS the 瓶子/bottle category filter, so the
  leftmost OBJECT (a can) beats the leftmost BOTTLE. FIX (offline, unwired): deterministic
  `_parse_ordinal`+`_resolve_ordinal_target` in perception_grasp.py — parse ordinal+category, FILTER to
  category, sort by image cx, pick extreme; 12 unit + 138/138 skills green. Adjudicated R192 refuted,
  R188x2 superseded. Unit-green != acceptance — NOT sim-verified.

frontier: ordinal grounding is NOT robust (E30). RAISE: WIRE the resolver into perception_grasp's run
  flow, sim-verify 把最左边的瓶子→green N≥3, then quantity (两个/两瓶) + ambiguity (那个/它). AMBITION:
  a world-owned NL→object spatial grounder (D182 spine, CEO-gated) makes ordinal/relational NL robust.

blocked: cloud VLM/BYO credit (perception VLM + judge + BYO-N≥4) — external BILLING gate; a local
  Ollama model is the plug-and-play workaround for the perception VLM (recipe: LESSONS/.env.example).

scene (real mujoco_go2 room XML, collinear along y, rightmost=smallest y): blue(2.78)=rightmost-BOTTLE,
  green(3.00)=leftmost-BOTTLE (grasp-reliable R190), red_can(3.22)=leftmost-OBJECT (excl. by 瓶子; R193
  wrongly grasped it). world-y↔image-cx sign UNPROVEN till wired.

next:
  1. [FRONTIER] WIRE `_resolve_ordinal_target` into perception_grasp run flow: on an ordinal query,
     filter perceived detections to the category + pick the cx-extreme; verify world-y↔image-cx SIGN vs
     the sim FIRST, then sim-verify 把最左边的瓶子→green N≥3 (local-VLM route) → confirmed row.
  2. [FRONTIER] after ordinal robust: quantity (两个/两瓶) + ambiguity (那个/它 anaphora); bank each
     failure mode as a Casebook case, not just a count.
  3. [DEBT] 6 aging N=1 provisional acceptance rows (R168/174/176/177/182/184) — batch re-verify on a
     review round (check.sh doesn't block, but the confirmation debt is real).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder would fix E25/E30
    fragility. META: plug-and-play verify-predicates (`_PREDICATE_ORACLES` hardcoded).
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S4/S5/S6
    ladder · BILLING (external) · RELEASE: restructure merge to master (owner).
last_review: R190
