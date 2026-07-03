# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R270 (E68) REVIEW — skeptic re-verify of the OLDEST stale BOARD row
  quantity-place.nl-isolation (R204 age65, MODE=seq) did NOT cleanly reproduce: turn1 place-BLUE
  RE-CONFIRMED True(2/2) but turn2 place-GREEN emitted 0 verdicts (green-2nd-object grasp thrash ~15min).
  R204 repro-QUESTIONED (provisional PARTIAL row), NOT refuted — place machinery holds, 2nd place never reached.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: blocked
last-round: R270 (E68, REVIEW, non-gated). SKEPTIC (bare-face, deepseek-v4-flash brain + local gemma4:e4b
  eyes, MODE=seq): isolation turn1 blue GROUNDED True(2/2) grasp holding(blue) CAUSED + place resting GT-True;
  turn2 green looped detect+perception_grasp(green) ~15min, grasp never grounded (seq2=[]) → NOT a clean 2/2 repro.
  RE-RED-TEAM of R262 'non-gated frontier EXHAUSTED' REFINED, not overturned: acceptance/vision_judge.py is a
  BUILT fail-closed VLM judge wired into visual_e2e.py but ORPHANED from repl_accept (why EVERY ledger row is
  eyes=self-read) — a LOCAL gemma4:e4b judge (0 credit, stricter-only Inv.1) is a genuinely NON-gated verify-pillar
  BUILD, D181 mislabel corrected. WIRING verify-spine + embodiments re-audited accurate (stamps R240→7bc6ca0).
  Gate/token R261-269 CLEAN (last crossing R187). LESSONS folded critics R230-260→1 line (260→255). PLATEAU: R260-R269 = ZERO new confirmed capability.
frontier: BLOCKED for NEW ROBOT capability (S4/D182 gated ~30 rounds) — BUT the verify pillar has ONE non-gated
  build the loop mislabeled external-blocked: wire the orphaned vision_judge.py to the LOCAL gemma4:e4b so the
  acceptance face upgrades self-read→automated vlm-judge (removes the manual-eyes dependency D181 called 'the ONE thing').
watch: Real-face recipe per .env.example: bare vcli + NL, force the deepseek provider+model (default qwen route in
  ARREARAGE 400), local ollama gemma4:e4b eyes (repl_accept AUTO-routes via resolve_local_vlm_env — do NOT set the
  VLM url env; the qwen3-vl JUDGE shares the arrears key → eyes=self-read). tools/acceptance/repl_accept.py
  <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|seq}>. RUN `.venv/bin/python` under `systemd-run --user --scope
  -p MemoryMax=24G`; MODE=seq (2 place legs) ~15-20min → BACKGROUND+poll (Bash 120s cap). Sim is IN-PROCESS python
  (NOT a `mujoco` binary) — pgrep repl_accept, tear down MY OWN PIDs (kill the repl_accept tree), NEVER pkill mujoco.
  LEDGER: append 1 preformatted line ≤1KB, each field ≤280 chars, never rewrite. NOTE: green as a 2nd/ordinal grasp
  target is fragility-prone (E40/E45/E65) — a seq/ordinal 'confirmed' with a green target is a doubly-fragile skeptic row.
next:
  1. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment via BYO URDF+manifest, one generic
     driver) OR D182 (world-owned NL→object grounder). Both CEO-gated, unanswered ~30 rounds. See gates: below + LESSONS ## Frontier.
  2. [NON-gated BUILD — cracks the plateau] Wire the ORPHANED acceptance/vision_judge.py into repl_accept._eyes_frame
     against the LOCAL gemma4:e4b (VECTOR_JUDGE_* → the local ollama endpoint, per .env.example): flip acceptance eyes
     self-read→vlm-judge (secondary witness, stricter-only Inv.1, 0 credit). NOT a spine edit (judge is 'never the moat'). → E68/LESSONS.
  3. [NON-gated HYGIENE] Adjudicate the R270 PARTIAL provisional (quantity-place.nl-isolation): dedicated clean seq re-run
     — turn2 green grounds ⇒ RE-CONFIRM; else supersede R204 with a refuted/qualified row. Next stale after: quantity-place.nl (age65 FLAKY).
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. ← next#1.
  - SPINE (D182): world-owned NL→object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. ← next#1.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (external: qwen ROUTING brain + qwen3-vl JUDGE both in Arrearage; local ollama gemma4:e4b + deepseek route are the working seams) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R269 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
