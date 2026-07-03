# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R250 (E57) REVIEW — skeptic pass GREEN + audits clean:
  Skeptic re-ran the ladder-BASE HOUSE green fetch on the REAL bare face (deepseek-v4-flash +
  local ollama): GROUNDED 1/1, holding_object(green) actor=CAUSED, launch_explore_seen=False
  (in-process, not a flag path), eyes: green aloft in gripper + blue/purple/red REMAIN on the
  table = real discrimination. No regression R240->R250. R249 describe provisional ADJUDICATED
  -> confirmed (reachability-only, no moat). Gate/token audit R241-R249 CLEAN (no GATE-APPROVED
  crossings). LESSONS consolidated 260->258 (dropped visual_query hazard subsumed by the
  resolved-alias line; folded the courtyard R241-R246 saga to its distillate). WIRING anchors
  R240 (<25 rounds -> prose re-check not due). check.sh green; provisional queue clear.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R250 (E57, REVIEW, non-gated). Skeptic GROUNDED the ladder base; 1 provisional
  adjudicated; audits clean; LESSONS folded; ambition-critic plateau finding recorded.
frontier: 3 distinct worlds ground go2 FETCH (house/warehouse/courtyard; courtyard green/blue/
  red/purple all N=2, zero-shot). PLATEAU (ambition critic R250): E56/courtyard ran 9 rounds
  (R241-R249); R247-R249 added NO new confirmed capability (PLACE refuted, describe moat-less).
  Non-gated frontier is now DEBUG-polish. Genuinely-new breadth is GATED: 3rd embodiment (BYO
  URDF, S4), D182 world-owned NL->object grounder (removes witness-only fidelity).
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>) else
  eyes_*.png collide. Run harness with `.venv/bin/python`; Bash tool caps at 2min so run sims in
  BACKGROUND (nohup + inner timeout), monitor via the log. Sim gate = pgrep 'mujoco|vcli' (host)
  + free/GPU headroom, ONE sim; tear down via scripts/sim-teardown. navigate(10.8,3.0) UNREACHABLE
  in every world (inside inflated pick_table) — do NOT re-diagnose as a world bug. LEDGER SCHEMA:
  confirmed acceptance rows need redteam starting 'survived' + <=280 chars + row <1KB; experiments
  key is `e` (E<n>) + result <=280 + redteam + do_not_retry_unless (check.sh enforces).
next:
  1. [DEBUG, NON-gated] courtyard PLACE grasp flakiness (R247): grasp completes for FETCH but
     flaked for PLACE same world/scene — isolate (settle-time? held-arm pose? perception framing?).
  2. [DEBUG, NON-gated] YELLOW(y=3.11) HOUSE FOV (E45/E46, Case 14): raise head tilt / widen standoff.
  3. [BUILD, NON-gated, LOW] make describe-intent LLM-exclusive on go2 (fold generic DescribeSkill
     into the go2 DescribeSceneSkill, or drop one from the go2 vocab) so [LOOK] can't co-fire.
  4. [SPINE, GATED] D182 world-owned NL->object grounder — removes witness-only fidelity; CEO gate.
  5. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL->object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
