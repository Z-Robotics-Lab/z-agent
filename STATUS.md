# STATUS — arch/plug-and-play (snapshot, OVERWRITTEN every round; fields: doc-governance)
updated: 2026-07-03 · R279 (E76 BUILD+smoke) — goal-aware degenerate-spin reset landed; healthy fetch no-regression.
goal: PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/capability/model; plan·route·verify·recover; bare `vector-cli` + NL is the ONLY acceptance face.
phase: active (NEW-robot capability still gated S4/D182; frontier = eyes-frame workspace framing + real-thrash firing of the goal-aware guard)
last-round: R279 (E76 BUILD, non-gated). Landed the R278-frontier goal-aware degenerate-spin reset in native_loop
  (TDD): the spin counter now resets ONLY on a NOVEL (normalized-predicate, result) verify — re-reading an
  already-known outcome (the at_position-thrash interleaving ONE off-goal verify to pin the counter) is NOT progress,
  so repeats climb to the honest break@12 instead of dodging to the _MAX_NATIVE_TURNS cap. RED reproduced the R278
  symptom (repeated verify ran to the 24-cap, 24==24); GREEN via NativeStepRunner.last_verify_result +
  seen_verify_outcomes, planner-free (keys on the model's OWN verify, not the goal string). 26/26 unit green.
  Real-face MODE=fetch (deepseek-v4-flash + local gemma4:e4b) GROUNDED verified=True 1/1 with the guard SILENT
  (0 spin/nudge markers in session.log) = the goal-aware reset does NOT false-break a healthy task; eyes: green bottle
  aloft, red/purple/yellow remain=discrimination (vlm-judge ABSTAIN per known gemma4:e4b non-determ, fail-closed).
  E76 PROVISIONAL: unit + no-regression only; real-thrash FIRING is non-deterministic to induce (deferred).
frontier: (1) Real-thrash FIRING of the goal-aware guard: E76's break@12-under-repeat is unit-repro'd only; a MODE=seq/place
  run whose brain thrashes with interleaved off-goal verifies would catch it live (non-deterministic — opportunistic). (2) The
  offscreen eyes verdict-render off-centers the shelf -> vlm-judge workspace_in_frame=no/ABSTAIN false-negs on place turns;
  a cheaper camera/render-framing fix unblocks eyes-place corroboration. ROOT VLM weakness stays owner/billing (stronger VLM).
watch: Real-face recipe: bare vcli + NL; FORCE deepseek provider + deepseek-v4-flash via env (.env defaults
  qwen, ARREARAGE); local ollama gemma4:e4b eyes+judge AUTO-routed by repl_accept (do NOT set VLM/JUDGE url).
  tools/acceptance/repl_accept.py <FETCH> <PLACE> <TAG> <MODE={fetch|place|combo|seq|quantity}>. RUN under
  `systemd-run --user --scope -p MemoryMax=24G`; fetch ~5min, place ~10min, seq ~20-25min -> BACKGROUND+poll (adopt
  next round if it outlives the deadline). Sim is IN-PROCESS python (pgrep the TAG; NEVER pkill mujoco). LEDGER:
  append <=1KB/row, string field <=280 chars (Python len), never rewrite a COMMITTED row. board.py WRITES
  BOARD.md itself — run `python3 loop/board.py` (NO shell redirect; a redirect corrupts line 1).
next:
  1. [NON-gated BUILD/harness] Fix the eyes verdict-render framing so the workspace (shelf/bin) is in-frame ->
     the vlm-judge can corroborate a place instead of workspace_in_frame=no/ABSTAIN false-neg. Cheap, unblocks eyes-place.
  2. [NON-gated VERIFY, opportunistic] Adjudicate E76: promote to confirmed after a round boundary + a real MODE=seq/place
     thrash catches the goal-aware break@12 FIRING live (non-deterministic; do NOT force). Else re-confirm the no-regr smoke.
  3. [OWNER GATE — the ONLY path to NEW ROBOT capability] Unblock S4 (3rd embodiment, BYO URDF+manifest, one
     generic driver) OR D182 (world-owned NL->object grounder). CEO-gated ~35r. down-gates.
gates: (queue — do NOT cross; format docs/RULES.md CEO-gates)
  - S4 (one generic driver): a genuinely-new 3rd embodiment needs the ONE generic driver replacing per-driver MuJoCoGo2/G1 (WIRING:53) — CEO-gated (kernel/interface), multi-round SDD. <- next#3.
  - SPINE (D182): world-owned NL->object grounder — fixes witness-only fidelity AND makes grasp-vs-wander deterministic (E46); also fixes ordinal E65. <- next#3.
  - D178 near_object VLN · D176 cmd_motion seam · D168 place-oracle · relational near(a,b) · S5/S6 ladder · BILLING (qwen ROUTING brain + qwen3-vl JUDGE both Arrearage; a STRONGER local/funded VLM judge would fix R272 non-determ) · RELEASE: restructure merge to master (owner).
  - SELF-APPROVAL AUDIT (R270): gate/token R261..R279 CLEAN (no GATE/CEO-APPROVED crossings; last was R187, audited clean R209).
last_review: R270
