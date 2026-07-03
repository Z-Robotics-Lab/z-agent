# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R255 (E60) VERIFY — COURTYARD PLACE PROVISIONAL REFUTED (no N>=2 repro).
  R253/E60 GROUNDED 1/1 does NOT reproduce: bare face courtyard MODE=place → RAN verified=False
  (1/2) — grasp holding_object CAUSED, resting_on_receptacle False; bottle lost MID mobile_place
  walk (brain '掉了'→re-grasp thrash), eyes: empty-armed dog, no bottle placed. Also cleared R254 quarantine.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R255 (E60, VERIFY, non-gated). Courtyard PLACE provisional REFUTED (supersedes R253
  provisional); 1 acceptance + 1 experiments row; R254 stale-BOARD quarantine cleared; BOARD regen; check.sh green.
frontier: 3 worlds ground go2 FETCH; novel-object breadth RGB+purple+yellow ALL confirmed. Courtyard PLACE
  is the OPEN non-gated reliability gap — FLAKY across N=3 (R246 2/3, R253 1/1, R255 dropped); residual flake
  = MID-WALK DROP (holding_object lost during the mobile_place walk/dock), distinct from the nav-miss R253 fixed.
  PLATEAU HOLDS (R250 critic): genuinely-new breadth is GATED (3rd embodiment BYO URDF S4 + D182 grounder);
  non-gated frontier = PLACE reliability.
watch: per-run evidence subdir (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>) else eyes_*.png collide. Run harness
  `.venv/bin/python`; `set -a; source .env; set +a` first (DEEPSEEK_API_KEY not auto-loaded); courtyard via
  VECTOR_ROOM_TEMPLATE=courtyard; DEEPSEEK_MODEL=deepseek-v4-flash; MODE=place = one compound utterance (brain
  decomposes grasp→nav→place). Perception VLM auto-routes to local ollama gemma4:e4b (VLM env unset + ollama up).
  Drop-debug: set VECTOR_PLACE_DIAG=<path> (mobile_place Step-6b writes dog/EE-vs-receptacle JSON, verdict-neutral).
  Sims slow+FLAKY (~4-8min place); run BACKGROUND (timeout 900), tear down via scripts/sim-teardown. Sim gate =
  pgrep 'mujoco|vcli|repl_accept' + free/GPU headroom, ONE sim (MuJoCo runs IN-process → pgrep mujoco finds nothing;
  a leftover --native-loop repl_accept orphan holds ~4.5GB). LEDGER: confirmed redteam starts 'survived'; free-text
  ≤280 chars + row <1KB; experiments key is `e`; append ONE preformatted line (E27), never load-all+dumps.
next:
  1. [DEBUG, NON-gated] Root-cause the courtyard PLACE mid-walk drop (R255/E60): re-run MODE=place courtyard with
     VECTOR_PLACE_DIAG set + grep [MOBILE-PLACE] to distinguish weld-break-under-locomotion (grasp stability) vs
     off-receptacle drop-release. Hypothesis Loop → DEBUG.md; regression-test the fix; re-verify N>=2 clean before
     any promotion. Do NOT re-diagnose as a nav-miss (E23: R253 already fixed that sub-failure).
  2. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
