# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R253 (E60) BUILD/VERIFY — COURTYARD PLACE RECOVERED to GROUNDED
  provisional N=1 (2/2, was R246 2/3): STATUS next#1. R247/E56 REFUTED the courtyard
  PLACE-leg, but its own root-cause was that mobile_place's transient FIRST-NAV miss
  surfaced to the brain as False, which the brain "recovered" by improvising an
  UNREACHABLE navigate(10.8,3.0) — ungrounding the composite though the physical place
  always succeeded. Fix (TDD, non-gated, intra-package): mobile_place now retries the
  approach nav internally (_NAV_RETRIES=1, re-reads pose) so a transient miss stays inside
  the skill; a genuinely-unreachable target still fast-fails → honest nav_failed. Bare
  face (v4-flash + ollama gemma4:e4b, courtyard MODE=place): holding_object(green) CAUSED +
  resting_on_receptacle True = 2/2 GROUNDED, no spurious brain navigate. Eyes
  (var/evidence/R253/place/eyes_place.png): green IN place_bin, purple/red REMAIN =
  discrimination. HONEST: the retry did NOT fire (first nav landed) → unit-tested only, N=1.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R253 (E60, BUILD/VERIFY, non-gated). Courtyard PLACE GROUNDED provisional N=1
  (supersedes R247 refuted); 1 acceptance + 1 experiments row; 22/22 mobile_place unit; BOARD regen.
frontier: 3 worlds ground go2 FETCH; novel-object breadth RGB+purple+yellow ALL confirmed.
  Courtyard PLACE now provisionally recovered (was the last refuted go2 capability). PLATEAU
  HOLDS (R250 critic): genuinely-new breadth is GATED — 3rd embodiment (BYO URDF, S4) + D182
  world-owned NL→object grounder. Non-gated frontier thins to PLACE reliability + robustness.
watch: per-run evidence subdir (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag>) else eyes_*.png collide.
  Run harness `.venv/bin/python`; `source .env` first (DEEPSEEK_API_KEY not auto-loaded); courtyard
  via VECTOR_ROOM_TEMPLATE=courtyard; MODE=place sends one compound utterance (brain decomposes
  grasp→nav→place). Perception VLM auto-routes to local ollama gemma4:e4b (VLM env unset + ollama up).
  Sims slow (~4min grasp+place); run BACKGROUND (timeout 600 + nohup), tear down via scripts/sim-teardown.
  Sim gate = pgrep 'mujoco|vcli' + free/GPU headroom, ONE sim. LEDGER: confirmed redteam starts
  'survived'; all free-text ≤280 chars + row <1KB; experiments key is `e` (check.sh enforces).
next:
  1. [VERIFY, NON-gated] Adjudicate R253/E60 courtyard PLACE provisional: re-run MODE=place courtyard
     for N≥2 same-brain repro across the boundary (promote confirmed, supersedes R247 refuted). Bonus:
     try to face-TRIGGER the nav-retry (a run whose first nav genuinely misses) to exercise the fix on the face.
  2. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
