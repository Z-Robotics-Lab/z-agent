# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R252 (E59) VERIFY — YELLOW HOUSE FETCH CONFIRMED N=2:
  next#1 taken. The long-refuted novel object yellow (y=3.11; R212/E46 REFUTED 0/2) is now
  CONFIRMED on the bare face — 2nd same-brain repro across the R251→R252 boundary
  (deepseek-v4-flash + local ollama gemma4:e4b), meeting the E46 N≥2 bar. Same recovery
  mechanism as R251: initial scan STILL no_detections (FOV-margin y=3.11 REAL) but the
  warehouse-built R234 far-recovery + R237 hue-gate fire: far-seed localize→re-pose→
  mask_px=4184→grasp (10.877,3.107,0.321), holding_object(bottle_yellow) actor=CAUSED.
  Eyes (var/evidence/R252/yellow/eyes_fetch.png): yellow aloft in the Piper gripper,
  green/blue/purple/red REMAIN on the pedestal = real discrimination. Appended confirmed
  acceptance row SUPERSEDING the R212 refuted yellow row. check.sh green; sim torn down.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R252 (E59, VERIFY, non-gated). Yellow HOUSE fetch CONFIRMED N=2 (supersedes
  R212 refuted); 1 acceptance confirmed row + 1 experiments row; BOARD regenerated.
frontier: 3 worlds ground go2 FETCH (house/warehouse/courtyard). Novel-object breadth now
  RGB+purple+YELLOW ALL confirmed (yellow closed R252/E59). PLATEAU STILL HOLDS (ambition
  critic R250): genuinely-new breadth is GATED — 3rd embodiment (BYO URDF, S4) + D182
  world-owned NL→object grounder. Non-gated frontier = courtyard PLACE nav/grasp debug.
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag> or
  ROUND_N) else eyes_*.png collide. Run harness with `.venv/bin/python`; source .env first
  (DEEPSEEK_API_KEY not auto-loaded). Bash caps ~2-10min so run sims in BACKGROUND (nohup +
  inner timeout), monitor the log. Perception VLM AUTO-ROUTES to local ollama gemma4:e4b when
  VLM env unset + ollama up (resolve_local_vlm_env) — no need to set VECTOR_VLM_URL manually;
  never inherit OpenRouter perception route (402 silent-spin, LESSONS:36). Sim gate = pgrep
  'mujoco|vcli' + free/GPU headroom, ONE sim; tear down via scripts/sim-teardown. LEDGER
  SCHEMA: confirmed rows redteam starts 'survived' + all free-text ≤280 chars + row <1KB;
  experiments key is `e` (E<n>) (check.sh enforces).
next:
  1. [DEBUG, NON-gated] courtyard PLACE grasp flakiness (R247): grasp completes for FETCH but
     flaked for PLACE same world/scene. R247 root-caused the NAV snag (navigate(10.8,3.0)
     unreachable inside inflated pick_table, EVERY world); PLACE-leg model-flakiness still open.
  2. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  3. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
