# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R236 (E54) BUILD/DEBUG — ROOT-CAUSED the warehouse green-fetch
  transfer gap ONE LAYER DEEPER than R234. Adopted R234's bg e2e (far-recovery fix f437f4e
  CONFIRMED engaging: localizes+standoffs+faces), then a fresh cap run + a NEW mask-gate
  breakdown diagnostic isolated the residual: front_object SALIENCY FLOOD.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R236 (E54, BUILD+DEBUG, non-gated). At the CORRECT 0.9m standoff facing the real
  bottle (attempt-1 localized (10.86,3.00) right), front_object_mask STILL = 0px. New breakdown
  (`front_object.mask_gate_breakdown`, logged at the 0px site): n_salient~99k = ~32% of frame
  passes sat>=140 (warehouse orange racking / yellow stripes / steel all vivid) → the green
  bottle's real pixels (n_color_hue<=2917) FUSE into bg blobs whose MEDIAN hue!=green →
  colour-blob resolver None. HOUSE works only because its bg is MUTED; the resolver's "vivid
  object on muted scene" assumption is FALSE industrial. Shipped mask_gate_breakdown()+5 TDD
  (17/17 front_object, 51/51 incl perception_grasp); wired at mask_px=0. E54 debug row confirmed.

frontier: Make the HOUSE colour fetch TRANSFER to go2_warehouse. Root cause now KNOWN
  (saliency flood, not nav/localizer/dead-band). Bar = e2e GROUNDED green fetch on the bare face.

watch: R234/R235 bg verify DONE+adopted; inflight cleared; sim down. 28 acceptance provisionals (check.sh green).

next:
  1. [BUILD/DEBUG, NON-gated] FIX saliency flood: in front_object_mask, for a COLOUR query gate
     the colour HUE at PIXEL level BEFORE `_open`/components (build the mask from green-hue px
     first, THEN pick nearest/central green blob) so warehouse bg never competes. TDD: a
     "vivid-orange-bg + small green blob" frame must return the green blob (today None). e2e
     re-verify on the bare face AND re-run the confirmed HOUSE red/green/blue/yellow/purple
     fetches to prove NO regression (shared path). GROUNDED N>=2 → promote fetch.nl-new-world-warehouse.
  2. [DEBUG, NON-gated] object_localizer unreliable in-warehouse (3/4 attempts floor/far phantoms;
     only attempt-1 right). After #1, harden the seed to always use the clean-forward localize.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
