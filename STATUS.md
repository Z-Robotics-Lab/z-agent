# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R272 (E70/E71) BUILD/VERIFY — PROMOTED the vlm-judge WIRING to confirmed,
  but honestly TEMPERED R271's strong claim: the local gemma4:e4b witness is NON-DETERMINISTIC.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (verify-pillar promotion landed; NEW-robot capability still gated S4/D182)
last-round: R272 (E71 VERIFY, non-gated). FETCH '把绿色的瓶子拿过来' across the R271→R272 boundary:
  verified=True(1/1) GT-grounded + human self-read (green bottle aloft in gripper, red-can+blue/purple
  boxes remain). Eyes=vlm-judge MODE reproduces (judge fires+records, [EYES-WITNESS] emitted, stricter-only,
  GT unchanged) → verify.eyes-vlm-judge-wired PROMOTED provisional→confirmed (supersedes R271). CAVEAT
  (refutes R271's STRONG half): gemma4:e4b witness=ABSTAIN(4/4) on an equally-clear render it PASSed in R271
  → the LOCAL judge is non-deterministic, a recorded-NOT-trusted witness (fail-closed: abstain never makes a
  green, so stricter-only holds). A TRUSTED vlm-judge needs a stronger model (funded qwen3-vl / better local VLM).
  E70: PLACE run flaked verified=False(2/6) AND the judge never fired on place — `_eyes_frame('place')` runs
  BEFORE snapshot_on_verdict writes verdict_*.png (race) → 'extend vlm-judge to place' is a REAL wiring gap.
frontier: vlm-judge WIRED+confirmed but the gemma4:e4b WITNESS is too weak to trust (PASS→ABSTAIN run-to-run).
  Next verify-pillar: (a) fix the place/seq/combo judge race (order _eyes_frame AFTER the verdict snapshot),
  (b) a stronger judge model. NEW ROBOT capability STILL gated (S4 / D182, ~32 rounds unanswered).
watch: Real-face recipe per .env.example: bare vcli + NL, FORCE deepseek provider+model (default qwen route in
  ARREARAGE 400), local ollama gemma4:e4b eyes. repl_accept AUTO-routes perception (resolve_local_vlm_env) AND the
  JUDGE (resolve_judge_env, LOCAL-PREFERS gemma4:e4b — OVERRIDES the stale supervisor VECTOR_JUDGE_MODEL=qwen3-vl-plus;
  R271-verified) — do NOT set VLM/JUDGE url env. Look for `[EYES-WITNESS ...] mode=vlm-judge` + judge_witness.log in
  var/evidence. FETCH fires the judge; PLACE currently does NOT (E70 race). tools/acceptance/repl_accept.py
  <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|seq}>. RUN `.venv/bin/python` under `systemd-run --user --scope
  -p MemoryMax=24G`; MODE=seq ~15-20min → BACKGROUND+poll (Bash 120s cap). Sim is IN-PROCESS python (NOT a
  `mujoco` binary) — pgrep repl_accept, tear down MY OWN PIDs, NEVER pkill mujoco. LEDGER: append 1 line ≤1KB,
  each field ≤280 chars, never rewrite. green as a 2nd/ordinal grasp target is fragility-prone (E40/E45/E65).
next:
  1. [DEADLINE-CRITICAL adjudicate] quantity-place.nl-isolation (R270 provisional) is now age 2 → age 3 next round
     FAILS check.sh: run a DEDICATED clean seq re-run — turn2 green grounds ⇒ RE-CONFIRM; else supersede R204
     with a refuted/qualified row. (OWED since R271; must land R273.)
  2. [NON-gated BUILD] Fix the place/seq/combo vlm-judge race (E70): order `_eyes_frame` AFTER the verdict
     snapshot so the judge fires on place; unit-test then re-verify a place run with eyes=vlm-judge.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one
     generic driver) OR D182 (world-owned NL→object grounder). Both CEO-gated, unanswered ~32 rounds. See gates:.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← next#3.
  - SPINE (D182): world-owned NL→object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. ← next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: qwen ROUTING brain + qwen3-vl JUDGE both in Arrearage; local ollama gemma4:e4b + deepseek route are the working seams) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R269 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
