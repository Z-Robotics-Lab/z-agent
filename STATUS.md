# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R242 (E56) VERIFY — ADOPTED the R241 inflight and RAN the owed bare-face
  courtyard green-fetch. GROUNDED 1/1: holding_object('pickable_bottle_green') actor=CAUSED;
  eyes (self-read, 2 frames): the Go2 holds the green bottle aloft in the open-air courtyard while
  the other 4 pickables (purple box/yellow/red/blue) remain on pick_table = colour discrimination.
  The 3rd distinct world (go2_courtyard.xml, pure CONFIG) TRANSFERS the fetch bar. N=1 provisional.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R242 (E56, VERIFY, non-gated). KEY FINDING: R241's inflight sim-free precondition
  listed `isaac` and re-owed the run as SIM-BLOCKED — but per the CONFIRMED E54 lesson (LESSONS:30)
  the sibling /workspace/go2w Isaac sim is a DIFFERENT engine, does NOT trip the repo's gate
  (mujoco|vcli), and with RAM/GPU headroom (43G RAM, 9.8G GPU free) is NOT an Inv-5 blocker; R241
  (like R231-R233) over-read it. Ran clean (local-ollama perception, deepseek planner, 0x402,
  in-process); provider unchanged ⇒ a world-generalization result, not a model artifact.

frontier: courtyard fetch TRANSFERS (N=1) → 3 distinct worlds ground the green-fetch bar (house
  N=3, warehouse N=3, courtyard N=1). Deeper bars unchanged: verify WITNESS-ONLY (D182); genuinely-
  new = 3rd embodiment (S4-gated) + world-owned NL→object grounder. Cheap win: courtyard COLOUR
  breadth (blue/red/purple), hue gate is colour-agnostic (E54).

watch: do NOT re-own a run SIM-BLOCKED on a sibling ISAAC sim — different engine, not the repo's
  Inv-5 gate (E54/LESSONS:30). Gate = pgrep 'mujoco|vcli' + free/GPU headroom; ONE MuJoCo/vcli sim.

next:
  1. [PROMOTE, NON-gated] Re-run courtyard green-fetch across this boundary + red-team → promote
     fetch.nl-new-world-courtyard to confirmed N>=2 (E46 rule). Cheap: add a 2nd courtyard colour
     (blue) in the same run to widen transfer while the sim is up.
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
