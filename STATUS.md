# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R234 (E54) DEBUG — BROKE the 3-round sim block: the repo's OWN sim gate
  (`pgrep -f "mujoco|vcli"` + `free -g`) was CLEAR (44G RAM / 12G GPU free); the sibling Isaac
  `/workspace/go2w` sim is a different engine that does NOT trip the pattern. So the decisive
  warehouse fetch finally RAN with the `[PGRASP]` trace, and adjudicated R229-R233's H1-H4.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R234 (E54, DEBUG, non-gated). ROOT-CAUSED the HOUSE→warehouse transfer gap: far-seed
  localizes the bottle at correct (10.86,3.00) (world+detector fine, H2 refuted); nav stops the dog
  0.88m off but front_object_mask=0px 6/6 scan, d_min~0.55m (mis-oriented at an obstacle, H3 approach
  CONFIRMED); far-recovery re-approach was band-gated d∈(1.6,8.0] → SKIPPED at 0.88m = DEAD-BAND.
  FIX (skill-only, not spine): perception_grasp `_far_localize_and_approach` floor 1.6→0.30m
  (`_RECOVERY_MIN_M`), recover-by-repose from any plausible distance. TDD 11/11+36/36 unit green
  (f437f4e). Acceptance row R234 refuted supersedes R231 (preflight unblocked). E2E re-verify of the
  fix launched in BACKGROUND (var/evidence/R234/verify.log, inflight.json) — R235 adopts the verdict.

frontier: Make the confirmed HOUSE green fetch TRANSFER to go2_warehouse — root cause now KNOWN
  (far-recovery dead-band) and fix shipped; the bar is now the e2e GROUNDED verdict of that fix.

watch: R234 background e2e verify (unit vecacc-r234-verify.scope) may be LIVE at R235 start — preflight pgrep finds it: WAIT + adopt (OURS), never kill (NEVER-KILL-INFRA).

next:
  1. [VERIFY, NON-gated] ADOPT the R234 inflight run (loop/.state/inflight.json): read
     var/evidence/R234/verify.log for `[RESULT r234b] fetch_verified/fetch_grounded` + grep its
     raw trace (path in inflight.json) for `[PGRASP] far recovery` (must NO LONGER SKIP at d<1.6
     — should navigate_to standoff + face + re-perceive). Append the acceptance row (GROUNDED→
     confirmed-provisional / RAN→refuted new mode) + clear inflight; LOOK at the persisted frame.
  2. [DEBUG/breadth, NON-gated] If the fix grounds, run N≥2 for robustness, then promote
     fetch.nl-new-world-warehouse. If not, iterate the approach-pose fix (dog still faces the
     obstacle — face-then-sidestep or a pre-grasp standoff re-plan for the compact enclosure).
  3. [FRONTIER/breadth, GATED] a NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
