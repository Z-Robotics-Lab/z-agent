# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)

updated: 2026-07-03 · R231 (E54) BUILD — hardened the acceptance harness against the R230/E53
  perception-VLM 402 confound; re-opened E52 warehouse cleanly (N=1): still RAN 0/1, but for a REAL
  grasp gap, not billing — so E52's 0/2 was NOT purely a confound.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R231 (E54, BUILD). Executed STATUS next#1 (HARNESS-HARDEN, non-gated).
  (a) NEW tools/acceptance/vlm_guard.py (pure, 10/10 unit tests green): resolve_local_vlm_env
  auto-routes VECTOR_VLM_URL=localhost:11434/gemma4:e4b when unset AND Ollama up (probe /api/tags),
  else fail-LOUD with the recipe; detect_perception_402 matches the perception-VLM
  'OpenRouter API client error 4xx' signature — verified True on the REAL var/evidence/R229 402
  stream (would have caught E52). (b) repl_accept.py now auto-routes BEFORE spawn + aborts a turn
  with a distinct VLM-BILLING-402 marker instead of a 300s silent spin. VERIFY (next#2, N=1): green
  fetch in go2_warehouse WITH the hardened harness RAN 0/1 — driver logged 'auto-routed', clean
  stream ZERO 402, fail is a REAL perception_grasp_skill -> verify holding_object() FAIL ([FAIL]1/2,
  84s) ⇒ R230's 'E52 0/2 = purely 402 confound' DISPROVEN at N=1. run2 DEFERRED (sibling Isaac
  warehouse_scene.py sim live; Inv-5 ONE-sim — did NOT launch a 2nd or kill it). My sim torn down clean.

frontier: Harness now confound-proof. Live REAL question: green fetch does NOT transfer zero-shot to
  go2_warehouse even confound-free (perception_grasp gap). NEW BAR: debug so a confirmed bar TRANSFERS.

next:
  1. [VERIFY/breadth, NON-gated] Complete E54 N=2: RE-RUN green fetch in go2_warehouse via the
     hardened harness (auto-routes local VLM) ONCE the host has NO concurrent sim (check pgrep
     mujoco|vcli|isaac + free -g; WAIT for the sibling Isaac sim to clear). 2nd clean-route RAN-0
     confirms the warehouse transfer gap is real & reproducible (not brain-flake).
  2. [DEBUG/breadth, NON-gated] Hypothesis-Loop the warehouse perception_grasp failure (DEBUG.md):
     holding_object() FAILs after perception_grasp_skill — is it detector (green geom vs warehouse
     clutter), approach/framing (dog start pose vs table), or grasp IK? Compare vs the HOUSE green
     fetch that GROUNDS (R230). Fix so the confirmed bar TRANSFERS zero-shot to the new world.
  3. [FRONTIER/breadth, GATED] a NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver
     (WIRING:53) + new MuJoCo assets; multi-round SDD.

gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N>=4 + PERCEPTION VLM look/describe_scene, all OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R230): gate/token audit R211..R230 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R230
