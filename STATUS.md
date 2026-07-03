# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R251 (E58) BUILD/DEBUG — YELLOW HOUSE FOV RECOVERED (provisional):
  next#2 taken. The long-refuted novel object yellow (y=3.11; R212/E46 REFUTED 0/2) GROUNDED
  1/1 on the bare face (deepseek-v4-flash + local ollama). ROOT CAUSE characterized, not
  fixed-blindly: the initial scan STILL returns no_detections (the FOV-margin at 3.11 is REAL)
  BUT the warehouse-built perception fixes recover it — R234 far-recovery floor localizes
  'yellow bottle', re-poses to (10.88,3.11), R237 hue-gate mask_px=4184 (not flooded), grasp
  at (10.877,3.107,0.321) actor=CAUSED. Eyes: yellow aloft in gripper, green/blue/purple/red
  REMAIN on table = real discrimination. A 2-world perception fix transferred back to HOUSE
  for free. Also cleared the preflight breach: orphaned R248 describe provisional adjudicated
  (superseded → R249→R250 confirmed). check.sh green.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: green
last-round: R251 (E58, BUILD/DEBUG, non-gated). Yellow FOV recovered to GROUNDED N=1
  provisional; R248 orphan adjudicated; 1 acceptance row + 1 experiments row.
frontier: 3 worlds ground go2 FETCH (house/warehouse/courtyard). Novel-object breadth now
  RGB+purple+YELLOW (yellow recovered R251/E58, N=1). PLATEAU STILL HOLDS (ambition critic
  R250): genuinely-new breadth is GATED — 3rd embodiment (BYO URDF, S4) + D182 world-owned
  NL→object grounder. Non-gated frontier = promote yellow N≥2, then courtyard PLACE nav debug.
watch: per-run evidence subdir BEFORE each run (VECTOR_EVIDENCE_DIR=var/evidence/R#/<tag> or
  ROUND_N) else eyes_*.png collide. Run harness with `.venv/bin/python`; Bash caps ~2-10min so
  run sims in BACKGROUND (nohup + inner timeout), monitor the log. LOCAL VLM route MANDATORY on
  every go2 run: VECTOR_VLM_URL=http://localhost:11434/v1 VECTOR_VLM_MODEL=gemma4:e4b (else 402
  silent-spin, LESSONS:36). Sim gate = pgrep 'mujoco|vcli' + free/GPU headroom, ONE sim; tear
  down via scripts/sim-teardown. LEDGER SCHEMA: confirmed rows need redteam starting 'survived'
  + all free-text ≤280 chars + row <1KB; experiments key is `e` (E<n>) (check.sh enforces).
next:
  1. [VERIFY, NON-gated] Promote yellow to confirmed: re-run HOUSE yellow-fetch across the
     R251→R252 boundary (E46 bar N≥2, same brain). On N≥2 GROUNDED, append confirmed row that
     SUPERSEDES the R212 refuted fetch.nl-novel-object-yellow row.
  2. [DEBUG, NON-gated] courtyard PLACE grasp flakiness (R247): grasp completes for FETCH but
     flaked for PLACE same world/scene — isolate (settle-time? held-arm pose? framing?).
  3. [SPINE, GATED] D182 world-owned NL→object grounder — removes witness-only fidelity; CEO gate.
  4. [FRONTIER/breadth, GATED] NEW 3rd embodiment via BYO URDF+manifest — S4 one-generic-driver (WIRING:53).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD.
  - SPINE (D182): actor-authored verify target — a world-owned NL→object grounder fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46). Object plug-in not pure config (per-object weld tuple + colour maps) → S4.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: VLM-judge + BYO-N≥4 + PERCEPTION VLM OpenRouter/dashscope-402; local Ollama gemma4:e4b is the working seam) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R250): gate/token audit R241..R249 CLEAN. R209 schema-cap approval remains the last, audited clean.
last_review: R250
