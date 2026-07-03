# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R237 (E54) BUILD+VERIFY — FIXED the warehouse green-fetch saliency
  flood (R236 root cause). front_object_mask now gates the target HUE at PIXEL level BEFORE
  _open/components for a colour query. Warehouse green-fetch GROUNDED N=2 + HOUSE no-regression
  GROUNDED, all on the bare face, eyes-confirmed (dog holds green bottle in the warehouse).
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R237 (E54, BUILD+VERIFY, non-gated). Fix (front_object.py): for color!=None, build the
  salient mask from target-hue PIXELS before morphology, so the vivid warehouse bg can't 8-connect
  the green bottle into an off-hue blob (the R236 flood → mask_px=0 → None). TDD: new
  test_color_green_survives_saliency_flood RED→GREEN; perception dir + grasp routing/recovery 121 pass.
  e2e on the bare warehouse face: N=2 GROUNDED (perceived:True detection_label pickable_bottle_green;
  holding_object(pickable_bottle_green)->PASS actor=CAUSED), + HOUSE green-fetch GROUNDED (shared path,
  no regression). 3 provisional acceptance rows + E54 verify(confirmed) banked. Was refuted R229/R231/R234/R236.

frontier: Warehouse green-fetch transfer CLOSED (N=2). Next floor: robustness N>=3 + the OTHER colours
  (red/blue/yellow/purple) must transfer to warehouse too, then a genuinely-NEW 3rd embodiment (S4-gated).

watch: inflight cleared; sim torn down. Sibling ISAAC sim (warehouse_nav.py, ~7G) was live in another
  loop all round — did NOT kill (NEVER-KILL-INFRA); RAM stayed ample (40G avail). 30 acceptance provisionals.

next:
  1. [ADJUDICATE, §1c] Promote fetch.nl-new-world-warehouse to confirmed: red-team the R237 GROUNDED
     N=2 (survived a round boundary), append confirmed acceptance row, and add the DECISIONS/LESSONS
     promotion. THEN robustness N>=3 fresh sims to certify determinism.
  2. [BUILD/VERIFY, NON-gated] Transfer the OTHER colours to warehouse: run red/blue/yellow/purple
     fetches on VECTOR_ROOM_TEMPLATE=warehouse — the pixel-hue gate should carry them; verify N>=1 each,
     any miss is a per-colour hue-band vs warehouse-render check (breakdown n_hue_anywhere).
  3. [DEBUG, NON-gated] object_localizer in-warehouse still noisy (R236: 3/4 attempts floor/far phantoms;
     seat-approach recovered it here). Harden the seed to prefer the clean-forward localize.
  4. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
