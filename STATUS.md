# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R247 (E56) DEBUG/VERIFY — courtyard PLACE nav snag ROOT-CAUSED, world-transfer
  hypothesis REFUTED. Deterministic geometry probe (g1_vgraph, R=0.28): navigate(10.8,3.0) sits INSIDE
  the inflated pick_table (table x∈[10.80,11.10]) → plan_path=None from every start, UNREACHABLE in
  EVERY world incl HOUSE (furniture byte-identical). R246's failing at_position was a brain-IMPROVISED
  recovery nav to the bottle pick-loc after a mobile_place first-nav flake; the physical place had already
  succeeded. R247 bare-face re-verify (courtyard place): grasp itself never completed (13× perception_grasp,
  robot pos drifted) → brain wandered → NO verdict. PLACE-leg is model-flaky (grasp+nav), not a clean transfer.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R247 (E56, DEBUG/VERIFY, non-gated). KEY FINDING: the R246 "same (10.8,3.0) grounds on HOUSE
  but not courtyard" world-transfer narrative is REFUTED — (10.8,3.0) is unreachable everywhere (inside the
  inflated pick_table). No product bug: navigate_to correctly rejects an inside-obstacle target; the bad coord
  was brain-authored. Provisional place.nl-new-world-courtyard adjudicated → refuted (not a clean transfer).
  Also found: go2 `describe`/`visual_query` dead-ends (Go2GraspPerception lacks the method) → recovery branch broken.
frontier: 3 distinct worlds ground go2 FETCH (house, warehouse, courtyard) — courtyard FETCH breadth CLOSED
  (green/blue/red/purple N=2, zero-shot). PLACE-leg does NOT transfer cleanly to the 3rd world: flaky at BOTH
  grasp-completion and brain-nav. Deeper: verify WITNESS-ONLY (D182); genuinely-new = 3rd embodiment (S4-gated,
  BYO URDF+manifest) + world-owned NL→object grounder. Cheap: fix go2 visual_query; YELLOW HOUSE-FOV (Case 14).
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>); ROUND_N alone
  reuses R#/ and collides eyes_*.png. Run harness with `.venv/bin/python`. ledger free-text hard-caps at 280
  chars (schema) — trim redteam/result/note BEFORE append. navigate(10.8,3.0) is UNREACHABLE in every world
  (inside inflated pick_table) — do NOT re-diagnose as a world difference. Do NOT re-own an Isaac-sibling
  SIM-BLOCK (E54): gate = pgrep 'mujoco|vcli' + free/GPU headroom, ONE MuJoCo/vcli sim.
next:
  1. [BUILD, NON-gated] Wire go2 `visual_query`/`caption` → the vlm_go2 describe_scene seam (R247 gap:
     Go2GraspPerception implements detect but not visual_query → describe raises AttributeError, so the
     brain's describe-based recovery dead-ends). Then re-verify courtyard PLACE N≥1 on the bare face.
  2. [DEBUG, NON-gated] courtyard PLACE grasp flakiness (R247): grasp completes for FETCH but flaked for
     PLACE same world/scene — isolate (settle-time? held-arm pose? perception under place framing?).
  3. [DEBUG, NON-gated] YELLOW(y=3.11) HOUSE FOV (E45/E46, Case 14): raise head tilt / widen standoff.
  4. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  5. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R240): gate/token audit R231..R239 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R240
