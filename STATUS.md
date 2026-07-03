# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R249 (E56) BUILD/VERIFY — RESOLVED the look<->describe alias collision (R248 gap):
  removed the colliding `describe`/`what do you see` aliases from the go2 LookSkill (intent split — look/看
  = survey-and-move, describe/看到什么 = static scene description). Deterministic alias_map now routes
  describe→generic DescribeSkill (RED→GREEN test_describe_look_alias_routing, 4 cases). Bare-face courtyard
  describe EXERCISED the R248 path: describe_ok=True path_entered=True (R248 was False) attr_error=False
  vlm_ran=True — raw log shows BOTH `[DESCRIBE]` (DescribeSkill fired) + `building Go2VLMPerception describe
  seam` (R248 seam). Eyes: go2+piper courtyard, 5 pickables. CAVEAT: an alias edit does NOT make LLM
  tool-choice exclusive ([LOOK] still fired same turn); describe has no moat → reachability/no-crash win.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R249 (E56, BUILD/VERIFY, non-gated). Alias-collision RESOLVED + R248 describe fix now
  face-exercised. Ledger: describe.nl-go2-courtyard RAN 1/1 provisional (path_entered=True); E56 verify
  provisional. Isaac sibling confirmed NOT an Inv-5 blocker (E54/R242) — ran clean alongside it.
frontier: 3 distinct worlds ground go2 FETCH (house/warehouse/courtyard) — courtyard FETCH breadth CLOSED
  (green/blue/red/purple N=2, zero-shot). PLACE-leg does NOT transfer cleanly (flaky at grasp + brain-nav,
  R247). Deeper bars: verify WITNESS-ONLY (D182 world-owned NL→object grounder); genuinely-new = 3rd
  embodiment (S4-gated, BYO URDF+manifest). Cheap: YELLOW HOUSE-FOV (Case 14).
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>) else eyes_*.png
  collide. Run harness with `.venv/bin/python`; Bash tool caps at 2min so run sims in BACKGROUND (nohup +
  inner `timeout`), monitor via the log. Isaac sibling (Docker /isaac-sim) is NOT an Inv-5 blocker (E54):
  gate = pgrep 'mujoco|vcli' (host) + free/GPU headroom, ONE sim. describe MODE grounds path_entered from
  the VERBOSE log (VECTOR_ACCEPT_VERBOSE=1); alias router now deterministic but LLM may still call look too.
  navigate(10.8,3.0) UNREACHABLE in every world (inside inflated pick_table) — do NOT re-diagnose as world.
next:
  1. [DEBUG, NON-gated] courtyard PLACE grasp flakiness (R247): grasp completes for FETCH but flaked for
     PLACE same world/scene — isolate (settle-time? held-arm pose? perception under place framing?).
  2. [DEBUG, NON-gated] YELLOW(y=3.11) HOUSE FOV (E45/E46, Case 14): raise head tilt / widen standoff.
  3. [BUILD, NON-gated, LOW] make describe-intent LLM-exclusive on go2 (fold generic DescribeSkill into the
     go2 DescribeSceneSkill, or drop one from the go2 vocab) so [LOOK] can't co-fire — only if it blocks work.
  4. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  5. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R240): gate/token audit R231..R239 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R240
