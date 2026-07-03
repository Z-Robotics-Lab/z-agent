# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R245 (E56) BUILD/VERIFY — 3rd-WORLD COURTYARD colour+geometry breadth
  CLOSED to N=2 on all three colours. Two bare-face fetch sims (deepseek-v4-flash planner,
  local-ollama gemma4:e4b perception, in-process, launch_explore_seen=False): (1) courtyard RED
  re-run across the R244→R245 boundary GROUNDED → PROMOTED confirmed N=2
  (holding_object(pickable_can_red) verified=True actor=CAUSED); (2) courtyard PURPLE box
  (novel non-cylinder geometry) GROUNDED N=1 provisional (holding_object(pickable_box_purple)).
  Eyes (self-read, 2 frames): Go2 holds red can, then purple box, aloft in the sandstone
  courtyard; the other 4 pickables remain on pick_table = colour+geometry discrimination. ZERO
  perception fix — sandstone bg (~25°) far from every target hue.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R245 (E56, BUILD/VERIFY, non-gated). KEY FINDING: a config-only world whose
  background hue is FAR from the target transfers zero-shot for both COLOUR and GEOMETRY — the
  purple BOX (non-cylinder) grounded on the first try alongside the hue-adjacent red can, no
  perception fix. 3rd-world colour breadth is now green/blue/red confirmed N=2, purple N=1.
frontier: 3 distinct worlds ground go2 fetch (house, warehouse, courtyard). Courtyard breadth
  green/blue/red N=2, purple N=1 (colour+geometry). Deeper bars unchanged: verify WITNESS-ONLY
  (D182); genuinely-new = 3rd embodiment (S4-gated, BYO URDF+manifest) + world-owned NL→object
  grounder. Cheap wins left: promote courtyard-purple to N≥2; the YELLOW HOUSE-FOV debug (Case 14).
watch: per-colour evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<colour>) —
  eyes_fetch.png collides in a shared R#/ dir. Run the harness with `.venv/bin/python` (bare
  `python` is absent). Do NOT re-own a run SIM-BLOCKED on a sibling ISAAC sim — different engine,
  not the Inv-5 gate (E54/LESSONS:30); gate = pgrep 'mujoco|vcli' + free/GPU headroom, ONE
  MuJoCo/vcli sim. Purple utterance is 把紫色的盒子拿过来 (box, not bottle).
next:
  1. [PROMOTE, NON-gated] Re-run courtyard PURPLE across this boundary + red-team → promote
     fetch.nl-new-world-courtyard-purple to confirmed N>=2 (E46 rule). Cheap: co-run a novel
     probe (a hue the courtyard has NOT yet exercised, or a place-leg) in the same sim window.
  2. [DEBUG, NON-gated] YELLOW(y=3.11) HOUSE FOV (E45/E46, Case 14): raise head tilt / widen standoff
     so the short/high pickable enters the near-field vertical frustum, then transfer yellow.
  3. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  4. [DEBUG, NON-gated] object_localizer in-warehouse still noisy (R236 floor/far phantoms); harden seed.
  5. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R240): gate/token audit R231..R239 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R240
