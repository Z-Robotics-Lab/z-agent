# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R271 (E69) BUILD — cracked the R260-269 plateau on the VERIFY pillar:
  wired the ORPHANED acceptance/vision_judge.py into repl_accept `_eyes_frame`; the acceptance
  eyes flipped self-read→vlm-judge on the REAL bare-cli face (deepseek-v4-flash brain + LOCAL
  gemma4:e4b judge, 0 credit). fetch verified=True(1/1) AND eyes vlm-judge PASS(4/4), GT unchanged.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (non-gated verify-pillar build landed; NEW-robot capability still gated S4/D182)
last-round: R271 (E69, BUILD, non-gated). `resolve_judge_env` (tools/acceptance/vlm_guard.py) LOCAL-PREFERS
  gemma4:e4b whenever Ollama up, OVERRIDING the stale supervisor-exported VECTOR_JUDGE_MODEL=qwen3-vl-plus
  (arreared → else abstains forever; first cut wrongly honoured it); escape hatch VECTOR_JUDGE_FORCE_REMOTE=1.
  `_eyes_frame` now runs `vision_judge.judge` on the offscreen render; witness RECORDED alongside GT, NEVER
  folded into verified= (stricter-only Inv.1). Red-team: judge FAILs a black frame (scene_rendered=no) + PASSes
  the real render → DISCRIMINATING not rubber-stamp. Self-read corroborates: green bottle aloft, 4 distractors
  remain. 30 harness + 38 vision_judge unit tests green. Non-spine (tools/ + repl call; vision_judge.py unedited).
frontier: EYES pillar upgraded self-read→vlm-judge (removes D181 'the ONE thing' manual-eyes dependency).
  NEW ROBOT capability STILL gated (S4 3rd embodiment / D182 NL→object grounder, ~31 rounds unanswered).
  Verify-pillar outward: extend vlm-judge to place/seq/combo MODEs; a DISAGREEMENT (GT True + judge FAIL)
  auto-downgrade→red-team is the next stricter-only step.
watch: Real-face recipe per .env.example: bare vcli + NL, force deepseek provider+model (default qwen route in
  ARREARAGE 400), local ollama gemma4:e4b eyes. repl_accept AUTO-routes perception (resolve_local_vlm_env) AND the
  JUDGE (resolve_judge_env, local-preferred — no longer eyes=self-read) — do NOT set VLM/JUDGE url env. Look for
  `[EYES-WITNESS ...] mode=vlm-judge` + judge_witness.log in var/evidence. tools/acceptance/repl_accept.py
  <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|seq}>. RUN `.venv/bin/python` under `systemd-run --user --scope
  -p MemoryMax=24G`; MODE=seq ~15-20min → BACKGROUND+poll (Bash 120s cap). Sim is IN-PROCESS python (NOT a
  `mujoco` binary) — pgrep repl_accept, tear down MY OWN PIDs, NEVER pkill mujoco. LEDGER: append 1 line ≤1KB,
  each field ≤280 chars, never rewrite. green as a 2nd/ordinal grasp target is fragility-prone (E40/E45/E65).
next:
  1. [NON-gated PROMOTE] Re-run fetch (or place) with eyes=vlm-judge across the R271→R272 boundary; if verified=True
     + judge PASS reproduces, PROMOTE verify.eyes-vlm-judge-wired provisional→confirmed. Then extend vlm-judge to place/seq MODEs.
  2. [NON-gated HYGIENE] Adjudicate the R270 PARTIAL provisional (quantity-place.nl-isolation): dedicated clean seq re-run
     — turn2 green grounds ⇒ RE-CONFIRM; else supersede R204 with a refuted/qualified row. (STILL OWED — deferred from R271.)
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one generic
     driver) OR D182 (world-owned NL→object grounder). Both CEO-gated, unanswered ~31 rounds. See gates: below + LESSONS ## Frontier.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← next#3.
  - SPINE (D182): world-owned NL→object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. ← next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: qwen ROUTING brain + qwen3-vl JUDGE both in Arrearage; local ollama gemma4:e4b + deepseek route are the working seams) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R269 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
