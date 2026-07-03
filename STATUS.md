# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R248 (E56) BUILD/VERIFY — wired Go2GraspPerception.caption/visual_query to the
  vlm_go2 describe_scene seam (R247 gap: it had detect() only → the generic DescribeSkill dead-ended on
  AttributeError('visual_query')). 3 unit tests GREEN. Bare-face courtyard describe run: NO dead-end
  (attr_error=False, vlm_ran=True, eyes: courtyard+5 pickables) — but the brain routed the describe NL to
  the alias-colliding go2 LookSkill (context.services['vlm']), NOT the generic DescribeSkill
  (context.perception) my fix patches, so the EXACT fixed path was not exercised on the face.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R248 (E56, BUILD/VERIFY, non-gated). Fix + a describe MODE added to repl_accept (post-hoc
  grounds via verbose-log markers). Ledger: describe.nl-go2-courtyard RAN 1/1 provisional; E56 build
  provisional. Latent-crash removed, unit-proven + no-regression on the face. KEY: go2 `describe`/`看到什么`
  NL is ALIAS-COLLIDED between the generic DescribeSkill (context.perception=Go2GraspPerception) and the
  go2 LookSkill (context.services['vlm']=Go2VLMPerception) — which fires is model/registration-dependent;
  the fix makes BOTH branches safe.
frontier: 3 distinct worlds ground go2 FETCH (house/warehouse/courtyard) — courtyard FETCH breadth CLOSED
  (green/blue/red/purple N=2, zero-shot). PLACE-leg does NOT transfer cleanly (flaky at grasp + brain-nav,
  R247). Deeper bars: verify WITNESS-ONLY (D182 world-owned NL→object grounder); genuinely-new = 3rd
  embodiment (S4-gated, BYO URDF+manifest). Cheap: YELLOW HOUSE-FOV (Case 14); alias-collision resolve.
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>) else eyes_*.png
  collide. Run harness with `.venv/bin/python`. ledger free-text hard-caps at 280 chars — trim BEFORE
  append. describe MODE grounds post-hoc from the VERBOSE log (needs VECTOR_ACCEPT_VERBOSE=1); the brain
  PREFERS the go2 LookSkill for describe NL, so the generic DescribeSkill (the fixed path) is not reliably
  reachable on the face without resolving the look<->describe alias collision. navigate(10.8,3.0) is
  UNREACHABLE in every world (inside inflated pick_table) — do NOT re-diagnose as a world difference. Do
  NOT re-own an Isaac-sibling SIM-BLOCK (E54): gate = pgrep 'mujoco|vcli' + free/GPU headroom, ONE sim.
next:
  1. [DEBUG, NON-gated] courtyard PLACE grasp flakiness (R247): grasp completes for FETCH but flaked for
     PLACE same world/scene — isolate (settle-time? held-arm pose? perception under place framing?).
  2. [BUILD, NON-gated] resolve the look<->describe alias collision (dedupe aliases, or fold the generic
     DescribeSkill into the go2 LookSkill on go2) so the R248 fix is deterministically exercised on the face.
  3. [DEBUG, NON-gated] YELLOW(y=3.11) HOUSE FOV (E45/E46, Case 14): raise head tilt / widen standoff.
  4. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  5. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R240): gate/token audit R231..R239 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R240
