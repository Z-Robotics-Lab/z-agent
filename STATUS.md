# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R238 (E54) VERIFY+BUILD — PROMOTED warehouse green-fetch to CONFIRMED
  (N=3) across the R237→R238 boundary, AND a SECOND colour (blue) transferred to the warehouse
  (provisional N=1). The R237 pixel-hue gate is colour-AGNOSTIC, not green-specific.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R238 (E54, VERIFY+BUILD, non-gated). §1b: re-ran warehouse green-fetch FRESH on the bare
  face (VECTOR_ROOM_TEMPLATE=warehouse, deepseek-v4-flash, local Ollama gemma4:e4b eyes) — GROUNDED 1/1
  (holding_object(pickable_bottle_green) actor=CAUSED; eyes: dog holds green aloft, warehouse floor-stripe),
  reproducing R237 across the boundary → PROMOTED fetch.nl-new-world-warehouse to confirmed (cum N=3).
  next#2: warehouse BLUE fetch GROUNDED N=1 (holding_object(blue) actor=CAUSED; eyes: dog holds blue,
  red/green/yellow/purple untouched=discrimination) → the fix generalizes past green. Both in-process
  (launch_explore_seen=False). Confirmed acceptance row + blue provisional + E54 verify(confirmed) banked.

frontier: New-world TRANSFER CLOSED for green (confirmed N=3) + generalizes to blue (N=1). Next floor:
  blue N>=2 to confirm + the REMAINING colours (red/yellow/purple) must transfer to warehouse (red is the
  hardest — its hue neighbours the orange racking), then robustness, then a genuinely-NEW 3rd embodiment (S4).

watch: inflight cleared; both sims torn down (37G avail). Multi-run evidence collision hit+recovered
  (blue overwrote green's eyes_fetch.png; green verdict PNG survived; per-run copies made) → LESSONS recipe.
  ⚠ ulimit -v 24G spuriously EAGAIN-kills this CUDA/torch perception run — use -v 50G (LESSONS/perf caveat).

next:
  1. [BUILD/VERIFY, NON-gated] Promote fetch.nl-new-world-warehouse-blue to confirmed: re-run blue N>=2
     fresh (boundary + red-team), then transfer the REMAINING colours red/yellow/purple to warehouse
     (VECTOR_ROOM_TEMPLATE=warehouse) — verify N>=1 each; any miss = per-colour hue-band vs warehouse-render
     check (front_object breakdown n_hue_anywhere). Set VECTOR_EVIDENCE_DIR per run (multi-run collision).
  2. [ADJUDICATE, §1b] fetch.nl-plain-colour provisional (R237 HOUSE no-regression, age 1) — a quick HOUSE
     green re-run to confirm, or supersede; it ages out at >2.
  3. [DEBUG, NON-gated] object_localizer in-warehouse still noisy (R236: 3/4 floor/far phantoms); harden the
     seed to prefer the clean-forward localize.
  4. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
