# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R246 (E56) BUILD/VERIFY — courtyard PURPLE PROMOTED confirmed N=2; first
  courtyard PLACE-leg RAN. Two bare-face sims (deepseek-v4-flash + local-ollama gemma4:e4b, in-process,
  launch_explore_seen=False): (1) PURPLE re-run across R245→R246 boundary GROUNDED
  holding_object(pickable_box_purple)=True actor=CAUSED (1/1) → confirmed N=2 (eyes: purple aloft,
  4 remain=colour+geometry discrimination). (2) PLACE-leg 把绿色的瓶子放到架子上 RAN verified=False (2/3):
  grasp + place resting_on_receptacle()=True (eyes: green bottle IN place_bin, physical place
  SUCCEEDED) but navigate at_position(10.8,3.0,tol=1.0) UNGROUNDED drags composite False.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R246 (E56, BUILD/VERIFY, non-gated). KEY FINDING: a new-world FETCH transferring
  zero-shot does NOT imply its PLACE-leg composite verdict transfers — grasp+place physically
  succeed (eyes-confirmed) but the multi-step nav sub-goal at_position(10.8,3.0) ungrounds; SAME
  coords ground on HOUSE with byte-identical furniture. Courtyard FETCH colour+geometry breadth
  CLOSED: green/blue/red/purple all confirmed N=2, zero-shot, no perception fix.
frontier: 3 distinct worlds ground go2 FETCH (house, warehouse, courtyard). Courtyard FETCH breadth
  CLOSED (green/blue/red/purple N=2). NEW bar: PLACE-leg transfer to the 3rd world (RAN, nav-verify
  snag — debug). Deeper: verify WITNESS-ONLY (D182); genuinely-new = 3rd embodiment (S4-gated, BYO
  URDF+manifest) + world-owned NL→object grounder. Cheap: fix courtyard place-nav; YELLOW HOUSE-FOV (Case 14).
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>) —
  eyes_*.png collides in a shared R#/ dir. Run harness with `.venv/bin/python` (bare `python` absent).
  ledger free-text fields hard-cap at 280 chars (schema); trim redteam/result/note BEFORE append.
  Do NOT re-own a run SIM-BLOCKED on a sibling ISAAC sim — different engine, not the Inv-5 gate
  (E54/LESSONS:30); gate = pgrep 'mujoco|vcli' + free/GPU headroom, ONE MuJoCo/vcli sim.
next:
  1. [DEBUG, NON-gated] Courtyard PLACE-leg nav snag (R246): grasp+place succeed but navigate
     at_position(10.8,3.0,tol=1.0) ungrounds → composite RAN/False. Hypothesis-Loop: why does the
     SAME target ground on HOUSE but not courtyard (byte-identical furniture)? Then re-verify place N≥2.
     Adjudicate the R246 place.nl-new-world-courtyard provisional (confirm RAN or resolve to GROUNDED).
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
