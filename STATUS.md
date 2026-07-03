# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R232 (E54) DEBUG — Hypothesis-Loop the warehouse green-fetch transfer
  gap. SIM-BLOCKED (sibling Isaac warehouse sim live, Inv-5 ONE-sim) so no MuJoCo launch: did the
  static OBSERVE+HYPOTHESIZE pass and shipped the instrumentation that makes next round's ONE run decisive.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R232 (E54, DEBUG, non-gated). Executed STATUS next#2 (sim-free half).
  OBSERVE (var/evidence/R231 clean-route): two-phase fail — Phase A perceive+approach+grasp ran 26.7s → holding_object
  False (perceived-then-missed); Phase B scan 6 headings `closest seen inf` (ZERO detections anywhere). RULED OUT:
  spawn/pose (green 10.88,3.0 byte-identical; dog 10,3 set programmatically; warehouse missing <keyframe> is flat-branch-
  only, irrelevant), lighting, desaturated-grey bg (should AID green vs _SAT_MIN=140). ROOT CAUSE UNRESOLVED — 4 ranked
  hypotheses (H1 compact-enclosure nav parks dog off-frame · H3 approach displaced/grasp IK-miss · H2 render/detect · H4
  scan-dir), all need the sim to falsify. BLIND SPOT found + FIXED: raw log had ZERO [PGRASP] lines (non-verbose pins
  skills/perception loggers to ERROR) → VECTOR_ACCEPT_VERBOSE=1 now adds --verbose (logging-only, face unchanged;
  test_never_injects_p_or_sim_flags guards it). 15/15 unit green (5 new TestReplCliArgv). DEBUG.md carries the plan.

frontier: Make the confirmed HOUSE green fetch TRANSFER zero-shot to go2_warehouse. Harness now
  confound-proof (E54 R231) AND trace-capable (E54 R232). NEW BAR: adjudicate H1-H4 in ONE decisive verbose run.

next:
  1. [DEBUG/VERIFY, NON-gated] ONCE host is sim-free (pgrep -f "mujoco|isaac|vcli" empty + free -g):
     run the DEBUG.md EXPERIMENT — `VECTOR_ACCEPT_VERBOSE=1 ... go2_warehouse ... MODE=fetch` ONCE,
     grep `[PGRASP]` for arrival get_position() + per-scan detection → adjudicate H1/H2/H3/H4, fix the
     top cause so green fetch TRANSFERS. This also gives the E52 N=2 clean re-run.
  2. [DEBUG/breadth, NON-gated] Apply the H1/H3 fix (nav standoff or approach re-pose for the compact
     enclosure) and re-verify green fetch GROUNDED in go2_warehouse; promote fetch.nl-new-world-warehouse.
  3. [FRONTIER/breadth, GATED] a NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene, all OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
